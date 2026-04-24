<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { knowledgeBaseApi, modelProviderApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'
import type { ModelProvider, RagPlanPreset } from '@/types'

const route = useRoute()
const kb = ref<any>(null)
const documents = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const form = ref({
  name: '',
  content: '',
})
const splitterForm = ref({
  type: 'recursive',
  chunk_size: 500,
  chunk_overlap: 100,
})
const hardwareTier = ref('medium')
const ragPlan = ref('medium')
const ragPlans = ref<RagPlanPreset[]>([])
const providers = ref<ModelProvider[]>([])
const retrievalForm = ref({
  methods: ['hybrid'],
  top_k: 10,
  fusion_mode: 'rrf',
  query_expansion: 'none',
  rerank_mode: 'none',
})
const hitTestForm = ref({
  query: '',
  top_k: 5,
  provider: '',
  model: '',
})
const hitTestResult = ref<any>(null)

const currentModels = computed(() => {
  const current = providers.value.find(item => item.provider === hitTestForm.value.provider)
  return current?.models || []
})

const onHitProviderChange = () => {
  hitTestForm.value.model = ''
}

const documentItems = computed(() => documents.value)
const {
  currentPage,
  total,
  paginatedItems: paginatedDocuments,
  shouldPaginate,
  resetPagination,
} = useClientPagination(documentItems, 10)

const kbId = route.params.id as string

const selectedPlan = () => ragPlans.value.find(plan => plan.key === ragPlan.value)

const backendLabel = (backend?: string) => {
  if (backend === 'sqlite') return 'SQLite 本地轻量'
  if (backend === 'pgvector') return 'PostgreSQL + pgvector'
  if (backend === 'elasticsearch') return 'Elasticsearch 集群'
  return backend || '-'
}

const vectorLabel = (backend?: string) => {
  if (backend === 'sqlite-builtin') return 'SQLite BLOB 本地向量替代'
  if (backend === 'pgvector') return 'pgvector HNSW/向量索引'
  if (backend === 'elasticsearch-dense-vector') return 'Elasticsearch dense_vector'
  return backend || '-'
}

const splitterTypeOptions = [
  { label: '递归分块（通用推荐）', value: 'recursive', tip: '优先按段落、标题、换行拆分，适合大多数文档。' },
  { label: '按 Token 分块', value: 'token', tip: '按模型 Token 数量切分，适合精确控制上下文成本。' },
  { label: '按句子分块', value: 'sentence', tip: '按自然句子切分，适合问答、说明文。' },
  { label: 'Markdown 结构分块', value: 'markdown', tip: '按标题层级切分，适合 Markdown 文档。' },
  { label: '代码结构分块', value: 'code', tip: '按函数、类、代码块切分，适合源码知识库。' },
  { label: '语义分块', value: 'semantic', tip: '根据语义变化切分，适合复杂长文档，但成本更高。' },
  { label: '父子分块', value: 'parent_child', tip: '小块检索、大块回传，兼顾召回率和上下文完整性。' },
]

const retrievalMethodOptions = [
  { label: '语义检索', value: 'semantic', tip: '按语义相似度查找，适合理解类问题。' },
  { label: '全文检索', value: 'fulltext', tip: '按关键词全文匹配，适合查具体词句。' },
  { label: '关键词检索', value: 'keyword', tip: '适合术语、编号、专有名词。' },
  { label: '混合检索', value: 'hybrid', tip: '综合语义+全文，通常是更稳妥的默认方案。' },
]

const fusionOptions = [
  { label: 'RRF 融合（推荐）', value: 'rrf', tip: '把多路检索结果按排名融合，稳健且通用。' },
  { label: '加权融合', value: 'weighted', tip: '给不同检索方式分配权重，适合做精细调优。' },
  { label: '简单融合', value: 'simple', tip: '简单合并结果，适合轻量场景。' },
]

const expansionOptions = [
  { label: '不扩展', value: 'none', tip: '直接按原问题检索，成本最低。' },
  { label: '多查询扩展', value: 'multi_query', tip: '自动改写多个相近问题，提高召回率。' },
  { label: 'HyDE 假设答案扩展', value: 'hyde', tip: '先生成假设答案再检索，召回更强，但成本更高。' },
]

const rerankOptions = [
  { label: '不重排', value: 'none', tip: '速度快，成本低。' },
  { label: 'Cross-Encoder 重排', value: 'cross_encoder', tip: '对候选结果再次精排，质量高，成本中等。' },
  { label: 'LLM 列表式重排', value: 'llm_listwise', tip: '用大模型整体比较候选结果，效果强但成本最高。' },
]

const applyTierPreset = (tier: string) => {
  const plan = ragPlans.value.find(item => item.key === tier)
  if (!plan) return
  ragPlan.value = plan.key
  hardwareTier.value = plan.hardware_tier
  splitterForm.value = { ...plan.splitter_config } as any
  retrievalForm.value = { ...plan.retrieval_config } as any
}

const fetchDetail = async () => {
  loading.value = true
  try {
    const [kbRes, docsRes, planRes] = await Promise.all([
      knowledgeBaseApi.get(kbId),
      knowledgeBaseApi.listDocuments(kbId),
      knowledgeBaseApi.getRagPlans(),
    ])
    const providerRes = await modelProviderApi.list()
    ragPlans.value = planRes.data.data || []
    providers.value = providerRes.data.data || []
    kb.value = kbRes.data
    documents.value = docsRes.data.data || []
    hardwareTier.value = kbRes.data.hardware_tier || 'medium'
    ragPlan.value = kbRes.data.rag_plan || kbRes.data.hardware_tier || 'medium'
    splitterForm.value = kbRes.data.splitter_config || splitterForm.value
    retrievalForm.value = kbRes.data.retrieval_config || retrievalForm.value
  }
  finally {
    loading.value = false
  }
}

const addDocument = async () => {
  try {
    await knowledgeBaseApi.addDocument(kbId, form.value.content, { name: form.value.name })
    ElMessage.success('文档添加成功')
    dialogVisible.value = false
    form.value = { name: '', content: '' }
    await fetchDetail()
  }
  catch {
    ElMessage.error('文档添加失败')
  }
}

const uploadTextFile = async (uploadFile: any) => {
  const file = uploadFile.raw as File
  try {
    await knowledgeBaseApi.uploadDocument(kbId, file)
    ElMessage.success('文件上传成功')
    await fetchDetail()
  }
  catch {
    const lowerName = file.name.toLowerCase()
    const isTextLike = ['.txt', '.md', '.markdown', '.html', '.htm'].some(ext => lowerName.endsWith(ext))
    if (!isTextLike) {
      ElMessage.error('该文件上传失败。PDF/Word 请确认后端依赖已安装；.doc 请先转换为 .docx。')
      return false
    }
    const text = await file.text()
    form.value.name = file.name
    form.value.content = text
    dialogVisible.value = true
    ElMessage.warning('已回退到文本导入模式')
  }
  return false
}

const deleteDocument = async (documentId: string) => {
  await knowledgeBaseApi.deleteDocument(kbId, documentId)
  ElMessage.success('文档删除成功')
  await fetchDetail()
}

const saveConfig = async () => {
  await knowledgeBaseApi.update(kbId, {
    rag_plan: ragPlan.value,
    hardware_tier: hardwareTier.value,
    splitter_config: splitterForm.value,
    retrieval_config: retrievalForm.value,
  })
  ElMessage.success('RAG 方案已保存；如已有文档，索引需重建后完全生效')
  await fetchDetail()
}

const runHitTest = async () => {
  if (!hitTestForm.value.provider) {
    ElMessage.warning('请选择模型提供商或先添加供应商')
    return
  }
  if (!hitTestForm.value.model) {
    ElMessage.warning('请选择要调用的模型')
    return
  }
  const response = await knowledgeBaseApi.hitTest(kbId, hitTestForm.value)
  hitTestResult.value = response.data
  ElMessage.success('检索测试完成')
}

onMounted(() => {
  fetchDetail()
})

watch(documentItems, () => {
  resetPagination()
})
</script>

<template>
  <div class="kb-detail" v-loading="loading">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-left">
        <div class="breadcrumb">
          <span class="breadcrumb-link" @click="$router.push('/knowledge-bases')">知识库</span>
          <el-icon size="12" class="breadcrumb-sep"><ArrowRight /></el-icon>
          <span class="breadcrumb-current">{{ kb?.name || '详情' }}</span>
        </div>
        <h1 class="page-title">{{ kb?.name || '知识库详情' }}</h1>
        <p class="page-desc">{{ kb?.description || '暂无描述' }}</p>
      </div>
      <div class="header-actions">
        <el-upload
          :show-file-list="false"
          accept=".txt,.md,.markdown,.html,.htm,.pdf,.doc,.docx"
          :auto-upload="false"
          :on-change="uploadTextFile"
        >
          <el-button>
            <el-icon><Upload /></el-icon>
            上传文件
          </el-button>
        </el-upload>
        <el-button type="primary" @click="dialogVisible = true">
          <el-icon><Plus /></el-icon>
          新增文档
        </el-button>
      </div>
    </div>

    <!-- Alert -->
    <el-alert
      v-if="kb?.reindex_required"
      class="mb-lg"
      type="warning"
      :closable="false"
      show-icon
      title="当前 RAG 方案已变更，已有文档需要重建索引后才能完全按新方案生效；当前版本不会自动重建索引，请重新导入文档或等待后续重建任务能力。"
    />

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="stat-card surface-card">
        <div class="stat-icon blue">
          <el-icon size="20"><Connection /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-label">Embedding</div>
          <div class="stat-value small">{{ kb?.embedding_provider || '-' }} / {{ kb?.embedding_model || '-' }}</div>
        </div>
      </div>
      <div class="stat-card surface-card">
        <div class="stat-icon green">
          <el-icon size="20"><Document /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-label">文档数量</div>
          <div class="stat-value">{{ kb?.document_count || 0 }}</div>
        </div>
      </div>
      <div class="stat-card surface-card">
        <div class="stat-icon purple">
          <el-icon size="20"><Cpu /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-label">RAG 方案</div>
          <div class="stat-value small">{{ selectedPlan()?.name || '均衡生产方案' }}</div>
        </div>
      </div>
      <div class="stat-card surface-card">
        <div class="stat-icon orange">
          <el-icon size="20"><DataLine /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-label">推荐检索后端</div>
          <div class="stat-value small">{{ backendLabel(kb?.recommended_backend) }}</div>
        </div>
      </div>
    </div>

    <div class="runtime-arch surface-card">
      <div class="runtime-arch-item">
        <span class="runtime-label">RAG 架构</span>
        <strong>{{ kb?.rag_architecture || selectedPlan()?.architecture || '-' }}</strong>
      </div>
      <div class="runtime-arch-item">
        <span class="runtime-label">向量能力</span>
        <strong>{{ vectorLabel(kb?.vector_backend || selectedPlan()?.vector_backend) }}</strong>
      </div>
      <div class="runtime-note">MySQL 适合作为业务数据库；知识库检索后端使用 SQLite/pgvector/Elasticsearch 等检索存储。</div>
    </div>

    <!-- RAG Plan Selection -->
    <div class="surface-card section-card">
      <div class="section-header">
        <div class="section-title">
          <el-icon size="18" class="text-accent"><Setting /></el-icon>
          <span>RAG 成本 / 性能方案</span>
        </div>
      </div>

      <div class="plan-grid">
        <button
          v-for="plan in ragPlans"
          :key="plan.key"
          type="button"
          class="plan-card"
          :class="{ active: plan.key === ragPlan }"
          @click="applyTierPreset(plan.key)"
        >
          <div class="plan-card__head">
            <strong>{{ plan.name }}</strong>
            <el-tag size="small" :type="plan.key === 'low' ? 'success' : plan.key === 'high' ? 'warning' : 'primary'">
              {{ plan.cost_level }}成本
            </el-tag>
          </div>
          <p>{{ plan.summary }}</p>
          <div class="plan-card__meta">
            <span>{{ plan.quality_level }} · top_k {{ plan.retrieval_config.top_k }}</span>
            <span>{{ backendLabel(plan.recommended_backend) }}</span>
          </div>
          <em>{{ plan.architecture || plan.datastore_note }}</em>
        </button>
      </div>

      <div class="tier-tip">
        <el-icon size="14"><InfoFilled /></el-icon>
        <span>切换方案会带入对应的分块、检索、查询扩展和重排配置；已有文档需要重建索引后完全生效。轻量起步可单机运行，团队标准推荐 pgvector，企业增强推荐 Elasticsearch/专用向量库。</span>
      </div>
    </div>

    <!-- Documents Section -->
    <div class="surface-card section-card">
      <div class="section-header">
        <div class="section-title">
          <el-icon size="18" class="text-accent"><Document /></el-icon>
          <span>文档列表</span>
        </div>
        <div class="section-count">{{ documents.length }} 个文档</div>
      </div>

      <div v-if="documents.length === 0" class="empty-state">
        <div class="empty-icon">
          <el-icon size="40" color="var(--color-text-tertiary)"><Document /></el-icon>
        </div>
        <div class="empty-title">还没有文档</div>
        <div class="empty-desc">上传文件或手动添加文本内容</div>
        <div class="empty-actions">
          <el-upload
            :show-file-list="false"
            accept=".txt,.md,.markdown,.html,.htm,.pdf,.doc,.docx"
            :auto-upload="false"
            :on-change="uploadTextFile"
          >
            <el-button>
              <el-icon><Upload /></el-icon>
              上传文件
            </el-button>
          </el-upload>
          <el-button type="primary" @click="dialogVisible = true">
            <el-icon><Plus /></el-icon>
            手动添加
          </el-button>
        </div>
      </div>

      <div v-else class="doc-list">
        <div
          v-for="doc in paginatedDocuments"
          :key="doc.id"
          class="doc-item"
        >
          <div class="doc-item-icon">
            <el-icon size="18"><Document /></el-icon>
          </div>
          <div class="doc-item-info">
            <div class="doc-item-name">{{ doc.name }}</div>
            <div class="doc-item-preview">{{ doc.content_preview || '暂无预览' }}</div>
          </div>
          <div class="doc-item-meta">
            <el-tag size="small" effect="light">{{ doc.chunks }} 分块</el-tag>
            <el-button
              type="danger"
              size="small"
              text
              @click="deleteDocument(doc.id)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <div v-if="shouldPaginate" class="page-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :total="total"
          :page-size="10"
          background
          layout="prev, pager, next"
          :hide-on-single-page="true"
        />
      </div>
    </div>

    <!-- Config Grid -->
    <div class="config-grid">
      <!-- Splitter Config -->
      <div class="surface-card section-card">
        <div class="section-header">
          <div class="section-title">
            <el-icon size="18" class="text-accent"><Scissor /></el-icon>
            <span>分词 / 切块策略</span>
          </div>
        </div>

        <el-form label-width="120px">
          <el-form-item label="策略类型">
            <el-select v-model="splitterForm.type" style="width: 100%">
              <el-option
                v-for="item in splitterTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="field-tip">{{ splitterTypeOptions.find(item => item.value === splitterForm.type)?.tip }}</div>
          </el-form-item>
          <el-form-item label="分块大小">
            <el-input-number v-model="splitterForm.chunk_size" :min="50" :step="50" />
            <div class="field-tip">单个分块的大致大小。越大上下文越完整，但成本越高。</div>
          </el-form-item>
          <el-form-item label="分块重叠">
            <el-input-number v-model="splitterForm.chunk_overlap" :min="0" :step="10" />
            <div class="field-tip">相邻分块保留的重复内容，能减少切分边界的信息丢失。</div>
          </el-form-item>
        </el-form>
      </div>

      <!-- Retrieval Config -->
      <div class="surface-card section-card">
        <div class="section-header">
          <div class="section-title">
            <el-icon size="18" class="text-accent"><Search /></el-icon>
            <span>检索策略</span>
          </div>
        </div>

        <el-form label-width="120px">
          <el-form-item label="检索方式">
            <el-select v-model="retrievalForm.methods" multiple style="width: 100%">
              <el-option
                v-for="item in retrievalMethodOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="field-tip">语义检索适合理解问题，全文/关键词适合精确词句，混合检索通常最稳。</div>
          </el-form-item>
          <el-form-item label="召回数量">
            <el-input-number v-model="retrievalForm.top_k" :min="1" :max="50" />
            <div class="field-tip">先召回多少条候选内容。越大越容易召回正确结果，但更耗资源。</div>
          </el-form-item>
          <el-form-item label="融合方式">
            <el-select v-model="retrievalForm.fusion_mode" style="width: 100%">
              <el-option
                v-for="item in fusionOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="field-tip">把多种检索结果合并的方式。RRF 一般最稳，Weighted 适合高配调优。</div>
          </el-form-item>
          <el-form-item label="查询扩展">
            <el-select v-model="retrievalForm.query_expansion" style="width: 100%">
              <el-option
                v-for="item in expansionOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="field-tip">把一个问题扩展成多个检索表达。Multi Query 更稳，HyDE 更强但更耗资源。</div>
          </el-form-item>
          <el-form-item label="结果重排">
            <el-select v-model="retrievalForm.rerank_mode" style="width: 100%">
              <el-option
                v-for="item in rerankOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="field-tip">对召回结果再次精排。Cross-Encoder 更均衡，LLM 列表式重排效果强但成本最高。</div>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- Save Config -->
    <div class="config-actions">
      <el-button type="primary" size="large" @click="saveConfig">
        <el-icon><Check /></el-icon>
        保存 RAG 方案
      </el-button>
    </div>

    <!-- Hit Test -->
    <div class="surface-card section-card">
      <div class="section-header">
        <div class="section-title">
          <el-icon size="18" class="text-accent"><Aim /></el-icon>
          <span>检索测试 / Hit Testing</span>
        </div>
      </div>

      <el-form label-width="100px">
        <el-form-item label="测试问题">
          <el-input
            v-model="hitTestForm.query"
            type="textarea"
            :rows="3"
            placeholder="输入一个问题，测试知识库的检索效果..."
          />
        </el-form-item>
        <el-form-item label="召回数量">
          <el-input-number v-model="hitTestForm.top_k" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="模型提供商">
          <el-select v-model="hitTestForm.provider" placeholder="选择模型提供商" clearable style="width: 100%" @change="onHitProviderChange">
            <el-option v-for="provider in providers" :key="provider.provider" :label="provider.label" :value="provider.provider" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="hitTestForm.model" placeholder="选择模型" clearable style="width: 100%">
            <el-option v-for="item in currentModels" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runHitTest">
            <el-icon><Aim /></el-icon>
            执行测试
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="hitTestResult" class="hit-test-result">
        <div class="result-block">
          <div class="result-header">
            <el-icon size="16" class="text-success"><ChatDotRound /></el-icon>
            <span>回答</span>
          </div>
          <pre>{{ hitTestResult.answer }}</pre>
        </div>
        <div class="result-block">
          <div class="result-header">
            <el-icon size="16" class="text-accent"><Document /></el-icon>
            <span>命中文档</span>
          </div>
          <el-table :data="hitTestResult.sources || []" size="small">
            <el-table-column prop="score" label="分数" width="100" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
          </el-table>
        </div>
      </div>
    </div>

    <!-- Add Document Dialog -->
    <el-dialog v-model="dialogVisible" title="新增文档" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="文档名称">
          <el-input v-model="form.name" placeholder="请输入文档名称" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="10"
            placeholder="在此粘贴文档内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addDocument">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-detail {
  padding: 0;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-header-left {
  flex: 1;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.breadcrumb-link {
  color: var(--color-text-link);
  cursor: pointer;
  font-weight: 500;
  transition: color var(--rp-transition-fast);
}

.breadcrumb-link:hover {
  color: var(--rp-primary-700);
}

.breadcrumb-sep {
  color: var(--color-text-tertiary);
}

.breadcrumb-current {
  color: var(--color-text-secondary);
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-heading);
  letter-spacing: -0.01em;
  line-height: 1.3;
  margin: 0;
}

.page-desc {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
}

.stat-icon.blue {
  background: linear-gradient(135deg, var(--rp-primary-500), var(--rp-primary-400));
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
}

.stat-icon.green {
  background: linear-gradient(135deg, var(--rp-success-500), #4ade80);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.25);
}

.stat-icon.purple {
  background: linear-gradient(135deg, #8b5cf6, #a78bfa);
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25);
}

.stat-icon.orange {
  background: linear-gradient(135deg, var(--rp-warning-500), #fbbf24);
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.25);
}

.runtime-arch {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
  padding: 16px 20px;
  margin-bottom: 20px;
}

.runtime-arch-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.runtime-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.runtime-arch-item strong {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-heading);
}

.runtime-note {
  grid-column: 1 / -1;
  font-size: 12px;
  color: var(--color-text-secondary);
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-heading);
  line-height: 1.2;
}

.stat-value.small {
  font-size: 16px;
  font-weight: 600;
}

/* Section Card */
.section-card {
  padding: 20px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-heading);
}

.section-count {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

/* Plan Grid */
.plan-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.plan-card {
  padding: 16px;
  border: 2px solid var(--color-border);
  border-radius: var(--rp-radius-lg);
  background: var(--color-surface);
  text-align: left;
  cursor: pointer;
  transition: all var(--rp-transition-base);
}

.plan-card.active,
.plan-card:hover {
  border-color: var(--rp-primary-400);
  box-shadow: var(--rp-shadow-md);
}

.plan-card.active {
  background: var(--rp-primary-50);
  border-color: var(--rp-primary-500);
}

.plan-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.plan-card__head strong {
  font-size: 15px;
  color: var(--color-heading);
}

.plan-card p {
  min-height: 42px;
  margin: 0 0 8px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.plan-card__meta {
  color: var(--color-text-tertiary);
  font-size: 12px;
  margin-bottom: 6px;
}

.plan-card em {
  display: block;
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-style: normal;
  line-height: 1.4;
}

.tier-tip {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--rp-primary-50);
  border-radius: var(--rp-radius-md);
  color: var(--rp-primary-700);
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.tier-tip .el-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 40px 24px;
}

.empty-icon {
  margin-bottom: 12px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
  margin-bottom: 4px;
}

.empty-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 16px;
}

.empty-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* Doc List */
.doc-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: var(--rp-radius-md);
  border: 1px solid var(--color-border-light);
  transition: all var(--rp-transition-fast);
}

.doc-item:hover {
  background: var(--rp-primary-50);
  border-color: var(--rp-primary-200);
}

.doc-item-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--rp-primary-50);
  color: var(--rp-primary-600);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.doc-item-info {
  flex: 1;
  min-width: 0;
}

.doc-item-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-heading);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-item-preview {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.config-grid .section-card {
  margin-bottom: 0;
}

/* Config Actions */
.config-actions {
  margin-bottom: 24px;
  display: flex;
  justify-content: flex-end;
}

/* Field Tips */
.field-tip {
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

/* Hit Test Result */
.hit-test-result {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border-light);
}

.result-block {
  margin-top: 16px;
}

.result-block:first-child {
  margin-top: 0;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--color-heading);
}

.result-block pre {
  white-space: pre-wrap;
  margin: 0;
  padding: 16px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text);
  border: 1px solid var(--color-border-light);
}

/* Utilities */
.mb-lg {
  margin-bottom: 20px;
}

/* Responsive */
@media (max-width: 960px) {
  .stats-row {
    grid-template-columns: 1fr;
  }

  .plan-grid {
    grid-template-columns: 1fr;
  }

  .config-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    gap: 16px;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
