<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleCheck,
  CircleCheckFilled,
  Connection,
  Delete,
  Edit,
  Key,
  Plus,
} from '@element-plus/icons-vue'
import { modelProviderApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'
import type { ModelProvider, ModelProviderCredential, ProviderModel } from '@/types'

type CredentialFormKey = 'name' | 'api_key' | 'base_url'

const providers = ref<ModelProvider[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const providerDialogVisible = ref(false)
const modelDialogVisible = ref(false)
const currentProvider = ref<ModelProvider | null>(null)
const editingCredentialId = ref('')
const editingProviderKey = ref('')
const editingModelName = ref('')
const credentialForm = ref({
  name: '',
  api_key: '',
  base_url: '',
})
const providerForm = ref({
  provider: '',
  label: '',
  credentialName: '默认凭证',
  api_key: '',
  base_url: '',
  supports_validate: true,
})
const modelForm = ref({ model_id: '', name: '' })
const validating = ref(false)
const credentialPages = reactive<Record<string, number>>({})

const credentialDialogTitle = computed(() => editingCredentialId.value ? '编辑凭证' : '新增模型凭证')
const providerDialogTitle = computed(() => editingProviderKey.value ? '编辑提供商' : '新增提供商')
const modelDialogTitle = computed(() => editingModelName.value ? '编辑模型' : '新增模型')

const {
  currentPage,
  total,
  paginatedItems: paginatedProviders,
  shouldPaginate,
  resetPagination,
} = useClientPagination(providers, 8)

const fetchProviders = async () => {
  loading.value = true
  try {
    const response = await modelProviderApi.list()
    providers.value = response.data.data
    for (const provider of response.data.data) {
      credentialPages[provider.provider] = 1
    }
  } finally {
    loading.value = false
  }
}

const openCreate = (provider: ModelProvider) => {
  currentProvider.value = provider
  editingCredentialId.value = ''
  credentialForm.value = { name: '', api_key: '', base_url: '' }
  dialogVisible.value = true
}

const openEditCredential = (provider: ModelProvider, credential: ModelProviderCredential) => {
  currentProvider.value = provider
  editingCredentialId.value = credential.id
  credentialForm.value = {
    name: credential.name,
    api_key: typeof credential.credentials.api_key === 'string' && credential.credentials.api_key !== '********' ? credential.credentials.api_key : '',
    base_url: typeof credential.credentials.base_url === 'string' ? credential.credentials.base_url : '',
  }
  dialogVisible.value = true
}

const openProviderCreate = () => {
  editingProviderKey.value = ''
  providerForm.value = {
    provider: '',
    label: '',
    credentialName: '默认凭证',
    api_key: '',
    base_url: '',
    supports_validate: true,
  }
  providerDialogVisible.value = true
}

const openProviderEdit = (provider: ModelProvider) => {
  editingProviderKey.value = provider.provider
    providerForm.value = {
      provider: provider.provider,
      label: provider.label,
      credentialName: '默认凭证',
      api_key: '',
      base_url: '',
      supports_validate: provider.supports_validate,
    }
  providerDialogVisible.value = true
}

const openModelCreate = (provider: ModelProvider) => {
  currentProvider.value = provider
  editingModelName.value = ''
  modelForm.value = { model_id: '', name: '' }
  modelDialogVisible.value = true
}

const openModelEdit = (provider: ModelProvider, model: ProviderModel) => {
  currentProvider.value = provider
  editingModelName.value = model.id
  modelForm.value = { model_id: model.id, name: model.name }
  modelDialogVisible.value = true
}

const validateCredential = async () => {
  if (!currentProvider.value) return
  validating.value = true
  try {
    const payload: Record<string, string> = {}
    currentProvider.value.fields.forEach((field) => {
      payload[field] = credentialForm.value[field as CredentialFormKey]
    })
    const response = await modelProviderApi.validateCredential(currentProvider.value.provider, { credentials: payload })
    if (response.data.result === 'success')
      ElMessage.success('校验通过')
    else
      ElMessage.error(response.data.error || '校验失败')
  } finally {
    validating.value = false
  }
}

const saveCredential = async () => {
  if (!currentProvider.value) return
  const payload: Record<string, string> = {}
  currentProvider.value.fields.forEach((field) => {
    payload[field] = credentialForm.value[field as CredentialFormKey]
  })
  if (editingCredentialId.value) {
    await modelProviderApi.updateCredential(currentProvider.value.provider, {
      credential_id: editingCredentialId.value,
      name: credentialForm.value.name,
      credentials: payload,
    })
  }
  else {
    await modelProviderApi.createCredential(currentProvider.value.provider, {
      name: credentialForm.value.name,
      credentials: payload,
    })
  }
  ElMessage.success('保存成功')
  dialogVisible.value = false
  await fetchProviders()
}

const saveProvider = async () => {
  if (!providerForm.value.label.trim()) {
    ElMessage.warning('请填写提供商名称')
    return
  }
  if (editingProviderKey.value) {
    const existingProvider = providers.value.find(item => item.provider === editingProviderKey.value)
    await modelProviderApi.updateProvider(editingProviderKey.value, {
      label: providerForm.value.label,
      models: existingProvider?.models || [],
      fields: ['api_key', 'base_url'],
      supports_validate: providerForm.value.supports_validate,
    })
  }
  else {
    if (!providerForm.value.provider.trim()) {
      ElMessage.warning('请填写提供商标识')
      return
    }
    if (!providerForm.value.api_key.trim() && !providerForm.value.base_url.trim()) {
      ElMessage.warning('请至少填写 API Key 或 Base URL')
      return
    }
    await modelProviderApi.createProvider({
      provider: providerForm.value.provider,
      label: providerForm.value.label,
      models: [],
      fields: ['api_key', 'base_url'],
      supports_validate: providerForm.value.supports_validate,
      credential_name: providerForm.value.credentialName || undefined,
      credentials: {
        api_key: providerForm.value.api_key,
        base_url: providerForm.value.base_url,
      },
    })
  }
  ElMessage.success('保存成功')
  providerDialogVisible.value = false
  await fetchProviders()
}

const saveModel = async () => {
  if (!currentProvider.value || !modelForm.value.model_id.trim() || !modelForm.value.name.trim()) return
  if (editingModelName.value) {
    await modelProviderApi.updateModel(currentProvider.value.provider, {
      old_model_id: editingModelName.value,
      model_id: modelForm.value.model_id,
      name: modelForm.value.name,
    })
  }
  else {
    await modelProviderApi.createModel(currentProvider.value.provider, { model_id: modelForm.value.model_id, name: modelForm.value.name })
  }
  ElMessage.success('模型已保存')
  modelDialogVisible.value = false
  await fetchProviders()
}

const deleteProvider = async (provider: ModelProvider) => {
  await ElMessageBox.confirm(`确定删除提供商「${provider.label}」吗？`, '删除提供商', { type: 'warning' })
  await modelProviderApi.deleteProvider(provider.provider)
  ElMessage.success('删除成功')
  await fetchProviders()
}

const deleteModel = async (provider: ModelProvider, model: ProviderModel) => {
  await ElMessageBox.confirm(`确定删除模型「${model.name}」吗？`, '删除模型', { type: 'warning' })
  await modelProviderApi.deleteModel(provider.provider, { model_id: model.id, name: model.name })
  ElMessage.success('删除成功')
  await fetchProviders()
}

const deleteCredential = async (provider: ModelProvider, credentialId: string) => {
  await ElMessageBox.confirm('确定删除该凭证吗？', '删除凭证', { type: 'warning' })
  await modelProviderApi.deleteCredential(provider.provider, { credential_id: credentialId })
  ElMessage.success('删除成功')
  await fetchProviders()
}

const switchCredential = async (provider: string, credentialId: string) => {
  await modelProviderApi.switchCredential(provider, { credential_id: credentialId })
  ElMessage.success('已切换为当前凭证')
  await fetchProviders()
}

const setDefaultModel = async (provider: string, model: string) => {
  await modelProviderApi.setDefaultModel(provider, { model })
  ElMessage.success('默认模型已更新')
  await fetchProviders()
}

const onModelChange = async (providerKey: string, value: string | number | boolean) => {
  await setDefaultModel(providerKey, String(value))
}

const getCredentialPage = (providerKey: string) => credentialPages[providerKey] || 1

const getVisibleCredentials = (provider: ModelProvider) => {
  const page = getCredentialPage(provider.provider)
  const start = (page - 1) * 5
  return (provider.credentials || []).slice(start, start + 5)
}

const hasMoreCredentials = (provider: ModelProvider) => {
  return (provider.credentials || []).length > 5
}

const getCredentialTotal = (provider: ModelProvider) => {
  return (provider.credentials || []).length
}

onMounted(() => {
  fetchProviders()
})

watch(providers, () => {
  resetPagination()
})
</script>

<template>
  <div class="providers-view">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">模型提供商</h1>
        <p class="page-subtitle">管理 AI 模型提供商的凭证和默认模型配置</p>
      </div>
      <el-button type="primary" @click="openProviderCreate">
        <el-icon><Plus /></el-icon>
        新增提供商
      </el-button>
    </div>

    <!-- Provider Cards Grid -->
    <div v-if="!loading && !providers.length" class="providers-empty surface-card">
      <el-icon size="28" color="var(--rp-gray-300)"><Connection /></el-icon>
      <div class="providers-empty-title">暂无模型提供商</div>
      <div class="providers-empty-desc">当前为完全空白状态，请点击右上角“新增提供商”手动添加。</div>
      <el-button type="primary" @click="openProviderCreate">
        <el-icon><Plus /></el-icon>
        新增提供商
      </el-button>
    </div>

    <div v-else class="providers-grid">
      <div
        v-for="provider in paginatedProviders"
        :key="provider.provider"
        class="provider-card surface-card"
        v-loading="loading"
      >
        <!-- Card Header -->
        <div class="provider-header">
          <div class="provider-info">
            <div class="provider-icon">
              <el-icon size="24" color="var(--color-accent)"><Connection /></el-icon>
            </div>
            <div class="provider-title">
              <h3 class="provider-name">{{ provider.label }}</h3>
              <span class="provider-key">{{ provider.provider }}</span>
            </div>
          </div>
          <div class="provider-actions">
            <el-button type="primary" size="small" @click="openModelCreate(provider)">
              <el-icon><Plus /></el-icon> 新增模型
            </el-button>
            <el-button v-if="provider.editable !== false" size="small" text @click="openProviderEdit(provider)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button v-if="provider.editable !== false" size="small" text type="danger" @click="deleteProvider(provider)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>

        <div class="provider-section">
          <div class="section-header">
            <label class="section-label">模型列表</label>
          </div>
          <div class="model-list">
            <el-tag v-for="item in provider.models" :key="item.id" class="model-tag" effect="plain">
              <span>{{ item.name }}</span>
              <el-button size="small" text @click="openModelEdit(provider, item)"><el-icon><Edit /></el-icon></el-button>
              <el-button size="small" text type="danger" @click="deleteModel(provider, item)"><el-icon><Delete /></el-icon></el-button>
            </el-tag>
          </div>
        </div>

        <!-- Default Model -->
        <div class="provider-section">
          <label class="section-label">默认模型</label>
          <el-select
            :model-value="provider.default_model || ''"
            placeholder="选择默认模型"
            style="width: 100%"
            @change="(value: string | number | boolean) => onModelChange(provider.provider, value)"
          >
            <el-option
              v-for="model in provider.models"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
        </div>

        <!-- Credentials Table -->
        <div class="provider-section">
          <label class="section-label">凭证列表</label>

          <div v-if="provider.credentials?.length" class="credentials-list">
            <div
              v-for="cred in getVisibleCredentials(provider)"
              :key="cred.id"
              class="credential-item"
              :class="{ active: provider.active_credential_id === cred.id }"
            >
              <div class="credential-info">
                <el-icon v-if="provider.active_credential_id === cred.id" class="active-dot" size="12"><CircleCheckFilled /></el-icon>
                <span class="credential-name">{{ cred.name }}</span>
              </div>
              <div class="credential-actions">
                <el-tag
                  v-if="provider.active_credential_id === cred.id"
                  type="success"
                  size="small"
                >
                  启用中
                </el-tag>
                <el-tag v-else type="info" size="small">备用</el-tag>
                <el-button
                  v-if="provider.active_credential_id !== cred.id"
                  size="small"
                  text
                  @click="switchCredential(provider.provider, cred.id)"
                >
                  启用
                </el-button>
                <el-button size="small" text @click="openEditCredential(provider, cred)">
                  编辑
                </el-button>
                <el-button size="small" text type="danger" @click="deleteCredential(provider, cred.id)">
                  删除
                </el-button>
              </div>
            </div>

            <div v-if="hasMoreCredentials(provider)" class="credentials-pagination">
              <el-pagination
                :current-page="getCredentialPage(provider.provider)"
                :total="getCredentialTotal(provider)"
                :page-size="5"
                size="small"
                layout="prev, pager, next"
                :hide-on-single-page="true"
                @update:current-page="credentialPages[provider.provider] = $event"
              />
            </div>
          </div>

          <div v-else class="credentials-empty">
            <el-icon size="20" color="var(--rp-gray-300)"><Key /></el-icon>
            <span>暂无凭证，请先在顶部新增提供商时填写，或稍后补充凭证</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="shouldPaginate && !loading" class="page-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :total="total"
        :page-size="8"
        background
        layout="prev, pager, next"
        :hide-on-single-page="true"
      />
    </div>

    <!-- Create Credential Dialog -->
    <el-dialog v-model="providerDialogVisible" :title="providerDialogTitle" width="560px">
      <el-form :model="providerForm" label-width="110px">
        <el-form-item label="提供商标识">
          <el-input v-model="providerForm.provider" :disabled="!!editingProviderKey" placeholder="例如 openai-compatible" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="providerForm.label" placeholder="例如 私有 OpenAI 兼容服务" />
        </el-form-item>
        <template v-if="!editingProviderKey">
          <el-form-item label="凭证名称">
            <el-input v-model="providerForm.credentialName" placeholder="例如 默认凭证" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="providerForm.api_key" placeholder="新增提供商时直接填写 API Key" show-password />
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="providerForm.base_url" placeholder="例如 https://api.openai.com/v1" />
          </el-form-item>
        </template>
        <el-form-item label="支持校验">
          <el-switch v-model="providerForm.supports_validate" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="providerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProvider">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="modelDialogVisible" :title="modelDialogTitle" width="420px">
      <el-form :model="modelForm" label-width="90px">
        <el-form-item label="模型 ID">
          <el-input v-model="modelForm.model_id" placeholder="例如 gpt-4o-mini" />
        </el-form-item>
        <el-form-item label="模型名字">
          <el-input v-model="modelForm.name" placeholder="例如 GPT-4o Mini" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveModel">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :title="credentialDialogTitle" width="520px">
      <div v-if="currentProvider" class="dialog-provider-info">
        <el-icon size="20" color="var(--color-accent)"><Connection /></el-icon>
        <span>{{ currentProvider.label }}</span>
      </div>

      <el-form :model="credentialForm" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="credentialForm.name" placeholder="给凭证起个名字" />
        </el-form-item>
        <el-form-item v-if="currentProvider?.fields.includes('api_key')" label="API Key">
          <el-input
            v-model="credentialForm.api_key"
            type="password"
            show-password
            placeholder="输入 API Key"
          />
        </el-form-item>
        <el-form-item v-if="currentProvider?.fields.includes('base_url')" label="Base URL">
          <el-input v-model="credentialForm.base_url" placeholder="https://api.example.com" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button :loading="validating" @click="validateCredential">
          <el-icon><CircleCheck /></el-icon> 校验连接
        </el-button>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCredential">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.providers-view {
  padding: var(--page-padding);
}

.providers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: var(--page-gap);
}

.providers-empty {
  padding: 40px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
}

.providers-empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--rp-gray-900);
}

.providers-empty-desc {
  max-width: 520px;
  color: var(--rp-gray-500);
}

@media (max-width: 640px) {
  .providers-grid {
    grid-template-columns: 1fr;
  }
}

.provider-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.provider-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.provider-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.provider-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--rp-radius-md);
  background: var(--rp-primary-50);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.provider-title {
  flex: 1;
}

.provider-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0 0 2px 0;
}

.provider-key {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-family: monospace;
}

.provider-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.model-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.model-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: auto;
  padding: 4px 6px;
}

.credentials-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.credential-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  border: 1px solid transparent;
  transition: all var(--rp-transition-fast);
}

.credential-item.active {
  background: var(--rp-success-50);
  border-color: var(--rp-success-200);
}

.credential-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.active-dot {
  color: var(--rp-success-500);
}

.credential-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
}

.credential-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.credentials-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  font-size: 13px;
  color: var(--color-text-secondary);
}

.credentials-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.dialog-provider-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--rp-primary-50);
  border-radius: var(--rp-radius-md);
  margin-bottom: 20px;
  font-weight: 500;
  color: var(--color-heading);
}
</style>
