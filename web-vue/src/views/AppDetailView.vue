<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { appApi, modelProviderApi } from '@/api'
import type { App, ModelProvider } from '@/types'

const route = useRoute()
const router = useRouter()
const app = ref<App | null>(null)
const providers = ref<ModelProvider[]>([])
const loading = ref(false)
const saving = ref(false)
const form = ref({
  name: '',
  description: '',
  provider: '',
  model: '',
})

const currentModels = computed(() => {
  const provider = providers.value.find(item => item.provider === form.value.provider)
  return provider?.models || []
})

const onProviderChange = () => {
  form.value.model = ''
}

const fetchData = async () => {
  loading.value = true
  try {
    const [appRes, providerRes] = await Promise.all([
      appApi.get(route.params.id as string),
      modelProviderApi.list(),
    ])
    app.value = appRes.data
    providers.value = providerRes.data.data
    form.value = {
      name: appRes.data.name || '',
      description: appRes.data.description || '',
      provider: appRes.data.provider || '',
      model: appRes.data.model || '',
    }
  } finally {
    loading.value = false
  }
}

const save = async () => {
  saving.value = true
  try {
    await appApi.update(route.params.id as string, form.value)
    ElMessage.success('应用配置已保存')
    await fetchData()
  } finally {
    saving.value = false
  }
}

const openChat = async () => {
  await router.push({ path: '/chat', query: { appId: route.params.id, provider: form.value.provider, model: form.value.model } })
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="app-detail-view" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <el-button text class="back-btn" @click="$router.push('/apps')">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div>
          <h1 class="page-title">{{ app?.name || '应用配置' }}</h1>
          <p class="page-subtitle">配置模型、描述与基础信息</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button size="large" text @click="openChat">
          <el-icon><ChatDotRound /></el-icon>
          进入聊天
        </el-button>
        <el-button size="large" type="primary" :loading="saving" @click="save">
          <el-icon><Check /></el-icon>
          保存配置
        </el-button>
      </div>
    </div>

    <!-- Form Card -->
    <div class="config-card surface-card">
      <div class="card-section">
        <h3 class="section-title">
          <el-icon class="section-icon"><InfoFilled /></el-icon>
          基本信息
        </h3>
        <el-form :model="form" label-width="120px" class="detail-form">
          <el-form-item label="应用名称">
            <el-input v-model="form.name" placeholder="应用名称" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="4" placeholder="描述一下这个应用的用途和场景" />
          </el-form-item>
        </el-form>
      </div>

      <div class="divider-soft" />

      <div class="card-section">
        <h3 class="section-title">
          <el-icon class="section-icon"><Cpu /></el-icon>
          模型设置
        </h3>
        <el-form :model="form" label-width="120px" class="detail-form">
          <el-form-item label="模型提供商">
            <el-select v-model="form.provider" style="width: 100%" placeholder="选择模型提供商" @change="onProviderChange">
              <el-option v-for="provider in providers" :key="provider.provider" :label="provider.label" :value="provider.provider" />
            </el-select>
          </el-form-item>
          <el-form-item label="模型">
            <el-select v-model="form.model" style="width: 100%" placeholder="选择模型">
              <el-option v-for="model in currentModels" :key="model.id" :label="model.name" :value="model.id" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-detail-view {
  padding: var(--page-padding);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  padding: 8px;
  font-size: 18px;
  color: var(--color-text-secondary);
}

.back-btn:hover {
  color: var(--color-text);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.config-card {
  padding: 28px 32px;
  max-width: 720px;
}

.card-section {
  padding: 8px 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0 0 20px 0;
}

.section-icon {
  color: var(--color-accent);
}

.detail-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--color-heading);
}

.divider-soft {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-border), transparent);
  margin: 24px 0;
}
</style>
