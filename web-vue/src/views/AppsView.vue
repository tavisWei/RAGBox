<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { appApi, modelProviderApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'
import type { App, ModelProvider } from '@/types'

const apps = ref<App[]>([])
const providers = ref<ModelProvider[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const form = ref({
  name: '',
  mode: 'chat',
  description: '',
  provider: '',
  model: '',
})

const {
  currentPage,
  total,
  paginatedItems: paginatedApps,
  shouldPaginate,
  resetPagination,
} = useClientPagination(apps, 12)

const currentModels = computed(() => {
  const provider = providers.value.find(item => item.provider === form.value.provider)
  return provider?.models || []
})

const onProviderChange = () => {
  form.value.model = ''
}

const fetchApps = async () => {
  loading.value = true
  try {
    const response = await appApi.list()
    apps.value = response.data
  } finally {
    loading.value = false
  }
}

const fetchProviders = async () => {
  const response = await modelProviderApi.list()
  providers.value = response.data.data
}

const handleCreate = async () => {
  try {
    await appApi.create(form.value)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    form.value = { name: '', mode: 'chat', description: '', provider: '', model: '' }
    fetchApps()
  } catch (_err) {
    ElMessage.error('创建失败')
  }
}

const handleDelete = async (app: App) => {
  try {
    await appApi.delete(app.id)
    ElMessage.success('删除成功')
    fetchApps()
  } catch (_err) {
    ElMessage.error('删除失败')
  }
}

const modeMeta: Record<string, { label: string; icon: string; color: string }> = {
  chat: { label: '对话', icon: 'ChatRound', color: 'var(--rp-primary-500)' },
  agent: { label: '智能体', icon: 'Cpu', color: 'var(--rp-coral-500)' },
}

onMounted(() => {
  fetchApps()
  fetchProviders()
})

watch(apps, () => {
  resetPagination()
})
</script>

<template>
  <div class="apps-view">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">应用管理</h1>
        <p class="page-subtitle">创建、配置和管理你的 AI 应用</p>
      </div>
      <el-button type="primary" size="large" class="create-btn" @click="dialogVisible = true">
        <el-icon class="btn-icon"><Plus /></el-icon>
        创建应用
      </el-button>
    </div>

    <!-- App Grid -->
    <div v-loading="loading" class="app-grid">
      <div
        v-for="app in paginatedApps"
        :key="app.id"
        class="app-card surface-card surface-card-hover"
      >
        <div class="app-card-header">
          <div class="app-avatar" :style="{ background: modeMeta[app.mode]?.color || 'var(--rp-primary-500)' }">
            <el-icon size="20" color="#fff">
              <component :is="modeMeta[app.mode]?.icon || 'ChatRound'" />
            </el-icon>
          </div>
          <div class="app-title-wrap">
            <h3 class="app-name">{{ app.name }}</h3>
            <el-tag size="small" :style="{ color: modeMeta[app.mode]?.color, background: modeMeta[app.mode]?.color + '15', borderColor: modeMeta[app.mode]?.color + '30' }">
              {{ modeMeta[app.mode]?.label || app.mode }}
            </el-tag>
          </div>
          <el-dropdown trigger="click" placement="bottom-end">
            <el-button text class="app-menu-btn">
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$router.push(`/apps/${app.id}`)">
                  <el-icon><Setting /></el-icon> 配置
                </el-dropdown-item>
                <el-dropdown-item @click="$router.push({ path: '/chat', query: { appId: app.id, provider: app.provider, model: app.model } })">
                  <el-icon><ChatDotRound /></el-icon> 使用
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleDelete(app)">
                  <el-icon><Delete /></el-icon> 删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <p v-if="app.description" class="app-desc">{{ app.description }}</p>
        <p v-else class="app-desc empty">暂无描述</p>

        <div class="app-meta">
          <span v-if="app.provider" class="meta-chip">
            <el-icon size="12"><Connection /></el-icon>
            {{ app.provider }}
          </span>
          <span v-if="app.model" class="meta-chip">
            <el-icon size="12"><Box /></el-icon>
            {{ app.model }}
          </span>
        </div>

        <div class="app-actions">
          <el-button size="small" text @click="$router.push(`/apps/${app.id}`)">
            <el-icon><Setting /></el-icon> 配置
          </el-button>
          <el-button size="small" type="primary" @click="$router.push({ path: '/chat', query: { appId: app.id, provider: app.provider, model: app.model } })">
            <el-icon><ChatDotRound /></el-icon> 使用
          </el-button>
        </div>
      </div>
    </div>

    <div v-if="shouldPaginate && !loading" class="page-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :total="total"
        :page-size="12"
        background
        layout="prev, pager, next"
        :hide-on-single-page="true"
      />
    </div>

    <!-- Empty State -->
    <div v-if="apps.length === 0 && !loading" class="empty-state">
      <div class="empty-illustration">
        <el-icon size="64" color="var(--rp-gray-300)"><Collection /></el-icon>
      </div>
      <h3 class="empty-title">还没有应用</h3>
      <p class="empty-desc">点击右上角按钮创建你的第一个 AI 应用</p>
      <el-button type="primary" @click="dialogVisible = true">
        <el-icon><Plus /></el-icon> 创建应用
      </el-button>
    </div>

    <!-- Create Dialog -->
    <el-dialog v-model="dialogVisible" title="创建应用" width="520px" class="app-dialog">
      <el-form :model="form" label-width="100px" class="app-form">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="给应用起个名字" />
        </el-form-item>
        <el-form-item label="模式">
          <el-select v-model="form.mode" style="width: 100%">
            <el-option label="对话" value="chat" />
            <el-option label="智能体" value="agent" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="简单描述一下这个应用的用途" />
        </el-form-item>
        <el-form-item label="模型提供商">
          <el-select v-model="form.provider" style="width: 100%" placeholder="请选择模型提供商" @change="onProviderChange">
            <el-option v-for="provider in providers" :key="provider.provider" :label="provider.label" :value="provider.provider" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="form.model" style="width: 100%" placeholder="请选择模型">
            <el-option v-for="model in currentModels" :key="model.id" :label="model.name" :value="model.id" />
          </el-select>
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
.apps-view {
  padding: var(--page-padding);
}

.create-btn {
  border-radius: var(--rp-radius-md);
  padding: 10px 20px;
  font-weight: 600;
}

.btn-icon {
  margin-right: 6px;
}

.app-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--page-gap);
}

.app-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.app-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.app-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.app-title-wrap {
  flex: 1;
  min-width: 0;
}

.app-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0 0 6px 0;
  line-height: 1.3;
}

.app-menu-btn {
  padding: 6px;
  color: var(--color-text-tertiary);
}

.app-menu-btn:hover {
  color: var(--color-text);
}

.app-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 0;
  min-height: 20px;
}

.app-desc.empty {
  color: var(--color-text-tertiary);
  font-style: italic;
}

.app-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border-light);
  border-radius: var(--rp-radius-sm);
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.app-actions {
  display: flex;
  gap: 8px;
  padding-top: 4px;
  border-top: 1px solid var(--color-border-light);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}

.empty-illustration {
  width: 120px;
  height: 120px;
  border-radius: var(--rp-radius-xl);
  background: var(--color-surface-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0 0 8px 0;
}

.empty-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 20px 0;
}

.app-form :deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
