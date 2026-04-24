<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useKnowledgeBaseStore } from '@/stores/knowledgeBase'
import { monitoringApi } from '@/api'

const kbStore = useKnowledgeBaseStore()
const health = ref<any>({})

onMounted(async () => {
  await kbStore.fetchKnowledgeBases()
  try {
    const res = await monitoringApi.getHealth()
    health.value = res.data
  } catch {
  }
})

const quickActions = [
  {
    icon: 'Plus',
    label: '创建知识库',
    desc: '上传文档，构建知识库',
    color: 'blue',
    path: '/knowledge-bases',
  },
  {
    icon: 'ChatDotRound',
    label: '开始对话',
    desc: '基于知识库进行问答',
    color: 'green',
    path: '/chat',
  },
  {
    icon: 'Cpu',
    label: '配置智能体',
    desc: '自定义 AI 助手行为',
    color: 'purple',
    path: '/agent',
  },
]

const statCards = [
  {
    icon: 'Collection',
    value: () => kbStore.knowledgeBases.length,
    label: '知识库',
    color: 'blue',
  },
  {
    icon: 'Document',
    value: () => 0,
    label: '文档',
    color: 'green',
  },
  {
    icon: 'ChatDotRound',
    value: () => 0,
    label: '问答次数',
    color: 'purple',
  },
  {
    icon: 'Timer',
    value: () => (health.value.status === 'healthy' ? '正常' : '-'),
    label: '系统状态',
    color: 'orange',
  },
]
</script>

<template>
  <div class="home">
    <!-- Welcome Header -->
    <div class="welcome-header">
      <h1 class="welcome-title">欢迎回来</h1>
      <p class="welcome-subtitle">这里是你的 RAG 工作空间概览</p>
    </div>

    <!-- Stat Cards -->
    <div class="stat-grid">
      <div
        v-for="stat in statCards"
        :key="stat.label"
        class="stat-card surface-card surface-card-hover"
      >
        <div class="stat-icon" :class="stat.color">
          <el-icon size="24">
            <component :is="stat.icon" />
          </el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ stat.value() }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
      </div>
    </div>

    <!-- Main Content Grid -->
    <el-row :gutter="20" class="content-grid">
      <el-col :span="16">
        <div class="surface-card quick-actions-card">
          <div class="card-header">
            <div class="card-header-title">
              <el-icon size="18" class="text-accent"><Star /></el-icon>
              <span>快捷操作</span>
            </div>
          </div>

          <div class="quick-actions-grid">
            <div
              v-for="action in quickActions"
              :key="action.label"
              class="quick-action surface-card-hover"
              @click="$router.push(action.path)"
            >
              <div class="quick-action-icon" :class="action.color">
                <el-icon size="24">
                  <component :is="action.icon" />
                </el-icon>
              </div>
              <div class="quick-action-title">{{ action.label }}</div>
              <div class="quick-action-desc">{{ action.desc }}</div>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :span="8">
        <div class="surface-card recent-card">
          <div class="card-header">
            <div class="card-header-title">
              <el-icon size="18" class="text-accent"><Clock /></el-icon>
              <span>最近知识库</span>
            </div>
            <el-link type="primary" class="view-all-link" @click="$router.push('/knowledge-bases')">
              查看全部
            </el-link>
          </div>

          <div v-if="kbStore.knowledgeBases.length === 0" class="empty-state">
            <div class="empty-icon">
              <el-icon size="40" color="var(--color-text-tertiary)"><Collection /></el-icon>
            </div>
            <div class="empty-title">还没有知识库</div>
            <div class="empty-desc">创建你的第一个知识库，开始构建 AI 知识库</div>
            <el-button type="primary" class="mt-md" @click="$router.push('/knowledge-bases')">
              立即创建
            </el-button>
          </div>

          <div v-else class="kb-list">
            <div
              v-for="kb in kbStore.knowledgeBases.slice(0, 5)"
              :key="kb.id"
              class="kb-item"
              @click="$router.push(`/knowledge-bases/${kb.id}`)"
            >
              <div class="kb-item-icon">
                <el-icon size="16"><Document /></el-icon>
              </div>
              <div class="kb-item-info">
                <div class="kb-item-name">{{ kb.name }}</div>
                <div class="kb-item-meta">
                  <el-tag size="small" :type="kb.document_count > 0 ? 'success' : 'info'" effect="light">
                    {{ kb.document_count }} 个文档
                  </el-tag>
                </div>
              </div>
              <el-icon size="14" class="kb-item-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.home {
  padding: 0;
}

/* Welcome Header */
.welcome-header {
  margin-bottom: 24px;
}

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-heading);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.welcome-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 6px;
}

/* Stat Cards */
.stat-grid {
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
  width: 48px;
  height: 48px;
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
  background: linear-gradient(135deg, #f59e0b, #fbbf24);
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.25);
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-heading);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

/* Content Grid */
.content-grid {
  margin: 0 !important;
}

.content-grid .el-col {
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

/* Card Header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-heading);
}

.view-all-link {
  font-size: 13px;
  font-weight: 500;
}

/* Quick Actions */
.quick-actions-card {
  padding: 20px;
  height: 100%;
}

.quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.quick-action {
  text-align: center;
  padding: 24px 16px;
  border-radius: var(--rp-radius-lg);
  cursor: pointer;
  transition: all var(--rp-transition-base);
  background: var(--color-surface-muted);
  border: 1px solid transparent;
}

.quick-action:hover {
  background: var(--rp-primary-50);
  border-color: var(--rp-primary-200);
  transform: translateY(-3px);
  box-shadow: var(--rp-shadow-md);
}

.quick-action-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
  color: #fff;
}

.quick-action-icon.blue {
  background: linear-gradient(135deg, var(--rp-primary-500), var(--rp-primary-400));
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
}

.quick-action-icon.green {
  background: linear-gradient(135deg, var(--rp-success-500), #4ade80);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.25);
}

.quick-action-icon.purple {
  background: linear-gradient(135deg, #8b5cf6, #a78bfa);
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25);
}

.quick-action-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-heading);
  margin-bottom: 4px;
}

.quick-action-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
}

/* Recent Card */
.recent-card {
  padding: 20px;
  height: 100%;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 32px 16px;
}

.empty-icon {
  margin-bottom: 12px;
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-heading);
  margin-bottom: 4px;
}

.empty-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 16px;
}

/* KB List */
.kb-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--rp-radius-md);
  cursor: pointer;
  transition: all var(--rp-transition-fast);
  border: 1px solid transparent;
}

.kb-item:hover {
  background: var(--rp-primary-50);
  border-color: var(--rp-primary-200);
}

.kb-item-icon {
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

.kb-item-info {
  flex: 1;
  min-width: 0;
}

.kb-item-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-heading);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kb-item-meta {
  margin-top: 2px;
}

.kb-item-arrow {
  color: var(--color-text-tertiary);
  transition: transform var(--rp-transition-fast);
}

.kb-item:hover .kb-item-arrow {
  transform: translateX(3px);
  color: var(--rp-primary-500);
}

/* Responsive */
@media (max-width: 960px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .quick-actions-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
