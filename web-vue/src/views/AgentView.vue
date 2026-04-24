<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi, modelProviderApi, promptApi } from '@/api'
import type { ModelProvider } from '@/types'

const query = ref('')
const systemPrompt = ref('你是一个 helpful 的助手。')
const result = ref('')
const loading = ref(false)
const provider = ref('')
const model = ref('')
const providers = ref<ModelProvider[]>([])
const promptTemplates = ref<any[]>([])
const promptTemplateId = ref('')

const currentModels = computed(() => {
  const current = providers.value.find(item => item.provider === provider.value)
  return current?.models || []
})

const fetchProviders = async () => {
  const response = await modelProviderApi.list()
  providers.value = response.data.data
}

const fetchPromptTemplates = async () => {
  const response = await promptApi.listTemplates()
  promptTemplates.value = response.data.data || []
}

const onProviderChange = () => {
  model.value = ''
}

const applyPromptTemplate = () => {
  const selected = promptTemplates.value.find(item => item.id === promptTemplateId.value)
  if (!selected) return
  systemPrompt.value = selected.template
}

const runAgent = async () => {
  if (!query.value.trim()) return
  if (!provider.value) {
    ElMessage.warning('请选择模型提供商或先添加供应商')
    return
  }
  if (!model.value) {
    ElMessage.warning('请选择要调用的模型')
    return
  }

  loading.value = true
  result.value = ''

  try {
    const response = await agentApi.run({
      query: query.value,
      system_prompt: systemPrompt.value,
      max_iterations: 5,
      provider: provider.value || undefined,
      model: model.value || undefined,
    })
    result.value = response.data.answer
  } catch {
    ElMessage.error('执行失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchProviders()
  fetchPromptTemplates()
})
</script>

<template>
  <div class="agent">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-icon-wrap">
          <el-icon size="24" color="var(--rp-primary-500)"><Cpu /></el-icon>
        </div>
        <div class="header-text">
          <h2>智能体</h2>
          <p>配置系统提示词与模型，运行自定义 AI 智能体</p>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="agent-workspace">
      <!-- Configuration Panel -->
      <div class="panel config-panel">
        <div class="panel-header">
          <div class="panel-badge">
            <el-icon size="14"><Setting /></el-icon>
          </div>
          <div class="panel-title">配置</div>
          <div class="panel-subtitle">设置模型与提示词</div>
        </div>

        <div class="panel-body">
          <div class="form-section">
            <div class="section-label">
              <span class="section-dot blue"></span>
              模型选择
            </div>
            <div class="form-row">
              <el-form-item label="提供商" class="compact-form-item">
                <el-select v-model="provider" style="width: 100%" clearable placeholder="选择模型提供商" @change="onProviderChange">
                  <el-option v-for="item in providers" :key="item.provider" :label="item.label" :value="item.provider" />
                </el-select>
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="模型" class="compact-form-item">
                <el-select v-model="model" style="width: 100%" clearable placeholder="选择模型">
                  <el-option v-for="item in currentModels" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
              </el-form-item>
            </div>
          </div>

          <div class="divider-soft"></div>

          <div class="form-section">
            <div class="section-label">
              <span class="section-dot coral"></span>
              提示词
            </div>
            <div class="form-row">
              <el-form-item label="提示词模板" class="compact-form-item">
                <el-select v-model="promptTemplateId" style="width: 100%" clearable placeholder="选择提示词模板（可选）" @change="applyPromptTemplate">
                  <el-option v-for="item in promptTemplates" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="系统提示词" class="compact-form-item">
                <el-input
                  v-model="systemPrompt"
                  type="textarea"
                  :rows="5"
                  placeholder="输入系统提示词，定义智能体的行为与角色..."
                />
              </el-form-item>
            </div>
          </div>

          <div class="divider-soft"></div>

          <div class="form-section">
            <div class="section-label">
              <span class="section-dot green"></span>
              输入
            </div>
            <div class="form-row">
              <el-form-item label="用户输入" class="compact-form-item">
                <el-input
                  v-model="query"
                  type="textarea"
                  :rows="4"
                  placeholder="输入您的问题或任务..."
                  @keyup.enter.ctrl="runAgent"
                />
              </el-form-item>
            </div>
          </div>

          <div class="form-actions">
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              :disabled="!query.trim()"
              @click="runAgent"
              class="run-btn"
            >
              <el-icon><Cpu /></el-icon>
              运行智能体
            </el-button>
            <div class="hint">
              <el-icon size="12"><InfoFilled /></el-icon>
              Ctrl + Enter 快速运行
            </div>
          </div>
        </div>
      </div>

      <!-- Result Panel -->
      <div class="panel result-panel">
        <div class="panel-header">
          <div class="panel-badge">
            <el-icon size="14"><Document /></el-icon>
          </div>
          <div class="panel-title">结果</div>
          <div class="panel-subtitle">智能体输出</div>
        </div>

        <div class="panel-body result-body">
          <div v-if="result" class="result-content">
            <pre>{{ result }}</pre>
          </div>
          <div v-else-if="loading" class="result-loading">
            <div class="loading-pulse">
              <el-icon size="32" class="is-loading"><Loading /></el-icon>
            </div>
            <div class="loading-text">智能体正在思考...</div>
            <div class="loading-sub">最多执行 5 轮迭代</div>
          </div>
          <div v-else class="result-empty">
            <div class="empty-illustration">
              <el-icon size="48" color="var(--rp-primary-300)"><Cpu /></el-icon>
            </div>
            <div class="empty-title">准备就绪</div>
            <div class="empty-desc">配置左侧参数并点击「运行智能体」查看结果</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent {
  padding: 0;
}

/* ---- Page Header ---- */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--page-gap);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: var(--rp-radius-lg);
  background: var(--rp-primary-50);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-text h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-heading);
  letter-spacing: -0.01em;
  line-height: 1.3;
}

.header-text p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* ---- Workspace Layout ---- */
.agent-workspace {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--page-gap);
  align-items: start;
}

/* ---- Panel ---- */
.panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--rp-radius-lg);
  box-shadow: var(--rp-shadow-sm);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
  background: var(--color-surface);
}

.panel-badge {
  width: 28px;
  height: 28px;
  border-radius: var(--rp-radius-md);
  background: var(--rp-primary-50);
  color: var(--rp-primary-500);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-heading);
}

.panel-subtitle {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-left: auto;
}

.panel-body {
  padding: 20px;
  flex: 1;
}

/* ---- Form Sections ---- */
.form-section {
  margin-bottom: 4px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-heading);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.section-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.section-dot.blue {
  background: var(--rp-primary-500);
}

.section-dot.coral {
  background: var(--rp-coral-500);
}

.section-dot.green {
  background: var(--rp-success-500);
}

.form-row {
  margin-bottom: 12px;
}

.compact-form-item {
  margin-bottom: 0;
}

.compact-form-item :deep(.el-form-item__label) {
  font-size: 13px;
  padding-bottom: 6px;
  line-height: 1.4;
}

/* ---- Divider ---- */
.divider-soft {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-border), transparent);
  margin: 16px 0;
}

/* ---- Actions ---- */
.form-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light);
}

.run-btn {
  width: 100%;
  font-weight: 600;
  font-size: 14px;
  padding: 12px 24px;
  height: auto;
}

.hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* ---- Result Panel ---- */
.result-body {
  min-height: 400px;
  display: flex;
  flex-direction: column;
}

.result-content {
  background: var(--color-background-canvas);
  border: 1px solid var(--color-border-light);
  border-radius: var(--rp-radius-md);
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.result-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text);
}

/* Loading state */
.result-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
}

.loading-pulse {
  width: 64px;
  height: 64px;
  border-radius: var(--rp-radius-xl);
  background: var(--rp-primary-50);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.05); opacity: 0.8; }
}

.loading-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-heading);
}

.loading-sub {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* Empty state */
.result-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  text-align: center;
}

.empty-illustration {
  width: 80px;
  height: 80px;
  border-radius: var(--rp-radius-xl);
  background: var(--rp-primary-50);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
}

.empty-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  max-width: 280px;
  line-height: 1.6;
}

/* Responsive */
@media (max-width: 1024px) {
  .agent-workspace {
    grid-template-columns: 1fr;
  }
}
</style>
