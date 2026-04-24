<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { componentConfigApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'

const components = ref<any[]>([])
const runtimeDataStore = ref('sqlite')
const loading = ref(false)
const testingId = ref<string | null>(null)

const {
  currentPage,
  total,
  paginatedItems: paginatedComponents,
  shouldPaginate,
  resetPagination,
} = useClientPagination(components, 12)

const fetchComponents = async () => {
  loading.value = true
  try {
    const response = await componentConfigApi.list()
    components.value = response.data.data || []
    runtimeDataStore.value = response.data.runtime_data_store || 'sqlite'
  } finally {
    loading.value = false
  }
}

const saveComponent = async (component: any) => {
  await componentConfigApi.update(component.id, {
    enabled: component.enabled,
    config: component.config,
  })
  ElMessage.success('组件配置已保存')
  await fetchComponents()
}

const testComponent = async (component: any) => {
  testingId.value = component.id
  try {
    const response = await componentConfigApi.test(component.id)
    if (response.data.result === 'success')
      ElMessage.success(response.data.message)
    else
      ElMessage.warning(response.data.message)
  } finally {
    testingId.value = null
  }
}

const categoryMeta: Record<string, { label: string; icon: string; color: string }> = {
  database: { label: '数据库', icon: 'Coin', color: 'var(--rp-primary-500)' },
  datastore: { label: '检索存储', icon: 'Coin', color: 'var(--rp-primary-500)' },
  vector_store: { label: '向量库', icon: 'DataLine', color: 'var(--rp-coral-500)' },
  retrieval: { label: '检索', icon: 'Search', color: 'var(--rp-success-500)' },
  storage: { label: '存储', icon: 'Folder', color: 'var(--rp-warning-500)' },
}

onMounted(() => {
  fetchComponents()
})

watch(components, () => {
  resetPagination()
})
</script>

<template>
  <div class="component-configs-view">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">组件配置</h1>
        <p class="page-subtitle">管理员维护数据库、向量库和检索后端连接</p>
      </div>
    </div>

    <!-- Runtime Alert -->
    <div class="runtime-alert surface-card">
      <el-icon class="alert-icon" size="20"><WarningFilled /></el-icon>
      <div class="alert-content">
        <strong>运行时存储后端：{{ runtimeDataStore }}</strong>
        <span>修改此页配置不会立即切换运行中服务，请同步部署环境变量并重启后端。</span>
      </div>
    </div>

    <div class="architecture-note surface-card">
      <strong>RAG 三层成本架构</strong>
      <span>轻量起步：SQLite 本地混合检索；团队标准：PostgreSQL + pgvector；企业增强：Elasticsearch 集群，后续可迁移 Qdrant/Milvus 专用向量库。MySQL 用于业务数据，不作为知识库向量检索后端。</span>
    </div>

    <!-- Component Cards Grid -->
    <div class="components-grid" v-loading="loading">
      <div
        v-for="component in paginatedComponents"
        :key="component.id"
        class="component-card surface-card"
      >
        <!-- Card Header -->
        <div class="component-header">
          <div class="component-info">
            <div
              class="component-icon"
              :style="{ background: (categoryMeta[component.category]?.color || 'var(--rp-primary-500)') + '15' }"
            >
              <el-icon
                size="20"
                :color="categoryMeta[component.category]?.color || 'var(--rp-primary-500)'"
              >
                <component :is="categoryMeta[component.category]?.icon || 'Setting'" />
              </el-icon>
            </div>
            <div class="component-title">
              <h3 class="component-name">{{ component.name }}</h3>
              <span class="component-id">{{ component.id }} · {{ component.category }}</span>
            </div>
          </div>
          <el-tag
            :type="component.active ? 'success' : 'info'"
            size="small"
            effect="light"
          >
            {{ component.active ? '运行中' : '未运行' }}
          </el-tag>
        </div>

        <!-- Config Form -->
        <div class="component-form">
          <el-form label-width="110px">
            <el-form-item label="启用记录">
              <el-switch v-model="component.enabled" />
            </el-form-item>
            <template v-for="(_, key) in component.config" :key="key">
              <el-form-item :label="String(key)">
                <el-input
                  v-model="component.config[key]"
                  :type="String(key).includes('password') ? 'password' : 'text'"
                  show-password
                  :placeholder="String(key)"
                />
              </el-form-item>
            </template>
          </el-form>
        </div>

        <!-- Runtime Note -->
        <p v-if="component.runtime_note" class="runtime-note">
          <el-icon size="14"><InfoFilled /></el-icon>
          {{ component.runtime_note }}
        </p>

        <!-- Env Keys -->
        <div v-if="component.env_keys?.length" class="env-keys">
          <span class="env-label">环境变量：</span>
          <el-tag
            v-for="key in component.env_keys"
            :key="key"
            size="small"
            effect="plain"
          >
            {{ key }}
          </el-tag>
        </div>

        <!-- Actions -->
        <div class="component-actions">
          <el-button
            size="small"
            text
            :loading="testingId === component.id"
            @click="testComponent(component)"
          >
            <el-icon><Connection /></el-icon> 测试连接
          </el-button>
          <el-button size="small" type="primary" @click="saveComponent(component)">
            <el-icon><Check /></el-icon> 保存
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
  </div>
</template>

<style scoped>
.component-configs-view {
  padding: var(--page-padding);
}

.runtime-alert {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 18px;
  margin-bottom: var(--page-gap);
  border-left: 3px solid var(--rp-warning-500);
}

.architecture-note {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 18px;
  margin-bottom: var(--page-gap);
}

.architecture-note strong {
  color: var(--color-heading);
  font-size: 14px;
}

.architecture-note span {
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.alert-icon {
  color: var(--rp-warning-500);
  flex-shrink: 0;
  margin-top: 2px;
}

.alert-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.alert-content strong {
  font-size: 14px;
  color: var(--color-heading);
}

.alert-content span {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.components-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--page-gap);
}

@media (max-width: 640px) {
  .components-grid {
    grid-template-columns: 1fr;
  }
}

.component-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.component-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.component-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.component-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.component-title {
  flex: 1;
}

.component-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0 0 2px 0;
}

.component-id {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-family: monospace;
}

.component-form {
  padding-top: 8px;
}

.component-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--color-text-secondary);
}

.runtime-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0;
  padding: 10px 12px;
  background: var(--rp-info-50);
  border-radius: var(--rp-radius-md);
  font-size: 12px;
  color: var(--rp-info-500);
  line-height: 1.5;
}

.runtime-note .el-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

.env-keys {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.env-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.component-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border-light);
}
</style>
