<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeBaseApi } from '@/api'
import { useKnowledgeBaseStore } from '@/stores/knowledgeBase'
import { useClientPagination } from '@/composables/useClientPagination'
import type { KnowledgeBase, RagPlanPreset } from '@/types'

const kbStore = useKnowledgeBaseStore()
const dialogVisible = ref(false)
const form = ref({
  name: '',
  description: '',
  embedding_model: 'text-embedding-3-small',
  rag_plan: 'medium',
})
const ragPlans = ref<RagPlanPreset[]>([])

const knowledgeBases = computed(() => kbStore.knowledgeBases)
const {
  currentPage,
  total,
  paginatedItems: paginatedKnowledgeBases,
  shouldPaginate,
  resetPagination,
} = useClientPagination(knowledgeBases, 12)

const fetchRagPlans = async () => {
  const response = await knowledgeBaseApi.getRagPlans()
  ragPlans.value = response.data.data || []
}

const handleCreate = async () => {
  try {
    await kbStore.createKnowledgeBase(form.value)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    form.value = { name: '', description: '', embedding_model: 'text-embedding-3-small', rag_plan: 'medium' }
  } catch {
    ElMessage.error('创建失败')
  }
}

const handleDelete = async (kb: KnowledgeBase) => {
  try {
    await ElMessageBox.confirm('确定要删除该知识库吗？', '提示', {
      type: 'warning',
    })
    await kbStore.deleteKnowledgeBase(kb.id)
    ElMessage.success('删除成功')
  } catch {
    // cancelled
  }
}

const getRagPlanLabel = (key: string) => {
  if (key === 'low') return '轻量起步'
  if (key === 'high') return '企业增强'
  return '团队标准'
}

const getRagPlanBackend = (plan?: RagPlanPreset) => {
  if (!plan) return '-'
  if (plan.key === 'low') return 'SQLite 本地混合检索'
  if (plan.key === 'high') return 'Elasticsearch / 企业向量集群'
  return 'PostgreSQL + pgvector'
}

const getRagPlanColor = (key: string) => {
  if (key === 'low') return 'success'
  if (key === 'high') return 'warning'
  return 'primary'
}

onMounted(() => {
  kbStore.fetchKnowledgeBases()
  fetchRagPlans()
})

watch(knowledgeBases, () => {
  resetPagination()
})
</script>

<template>
  <div class="knowledge-base">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-left">
        <h1 class="page-title">知识库管理</h1>
        <p class="page-subtitle">管理你的知识库，配置 RAG 检索方案</p>
      </div>
      <el-button type="primary" size="large" @click="dialogVisible = true">
        <el-icon><Plus /></el-icon>
        创建知识库
      </el-button>
    </div>

    <!-- Empty State -->
    <div v-if="kbStore.knowledgeBases.length === 0 && !kbStore.loading" class="empty-state surface-card">
      <div class="empty-icon">
        <el-icon size="48" color="var(--color-text-tertiary)"><Collection /></el-icon>
      </div>
      <div class="empty-title">还没有知识库</div>
      <div class="empty-desc">创建你的第一个知识库，上传文档并配置检索方案</div>
      <el-button type="primary" size="large" @click="dialogVisible = true">
        <el-icon><Plus /></el-icon>
        创建知识库
      </el-button>
    </div>

    <!-- KB Cards Grid -->
    <div v-else class="kb-grid">
      <div
        v-for="kb in paginatedKnowledgeBases"
        :key="kb.id"
        class="kb-card surface-card surface-card-hover"
        @click="$router.push(`/knowledge-bases/${kb.id}`)"
      >
        <div class="kb-card-header">
          <div class="kb-card-icon">
            <el-icon size="20"><Collection /></el-icon>
          </div>
          <div class="kb-card-title">{{ kb.name }}</div>
          <el-dropdown
            trigger="click"
            @click.stop
          >
            <div class="kb-card-menu">
              <el-icon size="16"><More /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click.stop="handleDelete(kb)">
                  <el-icon><Delete /></el-icon>
                  <span>删除</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <div class="kb-card-desc">{{ kb.description || '暂无描述' }}</div>

        <div class="kb-card-meta">
          <el-tag :type="getRagPlanColor(kb.rag_plan ?? 'medium')" size="small" effect="light">
            {{ getRagPlanLabel(kb.rag_plan ?? 'medium') }}
          </el-tag>
          <el-tag :type="kb.reindex_required ? 'warning' : 'success'" size="small" effect="light">
            {{ kb.reindex_required ? '需重建' : '已同步' }}
          </el-tag>
        </div>

        <div class="kb-card-footer">
          <div class="kb-stat">
            <el-icon size="14" color="var(--color-text-tertiary)"><Document /></el-icon>
            <span>{{ kb.document_count }} 文档</span>
          </div>
          <div class="kb-stat">
            <el-icon size="14" color="var(--color-text-tertiary)"><Connection /></el-icon>
            <span>{{ kb.embedding_model }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="shouldPaginate && !kbStore.loading" class="page-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :total="total"
        :page-size="12"
        background
        layout="prev, pager, next"
        :hide-on-single-page="true"
      />
    </div>

    <!-- Loading State -->
    <div v-if="kbStore.loading" class="kb-grid">
      <div v-for="i in 4" :key="i" class="kb-card surface-card skeleton-card">
        <div class="skeleton-header">
          <div class="skeleton-icon"></div>
          <div class="skeleton-title"></div>
        </div>
        <div class="skeleton-desc"></div>
        <div class="skeleton-meta"></div>
      </div>
    </div>

    <!-- Create Dialog -->
    <el-dialog v-model="dialogVisible" title="创建知识库" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="RAG 方案">
          <el-radio-group v-model="form.rag_plan" class="rag-plan-group">
            <el-radio-button v-for="plan in ragPlans" :key="plan.key" :value="plan.key">
              {{ plan.name }}
            </el-radio-button>
          </el-radio-group>
          <div
            v-for="plan in ragPlans.filter(item => item.key === form.rag_plan)"
            :key="plan.key"
            class="plan-preview surface-muted"
          >
            <div class="plan-preview-title">{{ plan.summary }}</div>
            <div class="plan-preview-meta">
              <span class="plan-badge">成本：{{ plan.cost_level }}</span>
              <span class="plan-badge">质量：{{ plan.quality_level }}</span>
              <span class="plan-badge">后端：{{ getRagPlanBackend(plan) }}</span>
              <span class="plan-badge">分块：{{ plan.splitter_config.type }} / {{ plan.splitter_config.chunk_size }}</span>
            </div>
            <div class="plan-preview-desc">{{ plan.architecture || plan.datastore_note }}</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.knowledge-base {
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

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-heading);
  letter-spacing: -0.01em;
  line-height: 1.3;
  margin: 0;
}

.page-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 60px 24px;
}

.empty-icon {
  margin-bottom: 16px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-heading);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 24px;
}

/* KB Grid */
.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

/* KB Card */
.kb-card {
  padding: 20px;
  cursor: pointer;
  transition: all var(--rp-transition-base);
  border: 1px solid var(--color-border);
}

.kb-card:hover {
  border-color: var(--rp-primary-300);
  transform: translateY(-2px);
  box-shadow: var(--rp-shadow-lg);
}

.kb-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.kb-card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--rp-primary-500), var(--rp-primary-400));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kb-card-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kb-card-menu {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: all var(--rp-transition-fast);
}

.kb-card-menu:hover {
  background: var(--color-surface-muted);
  color: var(--color-text);
}

.kb-card-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
  min-height: 40px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-card-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.kb-card-footer {
  display: flex;
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
}

.kb-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* RAG Plan Group */
.rag-plan-group {
  margin-bottom: 10px;
}

.plan-preview {
  padding: 12px;
  border-radius: var(--rp-radius-md);
}

.plan-preview-title {
  font-weight: 600;
  color: var(--color-heading);
  margin-bottom: 8px;
  font-size: 13px;
}

.plan-preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.plan-preview-desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.plan-badge {
  display: inline-block;
  padding: 2px 8px;
  background: var(--rp-white);
  border: 1px solid var(--color-border);
  border-radius: var(--rp-radius-sm);
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* Skeleton */
.skeleton-card {
  pointer-events: none;
}

.skeleton-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.skeleton-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--color-surface-muted);
  animation: pulse 1.5s ease-in-out infinite;
}

.skeleton-title {
  flex: 1;
  height: 18px;
  border-radius: 4px;
  background: var(--color-surface-muted);
  animation: pulse 1.5s ease-in-out infinite;
  animation-delay: 0.1s;
}

.skeleton-desc {
  height: 40px;
  border-radius: 4px;
  background: var(--color-surface-muted);
  animation: pulse 1.5s ease-in-out infinite;
  animation-delay: 0.2s;
  margin-bottom: 12px;
}

.skeleton-meta {
  height: 24px;
  width: 80px;
  border-radius: 4px;
  background: var(--color-surface-muted);
  animation: pulse 1.5s ease-in-out infinite;
  animation-delay: 0.3s;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* Responsive */
@media (max-width: 768px) {
  .kb-grid {
    grid-template-columns: 1fr;
  }
}
</style>
