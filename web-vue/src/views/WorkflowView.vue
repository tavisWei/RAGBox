<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { VueFlow, useVueFlow, Handle, Position } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { ElMessage, ElMessageBox } from 'element-plus'
import { appApi, knowledgeBaseApi, modelProviderApi, workflowApi } from '@/api'
import type { KnowledgeBase, ModelProvider } from '@/types'

type WorkflowNodeType = 'start' | 'template' | 'llm' | 'knowledge' | 'condition' | 'variable' | 'http' | 'code' | 'iteration' | 'workflow' | 'merge' | 'tool' | 'approval' | 'answer' | 'end'
type WorkflowEdgeLabel = 'true' | 'false'

interface WorkflowNode {
  id: string
  type: WorkflowNodeType
  title: string
  position: { x: number; y: number }
  data: Record<string, unknown>
  [key: string]: unknown
}

interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  label?: WorkflowEdgeLabel | string
  [key: string]: unknown
}

interface AppItem { id: string; name: string }
interface WorkflowItem { id: string; app_id: string; name: string; description?: string; dsl?: { nodes?: WorkflowNode[]; edges?: WorkflowEdge[] } }

const apps = ref<AppItem[]>([])
const workflows = ref<WorkflowItem[]>([])
const providers = ref<ModelProvider[]>([])
const knowledgeBases = ref<KnowledgeBase[]>([])
const selectedAppId = ref('')
const currentWorkflowId = ref('')
const nodes = ref<WorkflowNode[]>([])
const edges = ref<WorkflowEdge[]>([])
const selectedNodeId = ref('')
const selectedEdgeId = ref('')
const connectSourceId = ref('')
const draggedNodeType = ref<WorkflowNodeType | ''>('')
const canvasRef = ref<HTMLElement | null>(null)
const runInput = ref('请总结这个流程的作用')
const runResult = ref<Record<string, unknown> | null>(null)
const globalVariablesText = ref('{}')
const workflowSettings = ref({ timeout: 60, parallelism: 4, on_error: 'stop' })
const resumeInput = ref('true')
const streamMode = ref(false)
const traceStatusMap = computed(() => {
  const traces = Array.isArray(runResult.value?.traces) ? runResult.value?.traces as Array<Record<string, unknown>> : []
  return Object.fromEntries(traces.map(trace => [String(trace.node_id), String(trace.status || 'succeeded')]))
})
const workflowRuns = ref<Array<Record<string, unknown>>>([])
const workflowVersions = ref<Array<Record<string, unknown>>>([])
const loading = ref(false)
const dialogVisible = ref(false)
const form = ref({ name: '', description: '' })
const nodePalette: Array<{ type: WorkflowNodeType; label: string; desc: string }> = [
  { type: 'start', label: '开始', desc: '输入变量入口' },
  { type: 'template', label: '模板', desc: '拼接变量与提示词' },
  { type: 'llm', label: 'LLM', desc: '调用选定模型' },
  { type: 'knowledge', label: '知识库', desc: '基于知识库问答' },
  { type: 'condition', label: '条件', desc: '输出布尔判断' },
  { type: 'variable', label: '变量', desc: '设置上下文变量' },
  { type: 'http', label: 'HTTP', desc: '调用外部接口' },
  { type: 'code', label: '代码', desc: '执行安全表达式' },
  { type: 'iteration', label: '迭代', desc: '遍历数组生成结果' },
  { type: 'workflow', label: '子工作流', desc: '调用其他工作流' },
  { type: 'merge', label: '合并', desc: '汇总多个分支输出' },
  { type: 'tool', label: '工具', desc: '执行工具模板' },
  { type: 'approval', label: '审批', desc: '等待审批变量' },
  { type: 'answer', label: '回答', desc: '输出可流式回答' },
  { type: 'end', label: '结束', desc: '生成最终答案' },
]
const workflowNodeTypes = new Set<WorkflowNodeType>(nodePalette.map(item => item.type))

const selectedNode = computed(() => nodes.value.find(node => node.id === selectedNodeId.value))
const selectedEdge = computed(() => edges.value.find(edge => edge.id === selectedEdgeId.value))

const selectedWorkflow = computed(() => workflows.value.find(item => item.id === currentWorkflowId.value))
const { onConnect, onNodeDragStop } = useVueFlow()

const validationIssues = computed(() => {
  const issues: string[] = []
  if (!nodes.value.some(node => node.type === 'start')) issues.push('缺少开始节点')
  if (!nodes.value.some(node => node.type === 'end')) issues.push('缺少结束节点')
  for (const node of nodes.value.filter(item => item.type === 'condition')) {
    const outgoing = edges.value.filter(edge => edge.source === node.id)
    if (!outgoing.some(edge => edge.label === 'true')) issues.push(`条件节点 ${node.title} 缺少 true 分支`)
    if (!outgoing.some(edge => edge.label === 'false')) issues.push(`条件节点 ${node.title} 缺少 false 分支`)
    if (outgoing.filter(edge => edge.label === 'true').length > 1) issues.push(`条件节点 ${node.title} true 分支重复`)
    if (outgoing.filter(edge => edge.label === 'false').length > 1) issues.push(`条件节点 ${node.title} false 分支重复`)
  }
  for (const node of nodes.value.filter(item => item.type === 'llm' || item.type === 'knowledge')) {
    if (!node.data.provider || !node.data.model) issues.push(`${node.title} 未配置模型`)
  }
  for (const node of nodes.value.filter(item => item.type === 'end')) {
    if (edges.value.some(edge => edge.source === node.id)) issues.push(`结束节点 ${node.title} 不能有输出连线`)
  }
  const inboundCounts = new Map<string, number>()
  for (const edge of edges.value) {
    inboundCounts.set(edge.target, (inboundCounts.get(edge.target) || 0) + 1)
  }
  for (const node of nodes.value) {
    const inbound = inboundCounts.get(node.id) || 0
    if (inbound > 1 && node.type !== 'merge') issues.push(`${node.title} 存在多入边，建议使用合并节点`) 
  }
  return issues
})

const pausedRun = computed(() => workflowRuns.value.find(run => run.status === 'paused'))

const modelsForProvider = (provider: unknown) => {
  if (typeof provider !== 'string') return []
  return providers.value.find(item => item.provider === provider)?.models || []
}

const nodeTitle = (id: string, data: Record<string, unknown>) => {
  const node = nodes.value.find(item => item.id === id)
  return node?.title || String(data.title || id)
}

const toDsl = () => ({
  nodes: nodes.value.map(node => ({
    id: node.id,
    type: node.type,
    title: node.title,
    position: node.position,
    data: node.data,
  })),
  edges: edges.value.map(edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    ...(edge.sourceHandle ? { sourceHandle: edge.sourceHandle } : {}),
    ...(edge.targetHandle ? { targetHandle: edge.targetHandle } : {}),
    ...(edge.label ? { label: edge.label } : {}),
  })),
  globals: JSON.parse(globalVariablesText.value || '{}'),
  settings: workflowSettings.value,
})

const syncRuntimeGraphFromDsl = (dsl: { nodes?: WorkflowNode[]; edges?: WorkflowEdge[] }) => {
  const safeNodes = (dsl.nodes || [])
    .filter((node: WorkflowNode) => Boolean(node.id) && workflowNodeTypes.has(node.type))
  const safeNodeIds = new Set(safeNodes.map(node => node.id))
  nodes.value = safeNodes.map((node: WorkflowNode) => ({
    id: node.id,
    type: node.type,
    title: node.title || nodePalette.find(item => item.type === node.type)?.label || node.type,
    position: node.position || nextNodePosition(),
    data: {
      ...defaultNodeData(node.type),
      ...(node.data || {}),
      title: node.title || nodePalette.find(item => item.type === node.type)?.label || node.type,
    },
  }))
  edges.value = (dsl.edges || [])
    .filter((edge: WorkflowEdge) => edge.id && safeNodeIds.has(edge.source) && safeNodeIds.has(edge.target))
    .map((edge: WorkflowEdge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      ...(edge.sourceHandle ? { sourceHandle: edge.sourceHandle } : {}),
      ...(edge.targetHandle ? { targetHandle: edge.targetHandle } : {}),
      ...(edge.label ? { label: edge.label } : {}),
    }))
}

const newNodeId = (type: WorkflowNodeType) => `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`

const defaultNodeData = (type: WorkflowNodeType) => {
  if (type === 'start') return { output_key: 'input' }
  if (type === 'template') return { template: '{{input}}', output_key: 'prompt' }
  if (type === 'llm') return { prompt: '{{prompt}}', output_key: 'llm_output', provider: '', model: '', max_tokens: 1024, temperature: 0.7 }
  if (type === 'knowledge') return { query: '{{input}}', output_key: 'knowledge_output', provider: '', model: '', top_k: 5 }
  if (type === 'condition') return { left: '{{input}}', operator: 'not_empty', right: '', output_key: 'condition_result' }
  if (type === 'variable') return { assignments: [{ key: 'variable', value: '{{input}}' }] }
  if (type === 'http') return { url: 'https://example.com', method: 'GET', output_key: 'http_output', timeout: 15 }
  if (type === 'code') return { expression: "context.get('input', '')", output_key: 'code_output' }
  if (type === 'iteration') return { items: '[]', template: '{{item}}', workflow_id: '', output_key: 'iteration_output' }
  if (type === 'workflow') return { workflow_id: '', inputs: '{"input":"{{input}}"}', result_path: '', output_key: 'workflow_output' }
  if (type === 'merge') return { sources: '["llm_output","knowledge_output"]', output_key: 'merge_output' }
  if (type === 'tool') return { tool: 'template', template: '{{input}}', output_key: 'tool_output' }
  if (type === 'approval') return { approval_key: 'approved', output_key: 'approval_output' }
  if (type === 'answer') return { answer: '{{answer}}', output_key: 'answer' }
  return { answer: '{{llm_output}}', output_key: 'answer' }
}

const nextNodePosition = () => {
  const index = nodes.value.length
  return {
    x: 100 + (index % 4) * 220,
    y: 120 + Math.floor(index / 4) * 150,
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const [appRes, providerRes, kbRes] = await Promise.all([
      appApi.list(),
      modelProviderApi.list(),
      knowledgeBaseApi.list(),
    ])
    apps.value = appRes.data
    providers.value = providerRes.data.data
    knowledgeBases.value = kbRes.data
    await fetchWorkflows()
  }
  finally {
    loading.value = false
  }
}

const fetchWorkflows = async () => {
  const response = await workflowApi.list(selectedAppId.value || undefined)
  workflows.value = response.data
  if (!currentWorkflowId.value && workflows.value.length > 0) {
    const first = workflows.value[0]
    if (first)
      await loadWorkflow(first.id)
  }
}

const fetchWorkflowMeta = async () => {
  if (!currentWorkflowId.value) return
  const [runsRes, versionsRes] = await Promise.all([
    workflowApi.runs(currentWorkflowId.value),
    workflowApi.versions(currentWorkflowId.value),
  ])
  workflowRuns.value = runsRes.data
  workflowVersions.value = versionsRes.data
}

const loadWorkflow = async (workflowId: string) => {
  const response = await workflowApi.get(workflowId)
  currentWorkflowId.value = workflowId
  const dsl = response.data.dsl || { nodes: [], edges: [] }
  syncRuntimeGraphFromDsl(dsl)
  globalVariablesText.value = JSON.stringify(dsl.globals || {}, null, 2)
  workflowSettings.value = { timeout: 60, parallelism: 4, on_error: 'stop', ...(dsl.settings || {}) }
  selectedNodeId.value = nodes.value[0]?.id || ''
  selectedEdgeId.value = ''
  runResult.value = null
  await fetchWorkflowMeta()
}

const createWorkflow = async () => {
  if (!selectedAppId.value) {
    ElMessage.warning('请先选择应用')
    return
  }
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入工作流名称')
    return
  }
  const response = await workflowApi.create({
    app_id: selectedAppId.value,
    name: form.value.name,
    description: form.value.description,
  })
  dialogVisible.value = false
  form.value = { name: '', description: '' }
  await fetchWorkflows()
  await loadWorkflow(response.data.id)
  ElMessage.success('工作流已创建')
}

const addNode = (type: WorkflowNodeType, position = nextNodePosition()) => {
  const id = newNodeId(type)
  nodes.value.push({
    id,
    type,
    title: nodePalette.find(item => item.type === type)?.label || type,
    position,
    data: { ...defaultNodeData(type), title: nodePalette.find(item => item.type === type)?.label || type },
  })
  selectedNodeId.value = id
  selectedEdgeId.value = ''
}

const onPaletteDragStart = (event: DragEvent, type: WorkflowNodeType) => {
  draggedNodeType.value = type
  event.dataTransfer?.setData('application/workflow-node', type)
  if (event.dataTransfer)
    event.dataTransfer.effectAllowed = 'copy'
}

const onCanvasDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/workflow-node') || draggedNodeType.value
  if (!type) return
  const rect = canvasRef.value?.getBoundingClientRect()
  addNode(type as WorkflowNodeType, {
    x: rect ? event.clientX - rect.left - 85 : nextNodePosition().x,
    y: rect ? event.clientY - rect.top - 30 : nextNodePosition().y,
  })
  draggedNodeType.value = ''
}

const deleteNode = () => {
  if (!selectedNode.value) return
  const id = selectedNode.value.id
  nodes.value = nodes.value.filter(node => node.id !== id)
  edges.value = edges.value.filter(edge => edge.source !== id && edge.target !== id)
  selectedNodeId.value = nodes.value[0]?.id || ''
  selectedEdgeId.value = ''
}

const syncNodePosition = (nodeId: string, position: { x: number; y: number }) => {
  const node = nodes.value.find(item => item.id === nodeId)
  if (node)
    node.position = { x: position.x, y: position.y }
}

const nextConditionLabel = (sourceId: string, sourceHandle?: string | null) => {
  const sourceNode = nodes.value.find(node => node.id === sourceId)
  if (sourceNode?.type !== 'condition') return undefined
  if (sourceHandle === 'true' || sourceHandle === 'false')
    return sourceHandle
  const labels = edges.value
    .filter(edge => edge.source === sourceId)
    .map(edge => edge.label)
  if (!labels.includes('true')) return 'true'
  if (!labels.includes('false')) return 'false'
  return 'true'
}

const createEdge = (
  source: string,
  target: string,
  sourceHandle?: string | null,
  targetHandle?: string | null,
): WorkflowEdge => ({
  id: `${source}-${target}-${Date.now()}`,
  source,
  target,
  ...(sourceHandle ? { sourceHandle } : {}),
  ...(targetHandle ? { targetHandle } : {}),
  ...(nextConditionLabel(source, sourceHandle) ? { label: nextConditionLabel(source, sourceHandle) } : {}),
})

const updateSelectedNodeTitle = () => {
  if (!selectedNode.value) return
  selectedNode.value.data.title = selectedNode.value.title
}

const connectNode = (nodeId: string) => {
  if (!connectSourceId.value) {
    connectSourceId.value = nodeId
    ElMessage.info('请选择目标节点')
    return
  }
  if (connectSourceId.value === nodeId) {
    connectSourceId.value = ''
    return
  }
  if (!edges.value.some(edge => edge.source === connectSourceId.value && edge.target === nodeId))
    edges.value.push(createEdge(connectSourceId.value, nodeId))
  connectSourceId.value = ''
}

const removeEdge = (edgeId: string) => {
  edges.value = edges.value.filter(edge => edge.id !== edgeId)
  if (selectedEdgeId.value === edgeId)
    selectedEdgeId.value = ''
}

const deleteWorkflow = async () => {
  if (!currentWorkflowId.value || !selectedWorkflow.value) return
  await ElMessageBox.confirm(`确定删除工作流「${selectedWorkflow.value.name}」吗？`, '删除工作流', { type: 'warning' })
  await workflowApi.delete(currentWorkflowId.value)
  ElMessage.success('工作流已删除')
  currentWorkflowId.value = ''
  nodes.value = []
  edges.value = []
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  runResult.value = null
  await fetchWorkflows()
}

const exportWorkflowDsl = async () => {
  if (!currentWorkflowId.value) return
  await navigator.clipboard.writeText(JSON.stringify(toDsl(), null, 2))
  ElMessage.success('工作流 DSL 已复制到剪贴板')
}

const importWorkflowDsl = async () => {
  if (!currentWorkflowId.value) return
  const text = await navigator.clipboard.readText()
  const dsl = JSON.parse(text)
  syncRuntimeGraphFromDsl(dsl)
  globalVariablesText.value = JSON.stringify(dsl.globals || {}, null, 2)
  ElMessage.success('已从剪贴板导入工作流 DSL')
}

const saveWorkflow = async () => {
  if (!currentWorkflowId.value) return
  if (validationIssues.value.length > 0) {
    ElMessage.warning(validationIssues.value[0])
    return
  }
  await workflowApi.update(currentWorkflowId.value, { dsl: toDsl() })
  ElMessage.success('工作流已保存')
  await fetchWorkflows()
  await fetchWorkflowMeta()
}

const runWorkflow = async () => {
  if (!currentWorkflowId.value) return

  const hasLlmOrKnowledge = nodes.value.some(node => node.type === 'llm' || node.type === 'knowledge')

  if (hasLlmOrKnowledge) {
    const missingProviderModel = nodes.value
      .filter(node => node.type === 'llm' || node.type === 'knowledge')
      .filter(node => !node.data.provider || !node.data.model)

    if (missingProviderModel.length > 0) {
      ElMessage.warning('存在 LLM / 知识库节点未配置模型提供商和模型，请先配置')
      return
    }
  }

  await saveWorkflow()
  if (streamMode.value) {
    const token = localStorage.getItem('token') || ''
    const response = await fetch(workflowApi.streamUrl(currentWorkflowId.value), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({ inputs: { input: runInput.value, prompt: runInput.value } }),
    })
    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    runResult.value = { traces: [] }
    while (reader) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      for (const chunk of chunks) {
        const line = chunk.split('\n').find(item => item.startsWith('data: '))
        if (!line) continue
        const payload = JSON.parse(line.replace(/^data:\s*/, ''))
        if (payload.type === 'trace') {
          const traces = Array.isArray(runResult.value?.traces) ? [...(runResult.value?.traces as Array<Record<string, unknown>>), payload.trace] : [payload.trace]
          runResult.value = { ...(runResult.value || {}), traces }
        }
        if (payload.type === 'result') runResult.value = payload.output
      }
    }
    await fetchWorkflowMeta()
    ElMessage.success('流式仿真运行完成')
    return
  }
  const response = await workflowApi.run(currentWorkflowId.value, {
    inputs: { input: runInput.value, prompt: runInput.value },
  })
  runResult.value = response.data.output
  await fetchWorkflowMeta()
  ElMessage.success('仿真运行完成')
}

const resumeWorkflowRun = async () => {
  if (!currentWorkflowId.value || !pausedRun.value) return
  const resumeKey = String((pausedRun.value.traces as Array<Record<string, unknown>> | undefined)?.find(trace => trace.status === 'paused')?.pause_key || 'approved')
  const parsedValue = resumeInput.value.trim().toLowerCase() === 'true'
  const response = await workflowApi.resumeRun(currentWorkflowId.value, String(pausedRun.value.id), {
    inputs: { [resumeKey]: parsedValue },
  })
  runResult.value = {
    run_id: response.data.id,
    status: response.data.status,
    result: response.data.result,
    context: response.data.context,
    traces: response.data.traces,
  }
  await fetchWorkflowMeta()
  ElMessage.success('已恢复审批中的工作流运行')
}

onMounted(fetchData)

watch(selectedAppId, async () => {
  currentWorkflowId.value = ''
  nodes.value = []
  edges.value = []
  await fetchWorkflows()
})

onConnect((connection) => {
  if (!connection.source || !connection.target) return
  const edge = createEdge(
    String(connection.source),
    String(connection.target),
    connection.sourceHandle,
    connection.targetHandle,
  )
  const sourceNode = nodes.value.find(node => node.id === edge.source)
  const duplicatesConditionBranch = sourceNode?.type === 'condition'
    && edges.value.some(item => item.source === edge.source && item.sourceHandle === edge.sourceHandle)
  if (duplicatesConditionBranch) {
    ElMessage.warning('条件节点的 true / false 分支各只能连接一条线')
    return
  }
  if (!edges.value.some(item => item.source === edge.source && item.target === edge.target && item.sourceHandle === edge.sourceHandle)) {
    edges.value.push(edge)
    selectedEdgeId.value = edge.id
    selectedNodeId.value = ''
  }
})

onNodeDragStop(({ node }) => {
  syncNodePosition(node.id, node.position)
})
</script>

<template>
  <div class="workflow-view" v-loading="loading">
    <div class="page-header workflow-header">
      <div>
        <h1 class="page-title">工作流编排</h1>
        <p class="page-subtitle">拖拽节点、连线组装，并通过仿真运行验证流程</p>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedAppId" placeholder="筛选应用" clearable style="width: 200px">
          <el-option v-for="app in apps" :key="app.id" :label="app.name" :value="app.id" />
        </el-select>
        <el-button type="primary" @click="dialogVisible = true">
          <el-icon><Plus /></el-icon>
          创建工作流
        </el-button>
      </div>
    </div>

    <div class="workflow-shell">
      <aside class="workflow-sidebar surface-card">
        <div class="panel-title">工作流</div>
        <div class="workflow-list">
          <button
            v-for="item in workflows"
            :key="item.id"
            type="button"
            class="workflow-item"
            :class="{ active: item.id === currentWorkflowId }"
            @click="loadWorkflow(item.id)"
          >
            <strong>{{ item.name }}</strong>
            <span>{{ item.description || '暂无描述' }}</span>
          </button>
        </div>

        <div class="panel-title mt">节点库</div>
        <button
          v-for="item in nodePalette"
          :key="item.type"
          type="button"
          class="palette-item"
          draggable="true"
          @click="addNode(item.type)"
          @dragstart="onPaletteDragStart($event, item.type)"
        >
          <strong>{{ item.label }}</strong>
          <span>{{ item.desc }}</span>
        </button>
      </aside>

      <main class="workflow-main surface-card">
        <div class="builder-toolbar">
          <div>
            <strong>{{ selectedWorkflow?.name || '请选择或创建工作流' }}</strong>
            <span>{{ nodes.length }} 个节点 · {{ edges.length }} 条连线</span>
          </div>
          <div class="toolbar-actions">
            <el-button :disabled="!currentWorkflowId" @click="saveWorkflow">保存</el-button>
            <el-button :disabled="!currentWorkflowId" @click="exportWorkflowDsl">导出</el-button>
            <el-button :disabled="!currentWorkflowId" @click="importWorkflowDsl">导入</el-button>
            <el-button type="danger" plain :disabled="!currentWorkflowId" @click="deleteWorkflow">删除</el-button>
            <el-button type="primary" :disabled="!currentWorkflowId" @click="runWorkflow">仿真运行</el-button>
          </div>
        </div>

        <div ref="canvasRef" class="canvas-wrap" @dragover.prevent @drop.prevent="onCanvasDrop">
          <VueFlow
            v-model:nodes="nodes"
            v-model:edges="edges"
            fit-view-on-init
            :default-edge-options="{ type: 'smoothstep' }"
            @node-click="({ node }) => { selectedNodeId = node.id; selectedEdgeId = '' }"
            @edge-click="({ edge }) => { selectedEdgeId = edge.id; selectedNodeId = '' }"
          >
            <Background />
            <Controls />
            <template #node-start="{ id, data }">
              <div
                class="workflow-node"
                :class="['start', traceStatusMap[id], { active: selectedNodeId === id, connecting: connectSourceId === id }]"
                @dblclick.stop="connectNode(id)"
              >
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">start</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-template="{ id, data }">
              <div
                class="workflow-node"
                :class="['template', traceStatusMap[id], { active: selectedNodeId === id, connecting: connectSourceId === id }]"
                @dblclick.stop="connectNode(id)"
              >
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">template</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-llm="{ id, data }">
              <div
                class="workflow-node"
                :class="['llm', traceStatusMap[id], { active: selectedNodeId === id, connecting: connectSourceId === id }]"
                @dblclick.stop="connectNode(id)"
              >
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">llm</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-knowledge="{ id, data }">
              <div
                class="workflow-node"
                :class="['knowledge', traceStatusMap[id], { active: selectedNodeId === id, connecting: connectSourceId === id }]"
                @dblclick.stop="connectNode(id)"
              >
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">knowledge</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-condition="{ id, data }">
              <div
                class="workflow-node"
                :class="['condition', traceStatusMap[id], { active: selectedNodeId === id, connecting: connectSourceId === id }]"
                @dblclick.stop="connectNode(id)"
              >
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">condition</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="true" class="condition-handle true" type="source" :position="Position.Right" />
                <Handle id="false" class="condition-handle false" type="source" :position="Position.Right" />
                <span class="branch-label true">true</span>
                <span class="branch-label false">false</span>
              </div>
            </template>
            <template #node-variable="{ id, data }">
              <div class="workflow-node variable" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">variable</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-http="{ id, data }">
              <div class="workflow-node http" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">http</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-code="{ id, data }">
              <div class="workflow-node code" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">code</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-iteration="{ id, data }">
              <div class="workflow-node iteration" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">iteration</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-workflow="{ id, data }">
              <div class="workflow-node workflow" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">workflow</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-merge="{ id, data }">
              <div class="workflow-node merge" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">merge</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-tool="{ id, data }">
              <div class="workflow-node tool" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">tool</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-approval="{ id, data }">
              <div class="workflow-node approval" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">approval</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
                <Handle id="source" type="source" :position="Position.Right" />
              </div>
            </template>
            <template #node-answer="{ id, data }">
              <div class="workflow-node answer" :class="[{ active: selectedNodeId === id, connecting: connectSourceId === id }, traceStatusMap[id]]" @dblclick.stop="connectNode(id)">
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">answer</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
              </div>
            </template>
            <template #node-end="{ id, data }">
              <div
                class="workflow-node"
                :class="['end', traceStatusMap[id], { active: selectedNodeId === id, connecting: connectSourceId === id }]"
                @dblclick.stop="connectNode(id)"
              >
                <Handle id="target" type="target" :position="Position.Left" />
                <div class="node-type">end</div>
                <strong>{{ nodeTitle(id, data) }}</strong>
                <span>{{ id }}</span>
              </div>
            </template>
          </VueFlow>
        </div>
      </main>

      <aside class="config-panel surface-card">
        <template v-if="selectedNode">
          <div class="panel-title">节点配置</div>
          <el-form label-position="top">
            <el-form-item label="标题">
              <el-input v-model="selectedNode.title" @input="updateSelectedNodeTitle" />
            </el-form-item>
            <el-form-item label="输出变量">
              <el-input v-model="selectedNode.data.output_key" />
            </el-form-item>
            <el-form-item label="失败重试次数">
              <el-input-number v-model="selectedNode.data.retry" :min="0" :max="3" />
            </el-form-item>
            <el-form-item v-if="selectedNode.type === 'template'" label="模板">
              <el-input v-model="selectedNode.data.template" type="textarea" :rows="5" />
            </el-form-item>
            <template v-if="selectedNode.type === 'llm'">
              <el-form-item label="提示词">
                <el-input v-model="selectedNode.data.prompt" type="textarea" :rows="5" />
              </el-form-item>
              <el-form-item label="模型提供商">
                <el-select v-model="selectedNode.data.provider" placeholder="选择提供商" clearable @change="selectedNode.data.model = ''">
                  <el-option v-for="provider in providers" :key="provider.provider" :label="provider.label" :value="provider.provider" />
                </el-select>
              </el-form-item>
              <el-form-item label="模型">
                <el-select v-model="selectedNode.data.model" placeholder="选择模型" clearable>
                  <el-option
                    v-for="item in modelsForProvider(selectedNode.data.provider)"
                    :key="item.id"
                    :label="item.name"
                    :value="item.id"
                  />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'knowledge'">
              <el-form-item label="知识库">
                <el-select v-model="selectedNode.data.knowledge_base_id" placeholder="选择知识库" clearable>
                  <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="问题模板">
                <el-input v-model="selectedNode.data.query" type="textarea" :rows="4" />
              </el-form-item>
              <el-form-item label="模型提供商">
                <el-select v-model="selectedNode.data.provider" placeholder="选择提供商" clearable @change="selectedNode.data.model = ''">
                  <el-option v-for="provider in providers" :key="provider.provider" :label="provider.label" :value="provider.provider" />
                </el-select>
              </el-form-item>
              <el-form-item label="模型">
                <el-select v-model="selectedNode.data.model" placeholder="选择模型" clearable>
                  <el-option
                    v-for="item in modelsForProvider(selectedNode.data.provider)"
                    :key="item.id"
                    :label="item.name"
                    :value="item.id"
                  />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'condition'">
              <el-form-item label="左值">
                <el-input v-model="selectedNode.data.left" />
              </el-form-item>
              <el-form-item label="判断方式">
                <el-select v-model="selectedNode.data.operator">
                  <el-option label="包含" value="contains" />
                  <el-option label="等于" value="equals" />
                  <el-option label="不等于" value="not_equals" />
                  <el-option label="非空" value="not_empty" />
                  <el-option label="为空" value="empty" />
                  <el-option label="大于" value="greater_than" />
                  <el-option label="小于" value="less_than" />
                  <el-option label="大于等于" value="greater_or_equal" />
                  <el-option label="小于等于" value="less_or_equal" />
                </el-select>
              </el-form-item>
              <el-form-item label="右值">
                <el-input v-model="selectedNode.data.right" />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'start'">
              <el-form-item label="输入变量 JSON">
                <el-input v-model="selectedNode.data.variables" type="textarea" :rows="4" placeholder='[{"key":"input","type":"string","required":true}]' />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'variable'">
              <el-form-item label="变量赋值 JSON">
                <el-input v-model="selectedNode.data.assignments" type="textarea" :rows="4" placeholder='[{"key":"name","value":"{{input}}"}]' />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'http'">
              <el-form-item label="URL">
                <el-input v-model="selectedNode.data.url" />
              </el-form-item>
              <el-form-item label="方法">
                <el-select v-model="selectedNode.data.method">
                  <el-option label="GET" value="GET" />
                  <el-option label="POST" value="POST" />
                </el-select>
              </el-form-item>
              <el-form-item label="请求体模板">
                <el-input v-model="selectedNode.data.body" type="textarea" :rows="4" />
              </el-form-item>
              <el-form-item label="响应 JSON Path">
                <el-input v-model="selectedNode.data.response_path" placeholder="data.answer" />
              </el-form-item>
              <el-form-item label="认证 Token / Secret 占位符">
                <el-input v-model="selectedNode.data.auth_token" placeholder="{{secret:API_TOKEN}}" />
              </el-form-item>
              <el-form-item label="失败回退值">
                <el-input v-model="selectedNode.data.fallback" />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'code'">
              <el-form-item label="表达式">
                <el-input v-model="selectedNode.data.expression" type="textarea" :rows="4" />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'iteration'">
              <el-form-item label="数组模板">
                <el-input v-model="selectedNode.data.items" />
              </el-form-item>
              <el-form-item label="单项模板">
                <el-input v-model="selectedNode.data.template" />
              </el-form-item>
              <el-form-item label="嵌套工作流">
                <el-select v-model="selectedNode.data.workflow_id" placeholder="可选：为每项调用工作流" clearable>
                  <el-option v-for="wf in workflows.filter(item => item.id !== currentWorkflowId)" :key="wf.id" :label="wf.name" :value="wf.id" />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'workflow'">
              <el-form-item label="子工作流">
                <el-select v-model="selectedNode.data.workflow_id" placeholder="选择工作流" clearable>
                  <el-option v-for="wf in workflows.filter(item => item.id !== currentWorkflowId)" :key="wf.id" :label="wf.name" :value="wf.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="输入映射 JSON">
                <el-input v-model="selectedNode.data.inputs" type="textarea" :rows="4" placeholder='{"input":"{{input}}"}' />
              </el-form-item>
              <el-form-item label="结果变量路径">
                <el-input v-model="selectedNode.data.result_path" placeholder="answer" />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'merge'">
              <el-form-item label="合并来源 JSON">
                <el-input v-model="selectedNode.data.sources" type="textarea" :rows="4" placeholder='["llm_output","knowledge_output"]' />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'tool'">
              <el-form-item label="工具类型">
                <el-input v-model="selectedNode.data.tool" placeholder="template" />
              </el-form-item>
              <el-form-item label="工具模板">
                <el-input v-model="selectedNode.data.template" type="textarea" :rows="4" />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'approval'">
              <el-form-item label="审批变量名">
                <el-input v-model="selectedNode.data.approval_key" placeholder="approved" />
              </el-form-item>
            </template>
            <template v-if="selectedNode.type === 'answer'">
              <el-form-item label="回答模板">
                <el-input v-model="selectedNode.data.answer" type="textarea" :rows="5" />
              </el-form-item>
            </template>
            <el-form-item v-if="selectedNode.type === 'end'" label="最终回答">
              <el-input v-model="selectedNode.data.answer" type="textarea" :rows="5" />
            </el-form-item>
          </el-form>
          <div class="config-actions">
            <el-button @click="connectNode(selectedNode.id)">{{ connectSourceId ? '连到此节点' : '开始连线' }}</el-button>
            <el-button type="danger" plain @click="deleteNode">删除节点</el-button>
          </div>
        </template>
        <template v-else-if="selectedEdge">
          <div class="panel-title">连线配置</div>
          <el-form label-position="top">
            <el-form-item label="标签">
              <el-select v-model="selectedEdge.label" placeholder="选择标签" clearable>
                <el-option label="true" value="true" />
                <el-option label="false" value="false" />
              </el-select>
              <div class="edge-help">条件节点连线使用 true / false 标签决定分支走向；普通连线可留空。</div>
            </el-form-item>
          </el-form>
          <div class="config-actions">
            <el-button type="danger" plain @click="removeEdge(selectedEdge.id)">删除连线</el-button>
          </div>
        </template>
        <el-empty v-else description="选择节点或连线进行配置" />
      </aside>
    </div>

    <div class="simulation-panel surface-card">
      <div class="panel-title">仿真测试</div>
      <el-alert v-if="validationIssues.length" type="warning" :closable="false" show-icon class="validation-alert">
        <template #title>{{ validationIssues[0] }}</template>
      </el-alert>
      <div class="simulation-form">
        <el-input v-model="runInput" placeholder="仿真输入" />
        <el-switch v-model="streamMode" active-text="流式" inactive-text="普通" />
        <el-button type="primary" @click="runWorkflow">运行仿真</el-button>
      </div>
      <div class="simulation-help">LLM / 知识库节点需在节点配置中显式选择模型提供商和模型；无模型节点可直接仿真。</div>
      <el-form label-position="top" class="globals-form">
        <el-form-item label="全局变量 JSON">
          <el-input v-model="globalVariablesText" type="textarea" :rows="4" placeholder='{"apiToken":"demo"}' />
        </el-form-item>
        <el-form-item label="工作流超时（秒）">
          <el-input-number v-model="workflowSettings.timeout" :min="1" :max="300" />
        </el-form-item>
        <el-form-item label="并发批次大小">
          <el-input-number v-model="workflowSettings.parallelism" :min="1" :max="16" />
        </el-form-item>
        <el-form-item label="错误策略">
          <el-select v-model="workflowSettings.on_error">
            <el-option label="停止" value="stop" />
            <el-option label="继续" value="continue" />
          </el-select>
        </el-form-item>
        <el-form-item label="Secrets 提示">
          <el-alert type="info" :closable="false" show-icon title="可在 HTTP/认证等字段中使用 {{secret:API_TOKEN}} 占位符，从环境变量读取密钥。" />
        </el-form-item>
      </el-form>
      <div v-if="pausedRun" class="resume-panel">
        <strong>审批等待中</strong>
        <span>运行 {{ pausedRun.id }} 已暂停，可输入审批值后恢复。</span>
        <div class="resume-actions">
          <el-input v-model="resumeInput" placeholder="true / false" />
          <el-button type="warning" @click="resumeWorkflowRun">恢复运行</el-button>
        </div>
      </div>
      <div v-if="Array.isArray(runResult?.traces)" class="trace-list">
        <div v-for="trace in runResult?.traces as Array<Record<string, unknown>>" :key="String(trace.node_id) + String(trace.started_at)" class="trace-item">
          <strong>{{ trace.title || trace.node_id }}</strong>
          <span>{{ trace.status }}</span>
          <small v-if="trace.error">{{ trace.error }}</small>
        </div>
      </div>
      <pre v-if="runResult" class="result-body">{{ JSON.stringify(runResult, null, 2) }}</pre>
    </div>

    <div class="history-panel surface-card">
      <div class="panel-title">运行历史与版本</div>
      <div class="history-grid">
        <div>
          <strong>最近运行</strong>
          <div v-for="run in workflowRuns.slice().reverse().slice(0, 5)" :key="String(run.id)" class="history-item">
            <span>{{ run.status }}</span>
            <small>{{ run.finished_at || run.updated_at }}</small>
          </div>
          <el-empty v-if="workflowRuns.length === 0" description="暂无运行记录" />
        </div>
        <div>
          <strong>版本历史</strong>
          <div v-for="version in workflowVersions.slice().reverse().slice(0, 5)" :key="String(version.version)" class="history-item">
            <span>v{{ version.version }}</span>
            <small>{{ version.created_at }}</small>
          </div>
          <el-empty v-if="workflowVersions.length === 0" description="暂无历史版本" />
        </div>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="创建工作流" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="工作流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="描述工作流用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createWorkflow">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.workflow-view { padding: var(--page-padding); }
.workflow-header, .header-actions, .builder-toolbar, .simulation-form, .config-actions { display: flex; align-items: center; gap: 12px; }
.workflow-header, .builder-toolbar { justify-content: space-between; }
.workflow-shell { display: grid; grid-template-columns: 240px minmax(0, 1fr) 300px; gap: 16px; min-height: 620px; }
.workflow-sidebar, .workflow-main, .config-panel, .simulation-panel, .history-panel { padding: 16px; }
.panel-title { font-weight: 700; color: var(--color-heading); margin-bottom: 12px; }
.panel-title.mt { margin-top: 24px; }
.workflow-list { display: flex; flex-direction: column; gap: 8px; max-height: 220px; overflow: auto; }
.workflow-item, .palette-item { width: 100%; border: 1px solid var(--color-border); background: var(--color-surface); border-radius: var(--rp-radius-md); padding: 10px; text-align: left; cursor: pointer; }
.workflow-item.active { border-color: var(--rp-primary-500); background: var(--rp-primary-50); }
.workflow-item span, .palette-item span, .builder-toolbar span { display: block; font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.palette-item { margin-bottom: 8px; }
.canvas-wrap { position: relative; min-height: 540px; border: 1px dashed var(--color-border); border-radius: var(--rp-radius-lg); overflow: hidden; background: linear-gradient(90deg, rgba(148,163,184,.12) 1px, transparent 1px), linear-gradient(rgba(148,163,184,.12) 1px, transparent 1px); background-size: 24px 24px; }
.canvas-wrap :deep(.vue-flow) { min-height: 540px; }
.workflow-node { width: 170px; padding: 12px; border: 1px solid var(--color-border); border-radius: var(--rp-radius-lg); background: var(--color-surface); box-shadow: var(--rp-shadow-sm); cursor: move; user-select: none; }
.workflow-node.active { border-color: var(--rp-primary-500); box-shadow: 0 0 0 3px var(--rp-primary-100); }
.workflow-node.connecting { border-color: var(--rp-coral-500); }
.workflow-node.llm { border-left: 4px solid var(--rp-primary-500); }
.workflow-node.knowledge { border-left: 4px solid var(--rp-success-500); }
.workflow-node.condition { border-left: 4px solid var(--rp-warning-500); }
.workflow-node.variable { border-left: 4px solid var(--rp-primary-300); }
.workflow-node.http { border-left: 4px solid var(--rp-success-400); }
.workflow-node.code { border-left: 4px solid var(--rp-warning-400); }
.workflow-node.iteration { border-left: 4px solid var(--rp-coral-400); }
.workflow-node.workflow { border-left: 4px solid var(--rp-primary-400); }
.workflow-node.merge { border-left: 4px solid var(--rp-success-300); }
.workflow-node.tool { border-left: 4px solid var(--rp-warning-300); }
.workflow-node.approval { border-left: 4px solid var(--rp-coral-300); }
.workflow-node.answer { border-left: 4px solid var(--rp-primary-600); }
.workflow-node.end { border-left: 4px solid var(--rp-coral-500); }
.workflow-node.succeeded { box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.25); }
.workflow-node.failed { box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.3); }
.workflow-node.paused { box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.3); }
.workflow-node.fallback { box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3); }
.workflow-node span { display: block; font-size: 11px; color: var(--color-text-tertiary); margin-top: 4px; }
.node-type { font-size: 11px; text-transform: uppercase; color: var(--color-text-secondary); margin-bottom: 4px; }
.canvas-wrap :deep(.vue-flow__edge-path) { stroke: var(--rp-primary-400); stroke-width: 2; }
.canvas-wrap :deep(.vue-flow__handle) { width: 10px; height: 10px; background: var(--rp-primary-500); border: 2px solid var(--color-surface); box-shadow: var(--rp-shadow-sm); }
.workflow-node :deep(.condition-handle.true) { top: 32%; background: var(--rp-success-500); }
.workflow-node :deep(.condition-handle.false) { top: 68%; background: var(--rp-coral-500); }
.branch-label { position: absolute; right: 12px; margin-top: 0; font-size: 10px; font-weight: 700; pointer-events: none; }
.branch-label.true { top: 20%; color: var(--rp-success-600); }
.branch-label.false { top: 56%; color: var(--rp-coral-600); }
.canvas-wrap :deep(.vue-flow__edge-textbg) { fill: var(--color-surface); }
.canvas-wrap :deep(.vue-flow__edge-text) { fill: var(--color-text-primary); font-size: 12px; font-weight: 700; }
.edge-help { margin-top: 6px; font-size: 12px; color: var(--color-text-secondary); line-height: 1.5; }
.simulation-panel { margin-top: 16px; }
.simulation-form { align-items: stretch; }
.simulation-form .el-input { flex: 1; }
.validation-alert { margin-bottom: 12px; }
.simulation-help { margin-top: 8px; font-size: 12px; color: var(--color-text-secondary); }
.resume-panel { display: grid; gap: 8px; margin-top: 12px; padding: 12px; border: 1px solid var(--color-border); border-radius: var(--rp-radius-md); background: var(--color-surface); }
.resume-panel span { color: var(--color-text-secondary); font-size: 13px; }
.resume-actions { display: flex; gap: 10px; align-items: center; }
.resume-actions .el-input { flex: 1; }
.trace-list { display: grid; gap: 8px; margin-top: 12px; }
.trace-item { display: grid; gap: 2px; padding: 10px 12px; border: 1px solid var(--color-border); border-radius: var(--rp-radius-md); background: var(--color-surface); }
.trace-item span { color: var(--color-text-secondary); font-size: 12px; }
.trace-item small { color: var(--rp-coral-600); font-size: 12px; }
.result-body { margin-top: 14px; padding: 14px; background: var(--color-surface-muted); border-radius: var(--rp-radius-md); max-height: 360px; overflow: auto; white-space: pre-wrap; }
.history-panel { margin-top: 16px; }
.history-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.history-item { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--color-border); font-size: 13px; }
.history-item small { color: var(--color-text-secondary); }
@media (max-width: 1200px) { .workflow-shell { grid-template-columns: 1fr; } }
</style>
