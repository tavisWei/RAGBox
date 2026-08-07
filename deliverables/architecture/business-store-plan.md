# 业务数据库（MySQL）与存储切换管理方案

- 版本：v1.0（2026-08-07）
- 背景：组件配置页的 MySQL 此前只是"业务数据库"占位。本方案实现业务数据的 MySQL 后端、业务库/向量库的单选切换与"先迁移后切换"。

## 0. 现状问答

- **有没有相关管理页面？** 没有业务数据库的管理页面。向量后端的选择已有两处入口（组件配置页启用开关、知识库"检索后端"配置），但业务数据写死在本地 JSON 文件。
- **是否互斥单选？** 是。业务库：local（JSON 文件）与 mysql 二选一；向量库：sqlite/pgvector/es/qdrant/milvus/mysql 单选（选择链已存在）。

## 1. 业务数据现状（迁移对象）

12 个 `LocalStore` JSON 命名空间（api/data/*.json）：users、sessions、apps、chat_roles、chat_state、knowledge_bases、model_providers、prompt_templates、resource_configs、component_configs、workflows、workflow_runs。`LocalStore` 语义为"整文件 dict 读/写"（`local_store.py`）。

例外：`workflow_runs.sqlite3` 是 run 记录的查询镜像（真源是 workflow_runs.json），切换后读路径需改为读主存储（见 §3.3）。

## 2. 架构

```
api/services/business_store/
├── base.py       # BusinessStoreBackend: read_namespace/write_namespace/list_namespaces/health_check
├── local_backend.py   # 现有 JSON 文件行为（默认）
├── mysql_backend.py   # business_kv 表：namespace 一行，payload 为整命名空间 JSON（与 LocalStore 语义一致）
└── manager.py    # 活跃后端解析与切换：系统设置 > BUSINESS_STORE_TYPE env > local
```

- `LocalStore` 改为薄壳：read/write/update 按文件名委托给 `manager.get_backend()`。全部 12 个消费方零改动。
- MySQL 表：`business_kv(namespace VARCHAR(128) PRIMARY KEY, payload MEDIUMTEXT, updated_at VARCHAR(40))`。整命名空间单行的原因是 LocalStore 本身就是整 dict 读写，拆行会引入并发合并问题且收益为零（体量小）。
- 切换设置持久化在 `api/data/system_settings.json`（**直接文件读写，不经 LocalStore**，避免自举循环）。

## 3. 切换与迁移（先迁移后切换）

### 3.1 业务库迁移

`POST /system/storage/business/migrate {target, config}`：

1. 用 config 建目标后端并 health_check（失败即 400，不动现状）
2. 逐命名空间 `read → write` 复制，逐命名空间校验（payload 相等）
3. 全部一致后写入 `system_settings.json` 切换；任何一步失败不切换
4. 回迁：`{target: "local"}` 同理（local 数据从未删除，天然可回退）

### 3.2 向量库切换

向量数据跨后端迁移不做（维度随 embedding 模型变化，正确路径是重建索引）：

`POST /system/storage/vector/switch {type, config}`：连通性检查通过 → 组件层启用该后端（复用 component_config 机制）→ 返回 `{switched: true, reindex_required: true, message: "训练素材需重新导入/重建索引"}`，并把各 KB 标记 `reindex_required=true`（该字段与前端提示已存在）。

### 3.3 workflow_runs 读路径调整

`workflow_store.py` 的 `_list_workflow_runs_for`/`load_workflow_run` 从"查 sqlite 镜像"改为"读主存储（LocalStore 命名空间）"，sqlite 镜像停止写入（存量数据 JSON 与镜像同源，无丢失）。否则切换业务库后 run 历史读不到。

## 4. API 与前端

新端点（挂在 component_configs 路由组）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/system/storage` | 当前业务库/向量库、可选列表、各命名空间统计 |
| POST | `/system/storage/business/test` | MySQL 连通性 |
| POST | `/system/storage/business/migrate` | 迁移+切换（§3.1） |
| POST | `/system/storage/vector/switch` | 向量库切换（§3.2） |

前端 `ComponentConfigsView.vue` 顶部加"存储管理"卡片：当前业务库展示、MySQL 参数表单、"迁移并切换"按钮（成功后提示可回迁）、向量库切换带"需重新导入训练素材"确认框。

## 5. 测试

- mysql backend：fake pymysql 验证建表/读写/列举
- 迁移：local → fake mysql 全命名空间复制 + 校验 + 设置翻转；失败路径不切换
- resolver：设置 > env > local
- workflow_runs 读路径改后主流程测试（审批/历史）回归
- 全量回归

## 6. 非目标

- 不把业务数据拆表规范化（users/sessions 等仍整命名空间 JSON）；需要真正的关系模型另立项。
- 不做向量数据跨后端搬运。
- omo_task_queue.db 与本系统无关，不涉及。

---

## 7. 实施结果（2026-08-07，已完成）

- `api/services/business_store/`：`base.py`（后端接口）+ `local_backend.py`（JSON 文件，排除 system_settings.json）+ `mysql_backend.py`（`business_kv` 表，pymysql 惰性导入）+ `manager.py`（解析：系统设置 > `BUSINESS_STORE_TYPE` env > local；`migrate_and_switch` 先复制逐条校验后切换）。
- `LocalStore` 改为委托壳，12 个消费方零改动；`workflow_store.py` 的 run 记录读路径从 sqlite 镜像改为主存储，sqlite 双写删除。
- 端点（component_configs 路由组）：`GET /system/storage`、`POST /system/storage/business/test`、`POST .../business/migrate`、`POST .../vector/switch`（连通检查→启用组件→标记全部 KB `reindex_required`→提示重新导入训练素材）；配置输出密码掩码。
- 前端 `ComponentConfigsView.vue` 顶部新增"存储管理"卡片：业务库 MySQL 表单 + 测试连接 + 迁移并切换（含确认框、可迁回本地）；向量库选择 + 直接切换（确认框明确提示重新导入）。运行时提示文案更新为真实语义。
- 测试 `api/tests/test_business_store.py` 8 项：local/mysql 后端 roundtrip、迁移往返、校验失败不切换、env 覆盖、端点冒烟。全量回归 **532 passed**，前端 `vue-tsc` 通过。
- 如实边界：MySQL 业务后端过的是 fake pymysql 测试，未经真实 MySQL 实例实测；密码以明文存于 `system_settings.json`（与 component_configs.json 现状一致，输出掩码），生产建议走密钥管理。
