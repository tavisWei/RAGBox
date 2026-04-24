<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { resourceConfigApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'
import {
  Plus,
  Edit,
  Delete,
  Document,
  Cpu,
  Search,
  Filter,
  Rank,
  MagicStick,
  Collection,
  DataLine,
} from '@element-plus/icons-vue'

interface ResourceConfigSettings {
  data_store_type?: string
  max_documents?: number
  embedding_model?: string
  chunk_size?: number
  chunk_overlap?: number
  vector_enabled?: boolean
  keyword_enabled?: boolean
  fulltext_enabled?: boolean
  rerank_enabled?: boolean
  recommended_retrieval?: {
    methods?: string[]
    top_k?: number
    fusion_mode?: string
    query_expansion?: string
    rerank_mode?: string
  }
}

interface ResourceConfig {
  id: string
  name: string
  config_type: string
  settings: ResourceConfigSettings
}

const configs = ref<ResourceConfig[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const activeLevel = ref<'all' | 'low' | 'medium' | 'high'>('all')
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const form = ref({
  name: '',
  level: 'medium',
  data_store_type: 'pgvector',
  max_documents: 1000000,
  embedding_model: 'text-embedding-3-small',
  chunk_size: 500,
  chunk_overlap: 50,
  vector_enabled: true,
  keyword_enabled: true,
  fulltext_enabled: true,
  rerank_enabled: true,
  retrieval_methods: ['hybrid'] as string[],
  retrieval_top_k: 10,
  retrieval_fusion_mode: 'rrf',
  retrieval_query_expansion: 'multi_query',
  retrieval_rerank_mode: 'cross_encoder',
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入配置名称', trigger: 'blur' },
    { min: 2, max: 40, message: '名称长度需为 2-40 个字符', trigger: 'blur' },
  ],
  level: [{ required: true, message: '请选择资源等级', trigger: 'change' }],
  data_store_type: [{ required: true, message: '请选择存储类型', trigger: 'change' }],
  embedding_model: [{ required: true, message: '请选择嵌入模型', trigger: 'change' }],
  retrieval_methods: [
    {
      validator: (_rule, value, callback) => {
        if (Array.isArray(value) && value.length > 0) callback()
        else callback(new Error('至少选择一种检索方式'))
      },
      trigger: 'change',
    },
  ],
}

const levelOptions = [
  { label: '轻量起步', value: 'low', desc: 'SQLite 本地混合检索，适合个人/小团队，最小组件' },
  { label: '团队标准', value: 'medium', desc: 'PostgreSQL + pgvector，适合团队生产 RAG' },
  { label: '企业增强', value: 'high', desc: 'Elasticsearch/企业向量集群，适合大规模和高质量检索' },
]

const defaultConfigs = (): ResourceConfig[] => [
  {
    id: 'low-default',
    name: '轻量起步资源',
    config_type: 'low',
    settings: {
      data_store_type: 'sqlite',
      max_documents: 10000,
      embedding_model: 'nomic-embed-text',
      chunk_size: 400,
      chunk_overlap: 50,
      vector_enabled: true,
      keyword_enabled: true,
      fulltext_enabled: true,
      rerank_enabled: false,
      recommended_retrieval: {
        methods: ['fulltext', 'keyword'],
        top_k: 5,
        fusion_mode: 'simple',
        query_expansion: 'none',
        rerank_mode: 'none',
      },
    },
  },
  {
    id: 'medium-default',
    name: '团队标准资源',
    config_type: 'medium',
    settings: {
      data_store_type: 'pgvector',
      max_documents: 1000000,
      embedding_model: 'text-embedding-3-small',
      chunk_size: 500,
      chunk_overlap: 100,
      vector_enabled: true,
      keyword_enabled: true,
      fulltext_enabled: true,
      rerank_enabled: true,
      recommended_retrieval: {
        methods: ['hybrid'],
        top_k: 10,
        fusion_mode: 'rrf',
        query_expansion: 'multi_query',
        rerank_mode: 'cross_encoder',
      },
    },
  },
  {
    id: 'high-default',
    name: '企业增强资源',
    config_type: 'high',
    settings: {
      data_store_type: 'elasticsearch',
      max_documents: 100000000,
      embedding_model: 'text-embedding-3-large',
      chunk_size: 1200,
      chunk_overlap: 120,
      vector_enabled: true,
      keyword_enabled: true,
      fulltext_enabled: true,
      rerank_enabled: true,
      recommended_retrieval: {
        methods: ['hybrid', 'semantic', 'fulltext'],
        top_k: 20,
        fusion_mode: 'weighted',
        query_expansion: 'hyde',
        rerank_mode: 'llm_listwise',
      },
    },
  },
]

const systemTemplates = defaultConfigs()

const configCards = computed(() =>
  configs.value
    .filter((config) => !isDefaultConfig(config))
    .filter((config) => activeLevel.value === 'all' || config.config_type === activeLevel.value)
    .map((config) => {
      const settings = config.settings || {}
      return {
        ...config,
        settings,
        featureCount: [
          settings.vector_enabled,
          settings.keyword_enabled,
          settings.fulltext_enabled,
          settings.rerank_enabled,
        ].filter(Boolean).length,
      }
    }),
)

const {
  currentPage,
  total,
  paginatedItems: paginatedConfigCards,
  shouldPaginate,
  resetPagination,
} = useClientPagination(configCards, 12)

const fetchConfigs = async () => {
  loading.value = true
  try {
    const response = await resourceConfigApi.list()
    configs.value = response.data
  } catch {
    configs.value = defaultConfigs()
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    name: '',
    level: 'medium',
    data_store_type: 'pgvector',
    max_documents: 1000000,
    embedding_model: 'text-embedding-3-small',
    chunk_size: 500,
    chunk_overlap: 50,
    vector_enabled: true,
    keyword_enabled: true,
    fulltext_enabled: true,
    rerank_enabled: true,
    retrieval_methods: ['hybrid'],
    retrieval_top_k: 10,
    retrieval_fusion_mode: 'rrf',
    retrieval_query_expansion: 'multi_query',
    retrieval_rerank_mode: 'cross_encoder',
  }
}

const applyTemplate = (template: ResourceConfig) => {
  const settings = template.settings || {}
  const retrieval = settings.recommended_retrieval || {}
  form.value.level = template.config_type
  form.value.data_store_type = settings.data_store_type || 'pgvector'
  form.value.max_documents = settings.max_documents || 1000000
  form.value.embedding_model = settings.embedding_model || 'text-embedding-3-small'
  form.value.chunk_size = settings.chunk_size || 500
  form.value.chunk_overlap = settings.chunk_overlap || 50
  form.value.vector_enabled = !!settings.vector_enabled
  form.value.keyword_enabled = !!settings.keyword_enabled
  form.value.fulltext_enabled = !!settings.fulltext_enabled
  form.value.rerank_enabled = !!settings.rerank_enabled
  form.value.retrieval_methods = retrieval.methods?.length ? [...retrieval.methods] : ['hybrid']
  form.value.retrieval_top_k = retrieval.top_k || 10
  form.value.retrieval_fusion_mode = retrieval.fusion_mode || 'rrf'
  form.value.retrieval_query_expansion = retrieval.query_expansion || 'multi_query'
  form.value.retrieval_rerank_mode = retrieval.rerank_mode || 'cross_encoder'
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const openEdit = (config: ResourceConfig) => {
  const settings = config.settings || {}
  const retrieval = settings.recommended_retrieval || {}
  editingId.value = config.id
  form.value = {
    name: config.name,
    level: config.config_type,
    data_store_type: settings.data_store_type || 'pgvector',
    max_documents: settings.max_documents || 1000000,
    embedding_model: settings.embedding_model || 'text-embedding-3-small',
    chunk_size: settings.chunk_size || 500,
    chunk_overlap: settings.chunk_overlap || 50,
    vector_enabled: !!settings.vector_enabled,
    keyword_enabled: !!settings.keyword_enabled,
    fulltext_enabled: !!settings.fulltext_enabled,
    rerank_enabled: !!settings.rerank_enabled,
    retrieval_methods: retrieval.methods?.length ? retrieval.methods : ['hybrid'],
    retrieval_top_k: retrieval.top_k || 10,
    retrieval_fusion_mode: retrieval.fusion_mode || 'rrf',
    retrieval_query_expansion: retrieval.query_expansion || 'multi_query',
    retrieval_rerank_mode: retrieval.rerank_mode || 'cross_encoder',
  }
  dialogVisible.value = true
}

const handleDialogClosed = () => {
  formRef.value?.clearValidate()
  resetForm()
}

const handleSubmit = async () => {
  try {
    const isValid = await formRef.value?.validate().catch(() => false)
    if (!isValid) return

    saving.value = true
    const payload = {
      name: form.value.name,
      config_type: form.value.level,
      settings: {
        data_store_type: form.value.data_store_type,
        max_documents: form.value.max_documents,
        embedding_model: form.value.embedding_model,
        chunk_size: form.value.chunk_size,
        chunk_overlap: form.value.chunk_overlap,
        vector_enabled: form.value.vector_enabled,
        keyword_enabled: form.value.keyword_enabled,
        fulltext_enabled: form.value.fulltext_enabled,
        rerank_enabled: form.value.rerank_enabled,
        recommended_retrieval: {
          methods: form.value.retrieval_methods,
          top_k: form.value.retrieval_top_k,
          fusion_mode: form.value.retrieval_fusion_mode,
          query_expansion: form.value.retrieval_query_expansion,
          rerank_mode: form.value.retrieval_rerank_mode,
        },
      },
    }
    if (editingId.value)
      await resourceConfigApi.update(editingId.value, payload)
    else
      await resourceConfigApi.create(payload)

    ElMessage.success(editingId.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    resetForm()
    await fetchConfigs()
  } catch {
    ElMessage.error(editingId.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (config: ResourceConfig) => {
  if (isDefaultConfig(config)) {
    ElMessage.warning('默认配置不允许删除')
    return
  }

  try {
    await ElMessageBox.confirm(`确定删除配置"${config.name}"吗？`, '提示', {
      type: 'warning',
    })
    await resourceConfigApi.delete(config.id)
    ElMessage.success('删除成功')
    await fetchConfigs()
  } catch {
    // cancelled
  }
}

const getLevelTag = (level: string) => {
  const map: Record<string, string> = {
    low: 'info',
    medium: 'success',
    high: 'danger',
  }
  return map[level] || 'info'
}

const getLevelLabel = (level: string) => {
  const map: Record<string, string> = {
    low: '低配',
    medium: '中配',
    high: '高配',
  }
  return map[level] || level
}

const getLevelIcon = (level: string) => {
  const map: Record<string, any> = {
    low: Document,
    medium: Collection,
    high: DataLine,
  }
  return map[level] || Document
}

const getLevelAccent = (level: string) => {
  const map: Record<string, string> = {
    low: 'var(--rp-info-500)',
    medium: 'var(--rp-success-500)',
    high: 'var(--rp-coral-500)',
  }
  return map[level] || 'var(--rp-primary-500)'
}

const getLevelBg = (level: string) => {
  const map: Record<string, string> = {
    low: 'var(--rp-info-50)',
    medium: 'var(--rp-success-50)',
    high: 'var(--rp-coral-50)',
  }
  return map[level] || 'var(--rp-primary-50)'
}

const formatNumber = (value?: number) =>
  typeof value === 'number' ? value.toLocaleString() : '-'

const formatMethods = (methods?: string[]) =>
  methods?.length ? methods.join(' / ') : '未配置'

const isDefaultConfig = (config: ResourceConfig) => config.id.endsWith('-default')

onMounted(() => {
  fetchConfigs()
})

watch([configCards, activeLevel], () => {
  resetPagination()
})
</script>

<template>
  <div class="resource-configs">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-text">
        <h2 class="page-title">RAG 方案</h2>
        <p class="page-subtitle">
          管理自定义成本/性能方案，系统模板仅在创建知识库或新建方案时使用
        </p>
      </div>
      <el-button type="primary" size="large" @click="openCreate">
        <el-icon><Plus /></el-icon>
        创建方案
      </el-button>
    </div>

    <!-- Info Banner -->
    <div class="info-banner">
      <el-icon size="18" class="banner-icon"><MagicStick /></el-icon>
      <p>
        RAG 方案会影响分块、检索、查询扩展、重排和推荐模型；底层数据库连接由部署环境或管理员维护
      </p>
    </div>

    <!-- Filter Tabs -->
    <div class="filter-tabs">
      <button
        v-for="tab in [
          { label: '全部方案', value: 'all' },
          { label: '低配', value: 'low' },
          { label: '中配', value: 'medium' },
          { label: '高配', value: 'high' },
        ]"
        :key="tab.value"
        class="filter-tab"
        :class="{ active: activeLevel === tab.value }"
        @click="activeLevel = tab.value as any"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Loading State -->
    <el-skeleton v-if="loading" :rows="8" animated />

    <!-- Empty State -->
    <template v-else>
      <el-empty v-if="configCards.length === 0" description="暂无自定义 RAG 方案">
        <template #image>
          <div class="empty-illustration">
            <el-icon size="64" class="text-tertiary"><Document /></el-icon>
          </div>
        </template>
      </el-empty>

      <!-- Config Cards Grid -->
      <div v-else class="config-grid">
        <div
          v-for="config in paginatedConfigCards"
          :key="config.id"
          class="config-card surface-card surface-card-hover"
        >
          <!-- Card Header -->
          <div class="card-header-row">
            <div class="level-badge" :style="{ background: getLevelBg(config.config_type), color: getLevelAccent(config.config_type) }">
              <el-icon size="14"><component :is="getLevelIcon(config.config_type)" /></el-icon>
              <span>{{ getLevelLabel(config.config_type) }}</span>
            </div>
            <div class="card-actions">
              <el-button size="small" text circle @click="openEdit(config)">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button size="small" text circle type="danger" @click="handleDelete(config)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- Card Title -->
          <h3 class="card-title">{{ config.name }}</h3>
          <p class="card-id">ID: {{ config.id }}</p>

          <!-- Core Metrics -->
          <div class="metrics-section">
            <div class="metric-pill">
              <el-icon size="14" class="text-secondary"><Cpu /></el-icon>
              <span class="metric-pill-label">存储</span>
              <span class="metric-pill-value">{{ config.settings.data_store_type || '-' }}</span>
            </div>
            <div class="metric-pill">
              <el-icon size="14" class="text-secondary"><Document /></el-icon>
              <span class="metric-pill-label">文档上限</span>
              <span class="metric-pill-value">{{ formatNumber(config.settings.max_documents) }}</span>
            </div>
            <div class="metric-pill">
              <el-icon size="14" class="text-secondary"><MagicStick /></el-icon>
              <span class="metric-pill-label">嵌入模型</span>
              <span class="metric-pill-value">{{ config.settings.embedding_model || '-' }}</span>
            </div>
            <div class="metric-pill">
              <el-icon size="14" class="text-secondary"><Collection /></el-icon>
              <span class="metric-pill-label">分块</span>
              <span class="metric-pill-value">{{ config.settings.chunk_size || '-' }} / {{ config.settings.chunk_overlap || '-' }}</span>
            </div>
          </div>

          <!-- Feature Toggles -->
          <div class="features-section">
            <div class="section-label">
              <el-icon size="14"><Filter /></el-icon>
              能力开关
              <span class="feature-count">{{ config.featureCount }} 项已启用</span>
            </div>
            <div class="feature-chips">
              <span
                class="feature-chip"
                :class="{ active: config.settings.vector_enabled }"
              >
                <el-icon size="12"><Search /></el-icon>
                向量检索
              </span>
              <span
                class="feature-chip"
                :class="{ active: config.settings.keyword_enabled }"
              >
                <el-icon size="12"><Filter /></el-icon>
                关键词
              </span>
              <span
                class="feature-chip"
                :class="{ active: config.settings.fulltext_enabled }"
              >
                <el-icon size="12"><Document /></el-icon>
                全文检索
              </span>
              <span
                class="feature-chip"
                :class="{ active: config.settings.rerank_enabled }"
              >
                <el-icon size="12"><Rank /></el-icon>
                重排序
              </span>
            </div>
          </div>

          <!-- Retrieval Settings -->
          <div class="retrieval-section">
            <div class="section-label">
              <el-icon size="14"><Search /></el-icon>
              推荐检索参数
            </div>
            <div class="retrieval-grid">
              <div class="retrieval-item">
                <span class="retrieval-label">检索方式</span>
                <span class="retrieval-value">{{ formatMethods(config.settings.recommended_retrieval?.methods) }}</span>
              </div>
              <div class="retrieval-item">
                <span class="retrieval-label">Top K</span>
                <span class="retrieval-value">{{ config.settings.recommended_retrieval?.top_k || '-' }}</span>
              </div>
              <div class="retrieval-item">
                <span class="retrieval-label">融合模式</span>
                <span class="retrieval-value">{{ config.settings.recommended_retrieval?.fusion_mode || '-' }}</span>
              </div>
              <div class="retrieval-item">
                <span class="retrieval-label">Query Expansion</span>
                <span class="retrieval-value">{{ config.settings.recommended_retrieval?.query_expansion || '-' }}</span>
              </div>
              <div class="retrieval-item wide">
                <span class="retrieval-label">Rerank</span>
                <span class="retrieval-value">{{ config.settings.recommended_retrieval?.rerank_mode || '-' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="shouldPaginate" class="page-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :total="total"
          :page-size="12"
          background
          layout="prev, pager, next"
          :hide-on-single-page="true"
        />
      </div>
    </template>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑 RAG 方案' : '创建 RAG 方案'"
      width="680px"
      @closed="handleDialogClosed"
      class="config-dialog"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="130px">
        <!-- Templates Section (only for create) -->
        <template v-if="!editingId">
          <div class="dialog-section">
            <div class="dialog-section-title">
              <el-icon size="16"><MagicStick /></el-icon>
              从系统模板开始
            </div>
            <p class="dialog-section-desc">选择一个预设模板快速填充推荐参数</p>
            <div class="template-grid">
              <button
                v-for="template in systemTemplates"
                :key="template.id"
                type="button"
                class="template-card"
                @click="applyTemplate(template)"
              >
                <div class="template-card__icon" :style="{ background: getLevelBg(template.config_type), color: getLevelAccent(template.config_type) }">
                  <el-icon size="20"><component :is="getLevelIcon(template.config_type)" /></el-icon>
                </div>
                <div class="template-card__content">
                  <strong>{{ template.name }}</strong>
                  <span>{{ template.settings.data_store_type }} · {{ formatNumber(template.settings.max_documents) }} 文档</span>
                </div>
                <el-icon size="16" class="template-card__arrow"><Plus /></el-icon>
              </button>
            </div>
          </div>

          <div class="divider-soft" />
        </template>

        <!-- Basic Info -->
        <div class="dialog-section">
          <div class="dialog-section-title">基本信息</div>
          <el-form-item label="方案名称" prop="name" required>
            <el-input v-model="form.name" placeholder="给方案起个名字" />
          </el-form-item>

          <el-form-item label="资源等级" prop="level">
            <el-select v-model="form.level" style="width: 100%">
              <el-option
                v-for="opt in levelOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              >
                <div class="level-option">
                  <span class="level-option-name">{{ opt.label }}</span>
                  <span class="level-option-desc">{{ opt.desc }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
        </div>

        <div class="divider-soft" />

        <!-- Storage & Model -->
        <div class="dialog-section">
          <div class="dialog-section-title">存储与模型</div>
          <el-form-item label="推荐后端" prop="data_store_type">
            <el-select v-model="form.data_store_type" style="width: 100%">
              <el-option label="SQLite（轻量本地）" value="sqlite" />
              <el-option label="PostgreSQL + pgvector（团队标准）" value="pgvector" />
              <el-option label="Elasticsearch（企业增强）" value="elasticsearch" />
            </el-select>
          </el-form-item>

          <el-form-item label="建议文档数">
            <el-input-number v-model="form.max_documents" :min="1000" :step="1000" style="width: 100%" />
          </el-form-item>

          <el-form-item label="嵌入模型" prop="embedding_model">
            <el-select v-model="form.embedding_model" style="width: 100%">
              <el-option label="text-embedding-3-small" value="text-embedding-3-small" />
              <el-option label="text-embedding-3-large" value="text-embedding-3-large" />
            </el-select>
          </el-form-item>

          <el-form-item label="Chunk 策略">
            <div class="chunk-row">
              <div class="chunk-field">
                <span class="chunk-label">大小</span>
                <el-input-number v-model="form.chunk_size" :min="100" :step="50" />
              </div>
              <div class="chunk-divider">/</div>
              <div class="chunk-field">
                <span class="chunk-label">重叠</span>
                <el-input-number v-model="form.chunk_overlap" :min="0" :step="10" />
              </div>
            </div>
          </el-form-item>
        </div>

        <div class="divider-soft" />

        <!-- Feature Toggles -->
        <div class="dialog-section">
          <div class="dialog-section-title">功能开关</div>
          <el-form-item label="启用能力">
            <div class="toggle-grid">
              <label class="toggle-item" :class="{ active: form.vector_enabled }">
                <el-checkbox v-model="form.vector_enabled" :value="true" />
                <div class="toggle-info">
                  <span class="toggle-name">向量检索</span>
                  <span class="toggle-desc">语义相似度搜索</span>
                </div>
              </label>
              <label class="toggle-item" :class="{ active: form.keyword_enabled }">
                <el-checkbox v-model="form.keyword_enabled" :value="true" />
                <div class="toggle-info">
                  <span class="toggle-name">关键词</span>
                  <span class="toggle-desc">精确匹配搜索</span>
                </div>
              </label>
              <label class="toggle-item" :class="{ active: form.fulltext_enabled }">
                <el-checkbox v-model="form.fulltext_enabled" :value="true" />
                <div class="toggle-info">
                  <span class="toggle-name">全文检索</span>
                  <span class="toggle-desc">BM25 全文搜索</span>
                </div>
              </label>
              <label class="toggle-item" :class="{ active: form.rerank_enabled }">
                <el-checkbox v-model="form.rerank_enabled" :value="true" />
                <div class="toggle-info">
                  <span class="toggle-name">重排序</span>
                  <span class="toggle-desc">结果重排序优化</span>
                </div>
              </label>
            </div>
          </el-form-item>
        </div>

        <div class="divider-soft" />

        <!-- Retrieval Parameters -->
        <div class="dialog-section">
          <div class="dialog-section-title">推荐检索参数</div>
          <el-form-item label="检索方式" prop="retrieval_methods">
            <el-checkbox-group v-model="form.retrieval_methods">
              <el-checkbox value="fulltext">全文</el-checkbox>
              <el-checkbox value="keyword">关键词</el-checkbox>
              <el-checkbox value="semantic">语义</el-checkbox>
              <el-checkbox value="hybrid">混合</el-checkbox>
            </el-checkbox-group>
          </el-form-item>

          <el-form-item label="Top K">
            <el-input-number v-model="form.retrieval_top_k" :min="1" :max="100" :step="1" style="width: 100%" />
          </el-form-item>

          <el-form-item label="融合模式">
            <el-select v-model="form.retrieval_fusion_mode" style="width: 100%">
              <el-option label="simple" value="simple" />
              <el-option label="rrf" value="rrf" />
              <el-option label="weighted" value="weighted" />
            </el-select>
          </el-form-item>

          <el-form-item label="Query Expansion">
            <el-select v-model="form.retrieval_query_expansion" style="width: 100%">
              <el-option label="none" value="none" />
              <el-option label="multi_query" value="multi_query" />
              <el-option label="hyde" value="hyde" />
            </el-select>
          </el-form-item>

          <el-form-item label="Rerank">
            <el-select v-model="form.retrieval_rerank_mode" style="width: 100%">
              <el-option label="none" value="none" />
              <el-option label="cross_encoder" value="cross_encoder" />
              <el-option label="llm_listwise" value="llm_listwise" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">
          {{ editingId ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.resource-configs {
  padding: 0;
}

/* Header */
.header-text {
  flex: 1;
}

/* Info Banner */
.info-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  background: var(--rp-primary-50);
  border: 1px solid var(--rp-primary-200);
  border-radius: var(--rp-radius-lg);
  margin-bottom: var(--page-gap);
}

.info-banner p {
  margin: 0;
  font-size: 13px;
  color: var(--rp-primary-700);
  line-height: 1.6;
}

.banner-icon {
  color: var(--rp-primary-500);
  flex-shrink: 0;
  margin-top: 2px;
}

/* Filter Tabs */
.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: var(--page-gap);
}

.filter-tab {
  padding: 8px 18px;
  border-radius: var(--rp-radius-full);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--rp-transition-fast);
}

.filter-tab:hover {
  border-color: var(--rp-primary-300);
  color: var(--rp-primary-600);
}

.filter-tab.active {
  background: var(--rp-primary-500);
  border-color: var(--rp-primary-500);
  color: var(--rp-white);
}

/* Empty State */
.empty-illustration {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 120px;
  height: 120px;
  border-radius: var(--rp-radius-xl);
  background: var(--color-surface-muted);
  margin-bottom: 16px;
}

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: var(--page-gap);
}

/* Config Card */
.config-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.level-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--rp-radius-full);
  font-size: 13px;
  font-weight: 600;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.card-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-heading);
  letter-spacing: -0.01em;
}

.card-id {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-family: 'SF Mono', monospace;
}

/* Metrics Section */
.metrics-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.metric-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  border: 1px solid var(--color-border-light);
}

.metric-pill-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.metric-pill-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  margin-left: auto;
}

/* Features Section */
.features-section,
.retrieval-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-heading);
}

.feature-count {
  margin-left: auto;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-surface-muted);
  padding: 2px 10px;
  border-radius: var(--rp-radius-full);
}

.feature-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.feature-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--rp-radius-full);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-tertiary);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--rp-transition-fast);
}

.feature-chip.active {
  background: var(--rp-success-50);
  border-color: var(--rp-success-500);
  color: var(--rp-success-600);
}

/* Retrieval Section */
.retrieval-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.retrieval-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  border: 1px solid var(--color-border-light);
}

.retrieval-item.wide {
  grid-column: span 2;
}

.retrieval-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.retrieval-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  word-break: break-word;
}

/* Dialog Styles */
.config-dialog :deep(.el-dialog__body) {
  padding: 0 !important;
}

.config-dialog :deep(.el-form) {
  padding: 24px;
}

.dialog-section {
  margin-bottom: 8px;
}

.dialog-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--color-heading);
  margin-bottom: 16px;
}

.dialog-section-desc {
  margin: -8px 0 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* Template Grid in Dialog */
.template-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.template-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--rp-radius-lg);
  background: var(--color-surface);
  cursor: pointer;
  transition: all var(--rp-transition-fast);
  text-align: left;
}

.template-card:hover {
  border-color: var(--rp-primary-300);
  box-shadow: var(--rp-shadow-md);
  transform: translateY(-1px);
}

.template-card__icon {
  width: 44px;
  height: 44px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.template-card__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-card__content strong {
  font-size: 14px;
  color: var(--color-heading);
}

.template-card__content span {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.template-card__arrow {
  color: var(--color-text-tertiary);
}

/* Level Option */
.level-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.level-option-name {
  font-weight: 500;
}

.level-option-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* Chunk Row */
.chunk-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.chunk-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.chunk-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.chunk-divider {
  color: var(--color-text-tertiary);
  font-weight: 600;
  padding-top: 20px;
}

/* Toggle Grid */
.toggle-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.toggle-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--rp-radius-md);
  background: var(--color-surface);
  cursor: pointer;
  transition: all var(--rp-transition-fast);
}

.toggle-item:hover {
  border-color: var(--rp-primary-300);
}

.toggle-item.active {
  background: var(--rp-primary-50);
  border-color: var(--rp-primary-300);
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.toggle-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-heading);
}

.toggle-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* Responsive */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .config-grid {
    grid-template-columns: 1fr;
  }

  .metrics-section {
    grid-template-columns: 1fr;
  }

  .template-grid {
    grid-template-columns: 1fr;
  }

  .toggle-grid {
    grid-template-columns: 1fr;
  }

  .retrieval-grid {
    grid-template-columns: 1fr;
  }

  .retrieval-item.wide {
    grid-column: span 1;
  }
}
</style>
