# 工作流引擎迁移二期计划（终版）：LangGraph / LangChain 各归其位，单引擎一步到位

- 版本：v3.0（2026-08-06，替代 v1.0/v2.0）
- 前置：一期已完成，双引擎共存、默认 langgraph；环境已有 langgraph 1.2.10 + langchain-core 1.5.3
- 本期目标：**按"框架该做的事全部交给框架"重划职责，删除 legacy，LangGraph 成为唯一引擎，一次性收口**

---

## 0. 复查结论（v2.0 为什么不符合要求）

以"LangChain 做 LangChain 的、LangGraph 做 LangGraph 的"逐条复查 v2.0，有三处越界：

1. **节点重试/超时是自研循环**（`nodes.py` 的 `_execute_with_retry` + `asyncio.wait_for`）——LangGraph 1.2 原生支持 `add_node(..., retry_policy=RetryPolicy, timeout=TimeoutPolicy)`，应交给框架。
2. **节点执行逻辑滞留在路由文件里**（`_execute_node` 在 `api/api/workflows.py`，靠惰性导入反哺引擎包，还存在 `_execute_node`→`runner` 的反向调用边）——节点执行是引擎代码，应整体迁入 `api/core/workflow/`，消灭所有惰性导入。
3. **LLM 调用仍走自研 LLMService**——LangChain 的 chat model 抽象（`ChatOpenAI`/`ChatOllama`）才是该做事的；v2.0 只列了方向没落到结构与步骤。

以下维持"自研"的边界不变，理由记录在 §8：RAG/embedding/文档解析、`{{var}}` 模板与表达式沙箱、主聊天链路、run 元数据持久化。

## 1. 职责划分总表（本期验收的唯一标准）

| 职责 | 归属 | 实现 |
|---|---|---|
| 图调度、并行扇出/扇入、条件路由 | LangGraph | `StateGraph` + `add_conditional_edges`（一期已就位） |
| 中断/恢复（approval） | LangGraph | `interrupt()` / `Command(resume=...)`（一期已就位） |
| 执行状态持久化 | LangGraph | `AsyncSqliteSaver` checkpoint（一期已就位） |
| 流式（逐节点） | LangGraph | `astream(stream_mode="updates")`（一期已就位） |
| **节点级重试** | **LangGraph** | `RetryPolicy(max_attempts, backoff_factor=2)`，替换自研循环 |
| **节点级超时** | **LangGraph** | `TimeoutPolicy`，替换自研 `asyncio.wait_for` 批次超时 |
| **LLM 调用（llm 节点）** | **LangChain** | `ChatOpenAI`（openai 及 base_url 兼容供应商）/ `ChatOllama`；demo 供应商保留演示分支 |
| **工具调用（tool 节点）** | **LangChain** | `@tool` 注册表 + `ainvoke`，桩变真功能 |
| DSL 定义/校验/模板/表达式 | 自研 | 前端编排器契约，见 §8 |
| RAG / embedding / 文档解析 | 自研 | 领域系统，见 §8 |
| workflow CRUD / run 元数据 / 鉴权 | 自研 | 应用层职责 |

## 2. 目标代码结构（全覆盖清单）

```
api/services/workflow_store.py      # 新：_workflows/_workflow_runs 存储与持久化（从 workflows.py 搬出，消灭循环依赖根源）
api/core/workflow/
├── dsl.py          # 新：NODE_TYPES、默认 DSL、_validate_dsl 系列、_topological_nodes、_node_data、
│                   #     _node_by_id、_terminal_output_from_traces、_apply_workflow_globals、_workflow_settings
├── template.py     # 新：_render_template、_json_safe、_cast_input_value、_resolve_secret、
│                   #     _safe_eval_expression、_apply_start_inputs、_evaluate_condition、_extract_json_path
├── llm.py          # 新：build_chat_model(resolved, ...) → ChatOpenAI / ChatOllama；provider 映射表
├── tools.py        # 新：TOOL_REGISTRY（calculator / http_get / current_time，@tool 定义）
├── executor.py     # 新：execute_node（原 _execute_node 全部分支；llm 走 llm.py、tool 走 tools.py、
│                   #     子流走 runner.execute）；带系统提示与模型身份提示组装
├── state.py        # 已有，不动
├── nodes.py        # 改：删掉 _execute_with_retry；节点函数只做"执行→增量→failed 标记"，
│                   #     重试/超时由 compiler 挂在节点上；保留 approval 的 interrupt 处理
├── compiler.py     # 改：add_node 带 retry_policy/timeout_policy；直接 import dsl/executor，删惰性导入
├── checkpointer.py # 已有，不动
└── runner.py       # 改：直接 import dsl/executor/store，删惰性导入；resume 删 None 回退（A1 后）
api/api/workflows.py # 只剩：路由、pydantic models、CRUD、版本管理；执行与存储全部移出；
                     # 保留 from ... import 的再导出 shim 兼容存量测试引用
```

**删除**：`_execute_workflow_graph`、`_node_is_ready`、`_frontier_nodes`、`_next_edges_for_node`、`_build_adjacency`、`_build_incoming`、`use_langgraph()`、`WORKFLOW_ENGINE` 开关及全部分支。

**新增依赖**：`langchain-openai`、`langchain-ollama`（与 langchain-core 1.5.x 兼容）。不装 `langchain` 本体（不需要 `init_chat_model`——该函数在 langchain-core 1.5.3 中不存在，直接用 provider 包更准确）。

**前端**：`web-vue/src/views/WorkflowView.vue` tool 节点面板改为从 `GET /workflows/tools` 拉工具列表；删 `api/index.ts:146` 死代码 `runDetail`。其余零改动。

## 3. 关键设计点

### 3.1 重试/超时交给 LangGraph

```python
# compiler.py
attempts = int(data.get("retry", 0) or 0) + 1
builder.add_node(
    node_id,
    make_node(node, settings),
    retry_policy=RetryPolicy(max_attempts=attempts, backoff_factor=2, max_interval=5),
    timeout=TimeoutPolicy(seconds=settings["timeout"]),
)
```

- `RetryPolicy` 只捕获节点抛出的异常并重试；节点函数内部不再自管次数。重试耗尽后的最终异常由节点函数外层 `try/except HTTPException` 转成 failed trace（路由到 END 的现有语义不变）。
- 行为差异（接受并记录）：trace 的 `attempt` 字段不再逐次精确（RetryPolicy 不上报次数），failed trace 记 `attempt = max_attempts`；`settings.timeout` 从"整批共享"变为"每节点"，语义更严但更合理。

### 3.2 LLM 节点（LangChain）

```python
# llm.py
def build_chat_model(resolved, *, max_tokens, temperature, timeout):
    provider = resolved["provider"].lower()
    if provider == "ollama":
        return ChatOllama(model=resolved["model"], base_url=resolved["base_url"] or None, ...)
    # openai 及一切 base_url 兼容供应商（现状 LLMService 的实际覆盖范围）
    return ChatOpenAI(model=..., api_key=..., base_url=..., max_tokens=..., temperature=..., timeout=...)
```

- `_resolve_model` 复用；`demo` 供应商走 executor 内的演示分支（对齐 `_chat_demo` 现有输出），不进 LangChain。
- **行为兼容点**：`with_model_identity_config` 追加的模型身份提示必须在组装 system_prompt 时保留，测试加断言盯住。
- 未识别的 provider → 抛错转 failed trace（不静默回退）。

### 3.3 tool 节点真实化（LangChain）

- `tool="template"`：保持模板渲染（兼容现网 DSL）。
- 其他名字查 `TOOL_REGISTRY`，`@tool` 定义 + `ainvoke`；未注册 → failed trace 并提示可用工具名。
- 初始工具：`calculator`（复用 `_safe_eval_expression` 沙箱）、`http_get`（httpx）、`current_time`。
- 新端点 `GET /workflows/tools` 返回 `[{name, description, args_schema}]`。

### 3.4 嵌套子流

iteration（workflows.py 现 :758）/ workflow（:780）两处改调 `runner.execute(sub_dsl, child_context, run_id=uuid4())`；返回形状与 legacy 一致，状态判断逻辑零改动。子流查表改走 `workflow_store`。approval 子流"暂停即 None 继续"的怪癖语义保留并记录。

## 4. 存量数据处理（删 legacy 前置）

1. 扫描 `api/data/workflow_runs.sqlite3` 与 `workflow_runs.json` 中 `status='paused'` 的 run。
2. 处置：量少人工审批至终态；需保留痕迹的脚本置 `failed`（不迁 checkpoint）。
3. 清零后删 `resume` 回退分支；`runner.resume` 无 checkpoint 直接返回 409 风格错误。

## 5. 测试迁移全覆盖表

`api/tests/test_workflows.py` + `test_workflows_langgraph.py` 逐条去向：

| 测试 | 处置 |
|---|---|
| 端点类（run/stream/resume/CRUD/版本/多审批等 12 个） | 不动——shim 保证 import 不变 |
| `_validate_dsl` 直接调用类（4 个） | 不动（shim 再导出） |
| `_execute_node` 直接调用类（8 个） | import 改指 executor（或继续用 shim）；monkeypatch 目标改 `api.core.workflow.executor` |
| `_execute_workflow_graph` 直接调用类（5 个） | 改打 `runner.execute` + golden 断言 |
| `test_llm_node_*`（2 个） | monkeypatch 改 `build_chat_model`；身份提示断言保留 |
| http 节点 urlopen monkeypatch（3 个） | 不动（patch 的是全局 `urllib.request` 属性，与 import 位置无关） |
| 对等测试 2 处 legacy 调用 | 改 golden 字面量 |
| 新增 | build_chat_model 映射测试；tool 三工具 + 未注册 failed；GET /workflows/tools；RetryPolicy 重试次数测试 |

## 6. 执行步骤与验收门禁

每步完成后必须过门禁才走下一步；任何一步红了就停在该步修。

- **A0 前端基线**：按 §3（v2.0 矩阵，见下）手动/自动验证现状全绿。门禁：10 项矩阵通过。
- **A1 存量清零**：§4 扫描→处置→确认。门禁：paused 扫描结果为空；处置记录留档。
- **A2 模块搬迁**（workflow_store / dsl / template / executor 纯搬移 + shim，不改逻辑）。门禁：`pytest -q` 全绿（双引擎仍在）；`grep -n "_execute_node\|_validate_dsl" api/api/workflows.py` 仅剩 shim。
- **A3 嵌套子流** → runner.execute。门禁：全量绿；子流两个改造测试通过。
- **A4 LLM 节点 → LangChain**（装依赖 + llm.py + executor 改 + 测试改）。门禁：全量绿；一个真实供应商手动跑通 LLM 节点。
- **A5 tool 真实化 + /workflows/tools + 前端面板**。门禁：新增测试绿；前端面板手动验证。
- **A6 删 legacy + RetryPolicy/TimeoutPolicy 化 + resume 回退删除**。门禁：全量绿（无开关）；`grep -rn "_execute_workflow_graph\|WORKFLOW_ENGINE\|_node_is_ready" api/ web-vue/src` 为零。
- **A7 单引擎前端回归 + uvicorn 冒烟**（run→paused→resume→stream 四连）。
- **A8 文档**：两期计划文档标记完成、`docs/development-guide.md` 更新引擎描述、删 `runDetail`。

## 7. 前端验证矩阵（A0/A7 共用）

触点已核实仅 `api/index.ts:138-149` + `WorkflowView.vue`：列表/新建/加载/保存(校验+版本)/删除/历史/同步运行/流式运行/审批恢复/画布编辑校验，共 10 项；`MonitoringView.vue` 轮询与引擎无关。流式运行与审批恢复两项必须手动过，其余自动化覆盖。

## 8. 非目标与理由（明确不交给框架的部分）

- **RAG/embedding/文档解析不迁 LangChain**：自研检索体系（sqlite store、多路检索、rerank、关键词表）没有对应的 LangChain 直接等价物，重写只有回归风险没有功能收益。knowledge 节点继续走 `RAGService`。
- **`{{var}}` 模板与表达式沙箱不迁**：是 DSL 对前端的契约，PromptTemplate 语义不等价。
- **主聊天链路 5 处 `LLMService` 消费方不动**：超出工作流引擎边界；如要统一，另立三期。
- **http 节点保留 urllib**：现有测试 seam 依赖；阻塞问题记录在案，不在本期扩 scope。

## 9. 风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| 无引擎开关后回滚靠 git revert | 中 | A0/A7 双轮前端验证；二期开始前打 tag |
| RetryPolicy/TimeoutPolicy 与自研语义差异 | 中 | A6 用现有失败/重试测试盯住；attempt 字段差异已记录 |
| LangChain 模型封装行为差异（身份提示、错误格式、超时） | 中 | §3.2 兼容点 + fake model 测试 + 真实供应商手动验证 |
| 模块搬迁引入 import 回归 | 低 | A2 纯搬移独立成步，门禁即全量测试 |
| 存量 paused run 处置 | 中 | A1 先扫描后动手 |

---

## 10. 实施结果（2026-08-06，已全部完成）

**验证**

- 全量回归 479 passed（单一 LangGraph 引擎，无引擎开关）。
- uvicorn 冒烟：`/workflows/tools` 返回三工具；run→paused→resume→`succeeded`；SSE 逐节点实时帧 + result 帧，calculator 工具真实计算（6*7=42）。
- 前端 `vue-tsc --build` 类型检查通过。
- A1 存量扫描：sqlite 与 JSON 中 paused run 均为 0，天然清零，无需处置。

**实施偏差（相对 §3/§6）**

1. **重试耗尽路径**：`RetryPolicy` 只在异常抛出时生效，因此节点函数把 `HTTPException` 包成 `NodeExecutionError` 抛出，由 runner 捕获后组装 legacy 形状的 failed trace（`runner.execute`/`resume`）。非 HTTPException 异常保持原有"直接 500"语义。
2. **节点超时**：用 `add_node(..., timeout=float(settings.timeout))`（langgraph 1.2 支持直接传 float，未用 `TimeoutPolicy` 类）。
3. **demo 供应商**：未走 LangChain，保留 `LLMService` 的演示应答路径（演示内容单一来源，避免复制）。
4. **checkpointer 退出清理**：aiosqlite worker 用 `call_soon_threadsafe` 完成 future，因此新增 `close_all_checkpointers()`——跨事件循环的连接在线程内以一次性 loop 关闭；测试 fixture 与 lifespan 使用。
5. **嵌套子流**：`executor._run_subflow` 保留一个函数级惰性 import（executor→runner→compiler→nodes→executor 是真实递归环），已注释说明。
6. **存量测试修复 1 处**：`test_import_error_sets_none_encoding` 原来 patch 模块属性对局部 `import tiktoken` 无效（只在 tiktoken 未安装时偶然通过），改为 `sys.modules["tiktoken"] = None` 的标准做法。与引擎无关，因 venv 补齐 tiktoken 而暴露。
7. `test_llm_node_*`/`test_knowledge_node_*` 的 monkeypatch 目标按计划迁至 `executor` 模块；`_execute_workflow_graph` 直调测试改为打 `runner.execute` + golden 断言。

**终态确认**：`grep -rn "_execute_workflow_graph\|WORKFLOW_ENGINE\|_node_is_ready" api/ web-vue/src` 无残留；legacy 调度循环、引擎开关、resume 回退分支均已删除。
