<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { promptApi } from '@/api'

const template = ref('你好，{{ name }}！欢迎来到{{ place }}。')
const inputs = ref<Record<string, string>>({
  name: '用户',
  place: 'RAG Platform',
})
const result = ref('')
const variables = ref<string[]>([])
const templates = ref<any[]>([])
const selectedTemplateId = ref('')
const templateName = ref('')
const templateDescription = ref('')
const templateCategory = ref('general')

const fetchTemplates = async () => {
  const response = await promptApi.listTemplates()
  templates.value = response.data.data || []
}

const onTemplateSelect = () => {
  const selected = templates.value.find(item => item.id === selectedTemplateId.value)
  if (!selected) return
  templateName.value = selected.name
  templateDescription.value = selected.description || ''
  templateCategory.value = selected.category || 'general'
  template.value = selected.template
  variables.value = selected.variables || []
}

const saveTemplate = async () => {
  if (!templateName.value.trim()) {
    ElMessage.warning('请输入模板名称')
    return
  }
  const payload = {
    name: templateName.value,
    description: templateDescription.value || undefined,
    template: template.value,
    category: templateCategory.value || 'general',
  }
  if (selectedTemplateId.value)
    await promptApi.updateTemplate(selectedTemplateId.value, payload)
  else {
    const response = await promptApi.createTemplate(payload)
    selectedTemplateId.value = response.data.data.id
  }
  ElMessage.success('模板已保存')
  await fetchTemplates()
}

const createNewTemplate = () => {
  selectedTemplateId.value = ''
  templateName.value = ''
  templateDescription.value = ''
  templateCategory.value = 'general'
  template.value = ''
  result.value = ''
  variables.value = []
}

const formatPrompt = async () => {
  try {
    const response = await promptApi.format({
      template: template.value,
      inputs: inputs.value,
    })
    result.value = response.data.result
    variables.value = response.data.variables
  } catch {
    ElMessage.error('格式化失败')
  }
}

const addVariable = () => {
  const key = `var${Object.keys(inputs.value).length + 1}`
  inputs.value[key] = ''
}

const removeVariable = (key: string) => {
  delete inputs.value[key]
}

onMounted(fetchTemplates)
</script>

<template>
  <div class="prompts">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-icon-wrap">
          <el-icon size="24" color="var(--rp-coral-500)"><Document /></el-icon>
        </div>
        <div class="header-text">
          <h2>提示词模板</h2>
          <p>编辑模板变量并预览格式化后的提示词结果</p>
        </div>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedTemplateId" placeholder="选择已保存模板" clearable style="width: 240px" @change="onTemplateSelect">
          <el-option v-for="item in templates" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-button @click="createNewTemplate">新建模板</el-button>
        <el-button type="primary" @click="saveTemplate">保存模板</el-button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="prompt-workspace">
      <!-- Template Editor Panel -->
      <div class="panel editor-panel">
        <div class="panel-header">
          <div class="panel-badge coral">
            <el-icon size="14"><Edit /></el-icon>
          </div>
          <div class="panel-title">模板编辑</div>
          <div class="panel-subtitle">定义变量与内容</div>
        </div>

        <div class="panel-body">
          <div class="form-section">
            <div class="section-label">
              <span class="section-dot blue"></span>
              模板信息
            </div>
            <el-input v-model="templateName" class="template-meta-input" placeholder="模板名称，例如：角色系统提示词" />
            <el-input v-model="templateDescription" class="template-meta-input" placeholder="模板说明" />
            <el-select v-model="templateCategory" class="template-meta-input" placeholder="使用场景">
              <el-option label="通用" value="general" />
              <el-option label="角色" value="role" />
              <el-option label="智能体" value="agent" />
              <el-option label="工作流" value="workflow" />
            </el-select>
          </div>

          <div class="divider-soft"></div>

          <div class="form-section">
            <div class="section-label">
              <span class="section-dot coral"></span>
              模板内容
            </div>
            <div class="template-editor">
              <el-input
                v-model="template"
                type="textarea"
                :rows="8"
                resize="none"
                placeholder="输入提示词模板，使用 {{ variable }} 语法插入变量..."
              />
              <div class="template-tip">
                <el-icon size="12"><InfoFilled /></el-icon>
                <span>使用 <code v-pre>{{ variable }}</code> 包裹变量名，例如 <code v-pre>{{ name }}</code></span>
              </div>
            </div>
          </div>

          <div class="divider-soft"></div>

          <div class="form-section">
            <div class="section-label">
              <span class="section-dot blue"></span>
              变量赋值
            </div>
            <div class="variables-list">
              <div v-for="(value, key) in inputs" :key="key" class="variable-row">
                <div class="variable-key">
                  <span class="key-badge">{{ key }}</span>
                </div>
                <el-input
                  v-model="inputs[key]"
                  :placeholder="`输入 ${key} 的值...`"
                  class="variable-input"
                />
                <el-button
                  class="variable-remove"
                  type="danger"
                  text
                  @click="removeVariable(key)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
            <el-button
              type="primary"
              size="small"
              text
              class="add-var-btn"
              @click="addVariable"
            >
              <el-icon><Plus /></el-icon>
              添加变量
            </el-button>
          </div>

          <div class="form-actions">
            <el-button
              type="primary"
              size="large"
              @click="formatPrompt"
              class="format-btn"
            >
              <el-icon><MagicStick /></el-icon>
              格式化
            </el-button>
          </div>
        </div>
      </div>

      <!-- Result Panel -->
      <div class="panel result-panel">
        <div class="panel-header">
          <div class="panel-badge green">
            <el-icon size="14"><View /></el-icon>
          </div>
          <div class="panel-title">结果预览</div>
          <div class="panel-subtitle">格式化输出</div>
        </div>

        <div class="panel-body result-body">
          <div v-if="result" class="result-content">
            <pre>{{ result }}</pre>
          </div>
          <div v-else class="result-empty">
            <div class="empty-illustration">
              <el-icon size="48" color="var(--rp-coral-400)"><MagicStick /></el-icon>
            </div>
            <div class="empty-title">提示词预览</div>
            <div class="empty-desc">编辑模板并点击「格式化」查看替换后的结果</div>
          </div>
        </div>

        <!-- Detected Variables Footer -->
        <div v-if="variables.length > 0" class="variables-footer">
          <div class="variables-label">
            <el-icon size="12"><Check /></el-icon>
            检测到的变量
          </div>
          <div class="variables-tags">
            <el-tag
              v-for="v in variables"
              :key="v"
              type="primary"
              effect="light"
              size="small"
            >
              {{ v }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prompts {
  padding: 0;
}

/* ---- Page Header ---- */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--page-gap);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
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
  background: var(--rp-coral-50);
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
.prompt-workspace {
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

.panel-badge.coral {
  background: var(--rp-coral-50);
  color: var(--rp-coral-500);
}

.panel-badge.green {
  background: var(--rp-success-50);
  color: var(--rp-success-500);
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

.template-meta-input {
  width: 100%;
  margin-top: 10px;
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

.section-dot.coral {
  background: var(--rp-coral-500);
}

.section-dot.blue {
  background: var(--rp-primary-500);
}

/* ---- Template Editor ---- */
.template-editor {
  position: relative;
}

.template-editor :deep(.el-textarea__inner) {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 13px;
  line-height: 1.7;
  padding: 14px;
}

.template-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--rp-primary-50);
  border-radius: var(--rp-radius-md);
  font-size: 12px;
  color: var(--rp-primary-600);
}

.template-tip code {
  background: var(--rp-white);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
  border: 1px solid var(--rp-primary-200);
}

/* ---- Divider ---- */
.divider-soft {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-border), transparent);
  margin: 16px 0;
}

/* ---- Variables ---- */
.variables-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.variable-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.variable-key {
  flex-shrink: 0;
  min-width: 80px;
}

.key-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: var(--rp-primary-50);
  color: var(--rp-primary-600);
  border-radius: var(--rp-radius-sm);
  font-size: 12px;
  font-weight: 600;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.variable-input {
  flex: 1;
}

.variable-input :deep(.el-input__wrapper) {
  padding-left: 10px;
}

.variable-remove {
  flex-shrink: 0;
  padding: 6px;
}

.add-var-btn {
  font-weight: 500;
}

/* ---- Actions ---- */
.form-actions {
  display: flex;
  justify-content: center;
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light);
}

.format-btn {
  font-weight: 600;
  font-size: 14px;
  padding: 12px 32px;
  height: auto;
}

/* ---- Result Panel ---- */
.result-body {
  min-height: 320px;
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
  background: var(--rp-coral-50);
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

/* ---- Variables Footer ---- */
.variables-footer {
  padding: 14px 20px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-surface);
  display: flex;
  align-items: center;
  gap: 12px;
}

.variables-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}

.variables-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.variables-tags :deep(.el-tag) {
  border-radius: var(--rp-radius-sm);
  font-weight: 500;
}

/* Responsive */
@media (max-width: 1024px) {
  .prompt-workspace {
    grid-template-columns: 1fr;
  }
}
</style>
