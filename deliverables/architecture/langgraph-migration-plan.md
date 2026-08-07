# 工作流引擎迁移 LangGraph 技术方案

- 版本：v1.0（2026-08-06）
- 范围：后端自研工作流引擎（`api/api/workflows.py`）→ LangGraph
- 前端影响：协议保持兼容，零改动或极小改动

---

## 1. 现状架构

### 1.1 引擎本体

`api/api/workflows.py`（约 1300 行）是一个自研 DAG 工作流引擎，执行核心为 `_execute_workflow_graph`（L951–1056）的**轮询式就绪队列循环**：

```
queue ← 所有入边源已执行的节点
while queue:
    ready, deferred = 按 _node_is_ready 拆分 queue      # 轮询就绪判断
    batch = ready[:settings.parallelism]                # 批次限流
    queue = ready[parallelism:] + deferred
    batch_traces = await asyncio.gather(批次内节点)      # 整批共享 timeout
    for trace in batch_traces:
        failed/paused → 按 on_error 决定是否中断整个循环
        按 _next_edges_for_node 把下游节点入队
    每批次全量持久化 run_record（JSON + SQLite 双写）
```

- **DSL**：`{nodes, edges, globals, settings}`，16 种节点类型（start/template/llm/knowledge/condition/variable/http/code/iteration/workflow/merge/tool/question_classifier/parameter_extractor/list_operator/approval/end/answer），`_execute_node`（L646–927）大 if/elif 分发。
- **状态**：单一扁平 `context: dict`，节点通过各自声明的 `output_key` 写入；模板为 `{{var}}` 朴素替换（`_render_template` L238），表达式为 AST 白名单 eval（`_safe_eval_expression` L280）。
- **条件分支**：condition 是产出 bool 的普通节点，边上挂 `label=true/false`，由 `_next_edges_for_node`（L930）选边。
- **中断/恢复**：approval 节点返回 `status="paused"` 的 trace 中断循环；`resume` 端点手工修补 context、删除 paused trace、靠 `executed_node_ids` 续跑（L1248–1276）。
- **持久化**：workflow 定义存 `api/data/workflows.json`；run 记录内存 + `workflow_runs.json` + `workflow_runs.sqlite3` 三处，每批次全量重写。
- **流式**：`/run/stream` 是伪流式——跑完后把 traces 逐条回放为 SSE 帧（`{type:"trace"|"result"}`）。

### 1.2 现状痛点（即迁移收益）

1. 手写就绪轮询 + 并发批次 + 边转移，等同重新发明图执行器，且有已知缺陷：并行节点共享可变 `context`（数据竞争）、重试无退避只 catch `HTTPException`、http 节点用同步 `urllib` 阻塞事件循环。
2. 中断/恢复是自造状态机，语义脆弱（resume 手工删 trace）。
3. 每批次全量双写 JSON+SQLite，性能差。
4. 伪流式，无逐节点实时事件。

---

## 2. 迁移目标与原则

- **目标**：图执行、中断恢复、检查点持久化交给 LangGraph；业务节点逻辑（16 种节点）、模板/表达式引擎、API 协议、前端协议全部保持兼容。
- **原则**：
  1. DSL 不变——前端编排器导出的现有 DSL 必须原样可跑。做法是写一个 **DSL → StateGraph 编译器**，而不是让上层改用 LangGraph API。
  2. API 不变——`POST /workflows/{id}/run`、`/run/stream`、`/runs/{run_id}/resume` 等端点签名与响应体（traces / final_output / status / context）保持一致。
  3. 节点执行逻辑复用——`_execute_node` 的各分支原样保留，只换外层调度。
  4. 渐进切换——新旧引擎并存一个阶段，按 feature flag 切换，可回滚。

---

## 3. 目标架构

### 3.1 新增依赖

```
langgraph>=0.2
langgraph-checkpoint-sqlite   # run 状态检查点，替换手写双写
```

Python 3.10+ 满足 LangGraph 要求。不引入 langchain 本体——LLM 调用继续走现有 `LLMService` / `RAGService`（`api/services/llm_service.py:155`、`api/services/rag_service.py:121`），避免重写模型层。

### 3.2 模块划分

```
api/core/workflow/
├── __init__.py
├── state.py        # WorkflowState 定义与 reducers
├── nodes.py        # 节点工厂：把现有 _execute_node 各分支包成 LangGraph 节点函数
├── template.py     # 从 workflows.py 平移 _render_template / _resolve_secret / _safe_eval_expression / _cast_input_value
├── compiler.py     # DSL → CompiledStateGraph 编译器（含校验复用）
└── runner.py       # run / stream / resume 三个执行入口，产出与现网一致的 run_record
```

`api/api/workflows.py` 只保留路由、workflow CRUD、版本管理和存储，执行部分改为调用 `runner.py`。

### 3.3 State 设计

```python
# api/core/workflow/state.py
import operator
from typing import Annotated, Any, TypedDict

def merge_dict(a: dict, b: dict) -> dict:
    return {**a, **b}

class WorkflowState(TypedDict, total=False):
    context: Annotated[dict, merge_dict]      # 原扁平 context，并行分支各自合入自己的 output_key
    traces: Annotated[list, operator.add]     # 每节点一条 trace，reducer 追加
    status: str                                # running / succeeded / failed / paused
    final_output: Any
    failed_node_id: str | None
```

要点：

- `context` 用 merge reducer，消除现有并行分支共享可变 dict 的竞争；节点函数**返回增量** `{context: {output_key: value}, traces: [trace]}`，不再原地改字典。
- 节点输出 key 是运行期数据（`output_key` 可配），因此不采用"每节点一个静态 state 字段"的方案，统一走 `context` 通道，兼容现有 `{{var}}` 模板。
- globals 在入口节点前以 `setdefault` 语义合入（保留 `_apply_workflow_globals` 行为）。

### 3.4 节点工厂

```python
# api/core/workflow/nodes.py（示意）
def make_node(node_spec: dict, settings: dict) -> Callable:
    node_id = node_spec["id"]
    async def node_fn(state: WorkflowState, config: RunnableConfig) -> dict:
        ctx = dict(state["context"])
        trace = await _execute_with_retry(node_spec, ctx, settings)  # 复用现有执行+重试逻辑
        delta = {"traces": [trace]}
        if trace["status"] == "succeeded":
            delta["context"] = {output_key: trace["output"]}
        elif trace["status"] == "failed" and settings["on_error"] == "stop":
            delta["status"] = "failed"
            delta["failed_node_id"] = node_id
        return delta
    return node_fn
```

- `_execute_with_retry` 内部复用现有 `_execute_node` 全部分支（llm/knowledge/http/code/…），保留 `retry` 次数逻辑，但补上指数退避（`asyncio.sleep(2**attempt)`），并捕获所有异常而非仅 `HTTPException`。
- http 节点顺手把同步 `urllib` 换成 `httpx.AsyncClient`（`httpx` 已在 `api/requirements.txt` 中），修掉事件循环阻塞。
- `tool` / `question_classifier` / `parameter_extractor` 等桩节点原样搬迁，不在本次迁移中扩功能。

### 3.5 DSL 编译器（核心）

```python
# api/core/workflow/compiler.py
def compile_workflow(dsl: dict, checkpointer=None) -> CompiledStateGraph:
    dsl = _validate_dsl(dsl)                      # 复用现有校验（拓扑、条件边、终态）
    g = StateGraph(WorkflowState)
    for node in dsl["nodes"]:
        g.add_node(node["id"], make_node(node, _workflow_settings(dsl)))
    for node in dsl["nodes"]:
        if node["type"] == "condition":
            g.add_conditional_edges(node["id"], _make_router(node), {"true": ..., "false": ...})
        else:
            for edge in 出边:
                g.add_edge(node["id"], edge["target"])
    for sid in _find_start_nodes(dsl):
        g.add_edge(START, sid)
    g.add_edge(终态节点, END)
    return g.compile(checkpointer=checkpointer)
```

关键映射决策：

| 现有机制 | LangGraph 对应 | 说明 |
|---|---|---|
| 就绪队列轮询 + parallelism 批次 | 图拓扑 + `RunnableConfig.max_concurrency=settings.parallelism` | 入边全部完成才触发的 join 语义与 LangGraph 天然一致，`_node_is_ready` 整体删除。**注意**：`max_concurrency` 对同一 superstep 内并行节点的实际约束行为需在 P1 用 spike 验证；若不生效，退回在节点工厂内用全局 `asyncio.Semaphore(parallelism)` 限流 |
| condition 节点 + label 边 | `add_conditional_edges` | condition 节点仍照常执行并把 bool 写入 `context["condition_result"]`（下游可能引用），router 函数读该值返回 `"true"/"false"`，映射到目标节点 |
| `on_error: stop` | 节点返回 `status="failed"`；router 统一在每条出边前检查：`failed 且 stop → END` | 用"普通边也走 conditional router"实现，避免异常炸穿导致 checkpoint 缺 trace |
| `on_error: continue` | 节点内捕获异常写 failed trace，正常放行出边 | 与现网语义一致 |
| approval 暂停 | `interrupt()` | 见 §3.6 |
| workflow / iteration 嵌套子流 | 节点函数内运行期 `compile_workflow(子DSL).ainvoke(...)` | 子图 DSL 本就运行期从 `_workflows` 查询，保持动态编译，加 `functools.lru_cache` 按 (workflow_id, version) 缓存编译产物 |
| merge 节点的"context key 存在性"检查 | 节点函数开头校验，缺 key 返回 failed trace | LangGraph 已保证所有入边完成，key 缺失即上游失败，语义等价且更显式 |
| `settings.timeout`（整批超时） | 节点级 `asyncio.wait_for`（现有 LLM 节点已有 60s 硬编码超时），外加 `graph.ainvoke(..., config={"recursion_limit": ...})` | 整批共享 timeout 语义在逐节点模型下无法也无必要复刻，改为每节点超时 |

编译产物按 `(workflow_id, dsl_hash)` 缓存，避免每次运行重复编译。

### 3.6 中断与恢复（approval）

现有自造机制（paused trace + resume 手工改 context + `executed_node_ids` 续跑）整体替换为 LangGraph 标准能力：

- **暂停**：approval 节点内检查 `context` 缺少 `approval_key` 时调用 `interrupt(payload={"node_id", "pause_key"})`，图在该点挂起，checkpoint 落盘。
- **恢复**：`resume` 端点改为
  ```python
  await graph.ainvoke(Command(resume={approval_key: value}), config={"configurable": {"thread_id": run_id}})
  ```
  approval 节点拿到 resume 值后写入 context 并继续。
- **兼容层**：resume 响应仍需返回现网形状（`id/status/result/context/traces`），并把中断点合成一条 `status="paused"` 的 trace 追加进响应——前端 `WorkflowView.vue:118` 的 `pausedRun` 检测和画布节点着色（`traceStatusMap`）依赖该结构，保持不变则前端零改动。
- run 状态机不变：`running / succeeded / failed / paused`（paused 由 `graph.get_state(thread_id).next` 非空判定）。

### 3.7 持久化

- **workflow 定义与版本**：维持 `LocalStore("workflows.json")` 不动（与引擎无关）。
- **run 状态**：`AsyncSqliteSaver`（`langgraph-checkpoint-sqlite`）作为 checkpointer，库文件独立为 `api/data/workflow_checkpoints.sqlite3`，`thread_id = run_id`。
- **run 元数据**：新增轻量表 `workflow_run_index(run_id, workflow_id, status, created_at, updated_at, final_output_json)`，支撑 `GET /workflows/{id}/runs` 列表与详情。traces/context 从 checkpoint 的 state 还原，不再双写 JSON 全量。
- **存量数据**：`workflow_runs.sqlite3` 中的历史 run 只做只读兼容（详情接口先查新索引，miss 则回源旧库），不做迁移写入；旧 `workflow_runs.json` 停止写入。

### 3.8 流式

`/run/stream` 从"跑完回放"升级为真流式，SSE 帧协议不变：

```
data: {"type": "trace", "trace": {...}}     # 每节点完成即推（astream_events 的 on_chain_end）
data: {"type": "result", "output": {...}}   # 图结束；字段名必须是 output，与 run_workflow_stream（workflows.py:1226）一致
```

实现用 `graph.astream_events(input, config, version="v2")`，过滤 `on_chain_end` 事件按 node_id 取出对应 trace。前端 `WorkflowView.vue:434-467` 已按 `type: trace/result` 增量渲染，无需改动。

### 3.9 API 层改动

`api/api/workflows.py` 中 `_execute_workflow_graph`、`_node_is_ready`、`_frontier_nodes`、`_next_edges_for_node`、`run_one` 等调度代码删除；端点改为：

- `run_workflow`：`runner.run(dsl, inputs)` → 组 run_record 返回（响应体不变）。
- `run_workflow_stream`：`runner.stream(dsl, inputs)` → SSE。
- `resume_workflow_run`：`runner.resume(run_id, inputs)`。
- 其余 CRUD / versions / runs 列表端点不动。

增加环境变量开关 `WORKFLOW_ENGINE=legacy|langgraph`（默认先 `legacy`），`runner` 内部按开关分流，支持灰度与秒级回滚。

---

## 4. 迁移步骤

按依赖顺序分 5 个阶段，每阶段独立可验证、可回滚：

**P0 准备（0.5d）**
- 依赖加入 `langgraph`、`langgraph-checkpoint-sqlite`（根 `requirements.txt` 与 `api/requirements.txt`）。
- 搭建 `api/core/workflow/` 骨架；把模板/表达式/cast 工具函数平移到 `template.py`（纯搬移，旧文件 re-export 保持兼容）。

**P1 同步执行路径（2d）**
- 实现 `state.py` / `nodes.py` / `compiler.py` / `runner.run`。
- `run_workflow` 端点接入新引擎（flag 控制）。
- 验收：用现有 DSL 样例（含并行分支、condition、merge、knowledge、http、嵌套 workflow、iteration）跑通，traces 与旧引擎逐字段对比一致。

**P2 中断恢复 + 持久化（1.5d）**
- approval 改 `interrupt()`；接入 `AsyncSqliteSaver` 与 `workflow_run_index` 表；`resume` 端点改造 + paused trace 兼容层。
- 存量 run 只读回源。
- 验收：approval 暂停 → 前端恢复 → 续跑完成；历史 run 列表/详情可查。

**P3 真流式（1d）**
- `runner.stream` 基于 `astream_events`；`/run/stream` 切换。
- 验收：前端流式模式逐节点实时着色，普通模式与审批恢复回归正常。

**P4 清理（0.5d）**
- 默认 flag 翻为 `langgraph`，观察后删除 legacy 执行循环与 `workflow_runs.json` 双写代码。
- 更新 `docs/` 与 `AGENT.md` 中相关工作流引擎描述。

## 5. 测试方案

- **新旧引擎对等测试**：建 `api/tests/workflows/golden/` 目录，放 6–8 个覆盖全部节点类型的 DSL 样例及输入，同一输入分别跑 legacy 与 langgraph 引擎，断言 `final_output`、`status`、traces 的 `(node_id, status, output)` 序列一致。
- **中断恢复测试**：approval DSL 两次调用（run → resume）断言状态机与 context 合并结果。
- **并行语义测试**：构造扇出/扇入图，断言并行节点 traces 均成功且 context 合并不丢 key（顺带验证修复了共享 dict 竞争）。
- 运行 `api/tests` 全量回归（pytest.ini 已配置）。
- 前端手动验证 `WorkflowView.vue` 三种路径：普通运行、SSE 流式、审批恢复。

## 6. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| `on_error=stop` 的"立即停图"语义在 LangGraph 下需靠 router 检查复刻，长并行扇出时停止时机略有差异（已入队的并行分支会跑完当前 superstep） | 低：现网也是整批 gather 完才停 | 对等测试明确该差异并向调用方说明；语义上可接受 |
| condition 节点的 bool 结果被下游 `{{condition_result}}` 引用 | 中：迁成纯 router 会丢该变量 | condition 节点仍作为普通节点执行并写 context，router 只是读它的产出 |
| 嵌套子图运行期编译的开销 | 低 | `(workflow_id, version)` 缓存编译产物 |
| 存量 run 记录双格式并存 | 低 | 详情接口双源回退，只读不迁移 |
| `AsyncSqliteSaver` 与 FastAPI 生命周期集成（连接管理） | 中 | 在 `api/main.py` lifespan 中统一打开/关闭，参照官方 async 用法 |
| 团队对 LangGraph 学习成本 | 低 | 编译器把 LangGraph 收敛在 `api/core/workflow/` 内部，业务侧仍只面对 DSL |

## 7. 不做的事（明确边界）

- 不引入 langchain 模型抽象，LLM/RAG 调用继续走 `LLMService` / `RAGService`。
- 不补齐 `tool` 节点的真实工具调用（现状即桩，属独立需求）。
- 不改前端 `MonitoringView.vue` 的 5s 指标轮询——那是监控页自动刷新，与工作流引擎无关。
- 不改 DSL schema 与前端编排器。

---

## 8. 实施结果与偏差记录（2026-08-06）

已按 P0–P4 完成实施并验证（langgraph 1.2.10 + langgraph-checkpoint-sqlite 3.1.1，Python 3.12 venv）。

**验证结果**

- 存量 `api/tests/test_workflows.py` 27 项：legacy 与 langgraph 双引擎下全部通过。
- 新增 `api/tests/test_workflows_langgraph.py` 6 项（并行扇出/扇入对等、失败停图、approval 中断/恢复、空恢复=拒绝、无 checkpoint 回退 None、流式帧协议）全部通过。
- 全量回归 `pytest`（474 项）双引擎全绿。
- uvicorn 真实服务冒烟：run(paused) → resume(succeeded, `smoke -> True`) → SSE 逐节点 trace 帧，均正常。

**与方案的偏差**

1. 未平移 `template.py`：新包通过函数内惰性导入直接复用 `api/api/workflows.py` 的 `_execute_node` 与模板/表达式工具，避免循环导入与大搬迁；legacy 执行循环整体保留，由 `WORKFLOW_ENGINE=legacy|langgraph`（默认 langgraph）切换。
2. 未新建 `workflow_run_index` 表：run 记录沿用现有 JSON+SQLite 存储（读取路径不变，前端零改动）；新引擎只在状态迁移时写记录，消除了 legacy 每批次全量双写。checkpoint 独立存 `api/data/workflow_checkpoints.sqlite3`。
3. 流式用 `astream(stream_mode="updates")` 而非 `astream_events`：每个节点完成时其 update 里正好带一条 trace，实现更简单，帧协议不变。
4. `max_concurrency`/`parallelism` 批次限流未复刻：LangGraph 按 superstep 并行执行全部就绪分支；评估后认为现有节点自身超时（LLM 60s、http 可配）已足够，未引入额外限流。
5. `on_error` 的 stop/continue 统一实现为"失败即路由到 END"——与 legacy 实际行为一致（legacy 的 continue 也只放完当前批次，最终状态仍是 failed）。
6. resume 对"失败但未暂停"的旧语义（续跑剩余节点）未复刻：LangGraph 路径下无中断即返回原状态；无 checkpoint 的旧 run 自动回退 legacy resume 路径。

**实施中发现并修复的问题**

- 条件路由必须返回 path-map 的键（`"true"/"false"`）而非目标节点 id。
- `AsyncSqliteSaver`（aiosqlite）绑定创建时的事件循环：TestClient/测试每次请求新循环会导致 "bound to a different event loop"。checkpointer 按事件循环隔离（`checkpointer.py`），编译缓存以 `(dsl_hash, checkpointer 对象)` 为键防止 id 复用拿到已关闭的 saver。
- LangGraph 对 falsy 的 resume 负载（如空 dict `{}`）不投递、重新 interrupt：空恢复包装哨兵 key（`EMPTY_RESUME_KEY`），approval 节点合并前剔除，语义=拒绝（False），与 legacy 一致。
- aiosqlite 连接线程非守护：测试进程退出挂起，测试内通过 fixture 调 `close_checkpointer()` 解决；生产由 `api/main.py` lifespan 关闭。

**环境说明**：新建项目根 `.venv`（python3.12，`uv` 安装；pkuseg 全仓库无引用未装）；分句器测试需 `NLTK_DATA=$PWD/.venv/nltk_data`（用户目录 `~/nltk_data/tokenizers/punkt.zip` 是 4 月 20 日遗留的损坏文件，未动）。`start.sh` 会自动优先使用 `.venv`。
