# RAG 四处"水分"实做方案与实施记录

- 版本：v1.0（2026-08-07，已全部实施完成）
- 背景：`langgraph-migration-plan.md` 之外的独立工作流——把 RAG 链路中四处占位/假实现做真。

## 1. pgvector 向量库接入

**改动**
- `api/services/rag_service.py`：新增 `_pgvector_config_from_env()`，支持 `PGVECTOR_DSN`（SQLAlchemy 风格连接串，驱动实为 psycopg2，scheme 后缀无关）或 `PGVECTOR_HOST/PORT/USER/PASSWORD/DATABASE` 分项配置；`DATA_STORE_TYPE=pgvector` 时生效。知识库路由经 `_kb_datastore_config`（`knowledge_bases.py:139`）读取 `DATA_STORE_TYPE`，无需改路由。
- 修复真 bug 1：`create_collection` 之前不传 dimension → HNSW 索引永远不建。现在 `add_documents` 用真实向量维度调用（`pgvector_data_store.py:124` 的显式维度分支才建索引）。
- 修复真 bug 2：pgvector 全文检索用 `to_tsvector('simple', ...)`，对中文不切词、永远查不中。增加 pg_trgm `similarity + ILIKE` 回退（扩展本来就在 `_init_extensions` 创建了）。
- 零向量降级维度按 provider 区分（openai 1536 / 其他 768），避免 pgvector 强类型列拒收。

**启用方式**：`DATA_STORE_TYPE=pgvector PGVECTOR_DSN=postgresql+asyncpg://aiwriter:aiwriter@localhost:5432/aiwriter ./start.sh`

**验证**：`api/tests/integration/test_pgvector_store.py`（4 项）——对 rag_test 库实测建表（断言 HNSW 索引存在）、入库、semantic/fulltext/hybrid 检索。

## 2. 查询扩展 / LLM 重排做真

**根因**：`rag_service.py` 的 `llm_fn` 返回空串；且检索器全同步、LLM 调用全异步。

**改动**
- `RAGService._retrieve_docs`：检索整体移入 `asyncio.to_thread`（顺带修掉同步检索阻塞事件循环）；`llm_fn` 在工作线程内用 `asyncio.run` 桥接 `LLMService.chat`（该线程无运行中的 loop，合法）。
- `use_reranker` 入参此前从未生效——现在 `False` 时强制 `rerank_mode=NONE`。
- 修复隐患：`LLMListwiseReranker` 在 LLM 返回空/不可解析时会把整批结果吞掉（返回空列表），现在回退原始顺序。

**验证**：`api/tests/test_rag_retrieval_real.py`（4 项）——扩展 prompt 确实到达 LLM、`use_reranker=False` 生效、空解析回退。

## 3. query_stream 真流式

`query()` 拆出 `_retrieve_docs` + `_build_messages` 两个共享helper；`query_stream` 复用后改走 `llm_service.chat_stream` 逐 token 产出，不再是"跑完按空格回放"。测试断言真实经过 `chat_stream`。

## 4. jieba 关键词检索腿

**改动**
- `BaseDataStore` 新增可选能力 `list_documents` / `get_documents_by_ids`（默认空实现），sqlite 与 pgvector 两个 store 均已实现（sqlite 全局表按 `metadata.knowledge_base_id` 过滤，跨库隔离有测试）。
- `MultiWayRetriever` 新增 `keyword_search` 回调参数：配置了该回调时，`keyword` 方法与 `hybrid` 方法都会额外产生一条 jieba 关键词检索腿，结果走 RRF/加权融合。
- `RAGService` 维护每 KB 的内存关键词倒排表（`KeywordTableHandler`）：入库时同步更新；进程重启后首次查询时从 data store 懒重建（有测试覆盖两种路径）。jieba 缺失时该腿静默关闭。
- `weight_rerank.py` 仍未接入——其输入是另一套 pydantic `Document` 模型，接入需要先统一模型，列入后续项（见 §6）。

**验证**：`api/tests/test_rag_keyword_leg.py`（3 项）——关键词腿独立命中、重启重建、store 层 list/get_by_ids 与跨库隔离。

## 5. index_processor 做真

**改动**
- `ParagraphIndexProcessor`：清除重复定义与死代码；`load/clean/retrieve` 经 `BaseIndexProcessor` 新增的 `_load_to_store/_clean_from_store/_retrieve_from_store` 共享实现落到 data store。
- `ParentChildIndexProcessor`：新增 `flatten_parent_child`（幂等——无 children 的文档原样透传）与 `collapse_parent_child_docs`；`load` 存子块（metadata 带 `parent_id`/`parent_content`），`retrieve` 命中子块后折叠回父段落。`RAGService._retrieve_docs` 统一调用折叠（无父子元数据的文档不受影响）。
- `QAIndexProcessor`：`_generate_qa_pairs` 接真实 LLM（注入式 `llm_function`，输出再用同一 QA 正则解析）；无 LLM 时回退普通切块。
- 入库路由（`knowledge_bases.py` 的 add_document / upload_document）：`splitter_config.index_mode` 支持 `paragraph`（默认，行为不变）/ `parent_child` / `qa`，经 `asyncio.to_thread` 调处理器；QA 的 LLM 生成经 `QA_GENERATION_PROVIDER`/`QA_GENERATION_MODEL` 环境变量启用。

**验证**：`api/tests/test_index_processors.py`（7 项）——段落 roundtrip、父子 transform/flatten/collapse/retrieve 返回父段落、QA 正则提取、QA LLM 生成、无 LLM 回退、路由级 parent_child 入库。

## 6. 已知边界（非目标）

- `weight_rerank.py` 需要先做 Document 模型统一，暂不接。
- 关键词倒排表是进程内存，多实例部署不共享（落库/Redis 化是后续项）。
- CrossEncoder 重排需要 `sentence-transformers`（未装），未配置时静默回退原序。
- pgvector 驱动为 psycopg2 同步 + 连接池，经 `asyncio.to_thread` 运行不阻塞事件循环；如需全异步可后续换 asyncpg。

**全量回归：497 passed**（含 pgvector 容器实测 4 项）。

---

## 7. 检索后端配置入口（2026-08-07 追加）

回答"前端有没有 pg 配置入口 / 能不能切换 / 参数够不够"——之前的答案是：只有标签没有参数、聊天路径硬编码 sqlite 导致切换即数据丢失、参数不满足使用。本次补齐：

**后端**
- `resolve_datastore_config(kb)`（`api/api/knowledge_bases.py`）成为唯一选择逻辑：**KB 级 datastore 配置 > `DATA_STORE_TYPE` env > 方案预设 recommended_backend > sqlite**；无 KB 上下文（纯聊天）永不默认外部后端。
- `retrieval.py build_rag_service` 删除硬编码 `sqlite`，改用同一解析函数——入库与问答两条路径从此一致。
- KB 记录新增 `datastore` 字段：`{type, dsn}` 或 `{type, host, port, user, password, database}`（分项与 DSN 二选一；分项未填的字段在 RAGService 内回退 `PGVECTOR_*` env）。`PUT /knowledge-bases/{id}` 校验 type/port/DSN。
- 安全：API 输出中 `dsn` 密码段与 `password` 字段一律掩码（`****`）；前端回传掩码或留空时后端保留原值，不会被掩码覆盖。
- 新增 `POST /knowledge-bases/test-datastore`：按给定配置（DSN 或分项）真实连接并 `health_check`，失败返回 400 + 原因。

**前端**（`KnowledgeBaseDetailView.vue` 设置区新增"检索后端"卡片）
- 后端类型下拉：跟随方案/环境（默认）、SQLite、pgvector、Elasticsearch
- pgvector 展开完整参数：主机、端口、数据库名、账号、密码（密码框留空=不修改）+ "测试连接"按钮
- `api/index.ts`：`update` 支持 `datastore`，新增 `testDatastore`

**验证**：`api/tests/test_kb_datastore_config.py` 8 项（优先级、掩码、密码保留、清空回退、非法类型 400、容器实测连通/错误密码 400）；全量回归 **505 passed**；前端 `vue-tsc` 通过。

**已知边界**：Elasticsearch 后端可在 UI 选择，但其 store 的字段级参数（host 等）未做分项表单（代码里走默认 localhost:9200）；换 embedding 模型导致维度变化时仍需重建集合（`reindex_required` 标记已有）。

---

## 8. 组件配置页接通运行时（2026-08-07 追加）

回答"组件配置下的组件是否都能切换能用"——之前只有 SQLite 真正生效，配置页是"记录本 + TCP 探测"。本次改造：

**运行时接通**（`component_config_service.py` + `resolve_datastore_config`）
- 新增 `get_active_datastore()`：启用的数据存储组件（sqlite/pgvector/elasticsearch）即全局默认检索后端；多个启用时非 SQLite 优先。
- 选择链最终形态：**KB 级配置 > `DATA_STORE_TYPE` env > 组件配置页（启用的组件）> 方案预设 > sqlite**。
- 语义变化（已记录）：组件页默认 sqlite 启用，因此方案预设的 recommended_backend 默认被组件层遮蔽——两条路径（入库/问答）现在一致默认 sqlite，与长期以来的聊天路径行为对齐；要 pgvector 就在组件页启用并填参数，或设 env，或 KB 级覆盖。配置映射：pgvector 的 username→user、端口转 int；ES 的 hosts 逗号拆分。
- `runtime_note` 文案更新为真实语义。

**连通性测试做真**
- `test_component` 对 sqlite/pgvector/elasticsearch 改为真实 `DataStoreFactory.create + health_check`（建扩展、验证账号密码），不再是 TCP 探测。
- mysql/qdrant/milvus 保持 TCP 探测，消息中明确标注"仅 TCP 探测：该组件未接入检索运行时"。

**验证**：`api/tests/test_component_config_runtime.py` 6 项（默认 sqlite、启用 pgvector 胜出、完整优先级链、sqlite 真实检查、pgvector 容器实测成功/错误密码失败、未接入组件标注）；`test_kb_datastore_config.py` 相应调整；全量回归 **511 passed**。前端 `ComponentConfigsView.vue` 本就有启用开关/编辑/测试按钮，无需改动。

**仍未接入**：MySQL（无运行时消费方，纯记录）、Qdrant/Milvus（无 store 实现，规划中标注保留）。

---

## 9. Qdrant / Milvus store 实现 + ES 代码验证（2026-08-07 追加）

- **`qdrant_data_store.py`**（新）：Qdrant REST API 实现，只用 httpx 无新依赖——`PUT /collections`（cosine + 维度）、points upsert、`/points/search` 向量检索、payload `match text` 全文腿（无评分，按出现次数排序）、scroll 列举、按 id 取回、delete/stats/health_check 全套。
- **`milvus_data_store.py`**（新）：pymilvus 实现（惰性 import，缺依赖时报清晰安装提示）——HNSW+COSINE 索引、search/query(LIKE 全文）/delete/stats 全套。
- 工厂注册：qdrant 无条件注册（httpx 是硬依赖），milvus 惰性注册。
- 组件页接通：`DATASTORE_COMPONENT_IDS` 加入 qdrant/milvus，配置映射（qdrant: url/api_key；milvus: host/port），两者的"测试中"按钮走真实初始化 + health_check；默认记录里的"规划中"文案做了迁移清理。MySQL 保持 TCP 探测 + "未接入"标注。
- **ES（第 4 项）**：本机无 ES 容器且 docker 不可用，改为 mock 单测锁定代码逻辑——连接参数（basic_auth）、dense_vector cosine mapping、knn 查询体、结果解析。
- 测试：`api/tests/test_vector_stores.py` 9 项（Qdrant 4 / Milvus 2 / ES 3，全部 mock 层验证请求构造与结果映射）。全量回归 **519 passed**。
- 诚实边界：Qdrant/Milvus/ES 三个 store 都只在 mock 层验证过，**未经过真实服务器实测**；有条件时起真实实例跑一轮再用于生产。

---

## 10. MySQL store 实现（2026-08-07 追加）

- **`mysql_data_store.py`**（新）：PyMySQL 驱动（纯 Python，惰性 import，缺包报清晰安装提示）。每集合一张 `rag_{collection}` 表：向量存 float32 BLOB、numpy 暴力余弦（与 sqlite 同策略，版本无关）；全文用 `FULLTEXT ... WITH PARSER ngram`（支持中文），建表/查询失败自动降级为普通表 + `LIKE` 回退。CRUD/search/list/get_by_ids/stats/health_check 全套。
- 组件页：mysql 加入 `DATASTORE_COMPONENT_IDS`，配置映射（username→user、port 转 int），"测试连接"走真实初始化 + health_check；默认记录的 role 文案从"不作为检索后端"迁移为如实描述。至此**组件页 6 个组件全部有真实实现**（mysql 的"业务数据库"角色仍是规划，未动）。
- 依赖：requirements 两个文件加 `pymysql>=1.1`。
- 测试：`api/tests/test_mysql_data_store.py` 4 项（ngram 建表、向量检索、MATCH/LIKE 双路径、删除与统计，fake pymysql 验证 SQL 构造与结果映射）。全量回归 **524 passed**。
- 诚实边界：与 Qdrant/Milvus/ES 一样只过 mock 层；MySQL 的 ngram FULLTEXT 需 5.7.6+，老版本自动降级。
