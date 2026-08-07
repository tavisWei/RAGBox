<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { componentConfigApi, storageApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'

const components = ref<any[]>([])
const runtimeDataStore = ref('sqlite')
const loading = ref(false)
const testingId = ref<string | null>(null)

// Storage management state
const businessStore = ref<any>({ type: 'local', namespaces: [] })
const activeVectorStore = ref<any>(null)
const mysqlForm = ref({ host: 'localhost', port: 3306, database: 'rag_platform', user: 'root', password: '' })
const migrating = ref(false)
const testingBusiness = ref(false)
const vectorSwitchTarget = ref('')
const switchingVector = ref(false)

const fetchStorage = async () => {
  try {
    const response = await storageApi.status()
    businessStore.value = response.data.business_store || { type: 'local', namespaces: [] }
    activeVectorStore.value = response.data.vector_store
  }
  catch {
    // 非管理员或无权限时忽略，存储管理卡片保持默认展示
  }
}

const testBusinessStore = async () => {
  testingBusiness.value = true
  try {
    await storageApi.testBusiness({ type: 'mysql', config: mysqlForm.value })
    ElMessage.success('MySQL 连接测试通过')
  }
  catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'MySQL 连接失败')
  }
  finally {
    testingBusiness.value = false
  }
}

const migrateBusinessStore = async (target: string) => {
  const action = target === 'mysql' ? '迁移到 MySQL 并切换' : '迁回本地 JSON 存储'
  try {
    await ElMessageBox.confirm(
      `将把全部业务数据（用户、会话、应用、知识库配置等 ${businessStore.value.namespaces?.length || 0} 个命名空间）${action}。迁移完成并逐条校验后才会切换，源数据保留可回退。是否继续？`,
      '业务数据库迁移',
      { type: 'warning', confirmButtonText: '迁移并切换', cancelButtonText: '取消' },
    )
  }
  catch {
    return
  }
  migrating.value = true
  try {
    const config = target === 'mysql' ? mysqlForm.value : {}
    const response = await storageApi.migrateBusiness({ type: target, config })
    ElMessage.success(`已切换业务存储：${response.data.from} → ${response.data.to}（${response.data.namespaces.length} 个命名空间）`)
    await fetchStorage()
  }
  catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '迁移失败，未切换')
  }
  finally {
    migrating.value = false
  }
}

const switchVectorStore = async () => {
  if (!vectorSwitchTarget.value) {
    ElMessage.warning('请选择目标向量后端')
    return
  }
  try {
    await ElMessageBox.confirm(
      '向量数据不会跨后端迁移。切换后，已有知识库的训练素材（文档）需要重新导入以在新后端重建索引。是否继续？',
      '切换向量后端',
      { type: 'warning', confirmButtonText: '直接切换', cancelButtonText: '取消' },
    )
  }
  catch {
    return
  }
  switchingVector.value = true
  try {
    const response = await storageApi.switchVector(vectorSwitchTarget.value)
    ElMessage.success(response.data.message || '向量后端已切换')
    await fetchStorage()
    await fetchComponents()
  }
  catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '切换失败')
  }
  finally {
    switchingVector.value = false
  }
}

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
  fetchStorage()
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
        <strong>运行时向量后端：{{ activeVectorStore?.data_store_type || runtimeDataStore }}</strong>
        <span>启用的数据存储组件即为全局生效的检索后端；知识库级配置与环境变量 DATA_STORE_TYPE 优先级更高。</span>
      </div>
    </div>

    <!-- Storage Management -->
    <div class="surface-card section-card storage-card">
      <div class="section-header">
        <div class="section-title">
          <el-icon size="18" class="text-accent"><Folder /></el-icon>
          <span>存储管理</span>
        </div>
      </div>
      <div class="storage-grid">
        <div class="storage-block">
          <div class="storage-title">业务数据库（当前：{{ businessStore.type === 'mysql' ? 'MySQL' : '本地 JSON' }}）</div>
          <div class="storage-desc">用户、会话、应用、知识库配置等业务数据。迁移会先复制并逐条校验，成功后才切换，源数据保留可回退。</div>
          <template v-if="businessStore.type !== 'mysql'">
            <el-form label-width="80px" size="small">
              <el-form-item label="主机/端口">
                <div style="display: flex; gap: 8px; width: 100%">
                  <el-input v-model="mysqlForm.host" style="flex: 1" />
                  <el-input-number v-model="mysqlForm.port" :min="1" :max="65535" style="width: 120px" />
                </div>
              </el-form-item>
              <el-form-item label="数据库名">
                <el-input v-model="mysqlForm.database" />
              </el-form-item>
              <el-form-item label="账号">
                <el-input v-model="mysqlForm.user" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input v-model="mysqlForm.password" type="password" show-password />
              </el-form-item>
            </el-form>
            <div class="storage-actions">
              <el-button size="small" :loading="testingBusiness" @click="testBusinessStore">测试连接</el-button>
              <el-button size="small" type="primary" :loading="migrating" @click="migrateBusinessStore('mysql')">迁移并切换到 MySQL</el-button>
            </div>
          </template>
          <template v-else>
            <div class="storage-actions">
              <el-button size="small" :loading="migrating" @click="migrateBusinessStore('local')">迁回本地 JSON 存储</el-button>
            </div>
          </template>
        </div>
        <div class="storage-block">
          <div class="storage-title">向量 / 检索后端（当前：{{ activeVectorStore?.data_store_type || runtimeDataStore }}）</div>
          <div class="storage-desc">向量数据不跨后端迁移；切换后各知识库会标记"需重建索引"，训练素材需重新导入。</div>
          <div class="storage-actions">
            <el-select v-model="vectorSwitchTarget" placeholder="选择目标后端" size="small" style="width: 220px">
              <el-option label="SQLite（本地内置）" value="sqlite" />
              <el-option label="PostgreSQL + pgvector" value="pgvector" />
              <el-option label="Elasticsearch" value="elasticsearch" />
              <el-option label="Qdrant" value="qdrant" />
              <el-option label="Milvus" value="milvus" />
              <el-option label="MySQL" value="mysql" />
            </el-select>
            <el-button size="small" type="primary" :loading="switchingVector" @click="switchVectorStore">切换</el-button>
          </div>
          <div class="storage-desc">提示：目标后端的连接参数请先在下方对应组件卡片中填写并保存。</div>
        </div>
      </div>
    </div>

    <div class="architecture-note surface-card">
      <strong>RAG 三层成本架构</strong>
      <span>轻量起步：SQLite 本地混合检索；团队标准：PostgreSQL + pgvector；企业增强：Elasticsearch 集群，亦可选用 Qdrant/Milvus 专用向量库或 MySQL（中小规模）。</span>
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

.storage-card {
  padding: 14px 18px;
  margin-bottom: var(--page-gap);
}

.section-header {
  margin-bottom: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.storage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
}

.storage-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.storage-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 10px;
  line-height: 1.5;
}

.storage-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
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
