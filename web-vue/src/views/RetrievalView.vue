<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { retrievalApi } from '@/api'
import type { RetrievalPreset } from '@/types'
import {
  Setting,
  Search,
  Filter,
  Rank,
  MagicStick,
  Document,
  ArrowRight,
} from '@element-plus/icons-vue'

const presets = ref<RetrievalPreset[]>([])
const loading = ref(false)
const expandedPreset = ref<string | null>(null)

const fetchPresets = async () => {
  loading.value = true
  try {
    const response = await retrievalApi.getPresets()
    presets.value = response.data
  } finally {
    loading.value = false
  }
}

const toggleExpand = (name: string) => {
  expandedPreset.value = expandedPreset.value === name ? null : name
}

const getPresetIcon = (name: string) => {
  const map: Record<string, any> = {
    expert: Rank,
    advanced: MagicStick,
    basic: Search,
  }
  return map[name] || Setting
}

const getPresetAccent = (name: string) => {
  const map: Record<string, string> = {
    expert: 'var(--rp-coral-500)',
    advanced: 'var(--rp-warning-500)',
    basic: 'var(--rp-primary-500)',
  }
  return map[name] || 'var(--rp-primary-500)'
}

const getPresetBg = (name: string) => {
  const map: Record<string, string> = {
    expert: 'var(--rp-coral-50)',
    advanced: 'var(--rp-warning-50)',
    basic: 'var(--rp-primary-50)',
  }
  return map[name] || 'var(--rp-primary-50)'
}

const getPresetLabel = (name: string) => {
  const map: Record<string, string> = {
    expert: '专家模式',
    advanced: '高级模式',
    basic: '基础模式',
  }
  return map[name] || name
}

const getPresetDescription = (name: string) => {
  const map: Record<string, string> = {
    expert: '最高精度检索，适合对结果质量要求极高的场景',
    advanced: '平衡性能与精度，适合大多数业务场景',
    basic: '快速轻量检索，适合资源受限或实时性要求高的场景',
  }
  return map[name] || ''
}

const formatConfigValue = (value: any): string => {
  if (typeof value === 'boolean') return value ? '已启用' : '已禁用'
  if (typeof value === 'number') return value.toString()
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'object' && value !== null) return JSON.stringify(value)
  return String(value)
}

const getConfigIcon = (key: string) => {
  const map: Record<string, any> = {
    methods: Search,
    top_k: Filter,
    fusion_mode: MagicStick,
    query_expansion: Document,
    rerank_mode: Rank,
  }
  return map[key] || Setting
}

const getConfigLabel = (key: string) => {
  const map: Record<string, string> = {
    methods: '检索方式',
    top_k: '结果数量',
    fusion_mode: '融合策略',
    query_expansion: '查询扩展',
    rerank_mode: '重排模式',
    vector_weight: '向量权重',
    keyword_weight: '关键词权重',
    fulltext_weight: '全文权重',
    enable_hybrid: '混合检索',
    enable_rerank: '结果重排',
    temperature: '温度参数',
  }
  return map[key] || key
}

onMounted(() => {
  fetchPresets()
})
</script>

<template>
  <div class="retrieval">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-text">
        <h2 class="page-title">检索配置</h2>
        <p class="page-subtitle">
          预设检索策略模板，帮助您快速配置不同场景下的检索行为
        </p>
      </div>
    </div>

    <!-- Info Banner -->
    <div class="info-banner">
      <el-icon size="18" class="banner-icon"><MagicStick /></el-icon>
      <p>
        每个预设包含完整的检索参数组合，展开卡片可查看详细配置。在创建知识库时选择合适的预设即可一键应用。
      </p>
    </div>

    <!-- Loading State -->
    <el-skeleton v-if="loading" :rows="6" animated />

    <!-- Empty State -->
    <el-empty v-else-if="presets.length === 0" description="暂无检索配置">
      <template #image>
        <div class="empty-illustration">
          <el-icon size="64" class="text-tertiary"><Search /></el-icon>
        </div>
      </template>
    </el-empty>

    <!-- Presets Grid -->
    <div v-else class="presets-grid">
      <div
        v-for="preset in presets"
        :key="preset.name"
        class="preset-card surface-card"
        :class="{ expanded: expandedPreset === preset.name }"
      >
        <!-- Card Header -->
        <div class="preset-header" @click="toggleExpand(preset.name)">
          <div class="preset-icon-wrapper" :style="{ background: getPresetBg(preset.name), color: getPresetAccent(preset.name) }">
            <el-icon size="24"><component :is="getPresetIcon(preset.name)" /></el-icon>
          </div>
          <div class="preset-info">
            <div class="preset-name-row">
              <h3>{{ getPresetLabel(preset.name) }}</h3>
              <span class="preset-badge" :style="{ background: getPresetBg(preset.name), color: getPresetAccent(preset.name) }">
                {{ preset.name }}
              </span>
            </div>
            <p class="preset-desc">{{ getPresetDescription(preset.name) }}</p>
          </div>
          <div class="preset-toggle">
            <el-icon size="18" class="toggle-icon" :class="{ rotated: expandedPreset === preset.name }"><ArrowRight /></el-icon>
          </div>
        </div>

        <!-- Expanded Config Details -->
        <transition name="expand">
          <div v-show="expandedPreset === preset.name" class="preset-details">
            <div class="divider-soft" />
            <div class="details-grid">
              <div
                v-for="(value, key) in preset.config"
                :key="key"
                class="detail-item"
              >
                <div class="detail-icon">
                  <el-icon size="16" class="text-secondary"><component :is="getConfigIcon(String(key))" /></el-icon>
                </div>
                <div class="detail-content">
                  <span class="detail-label">{{ getConfigLabel(String(key)) }}</span>
                  <span class="detail-value" :class="{ 'text-success': value === true, 'text-secondary': value === false }">
                    {{ formatConfigValue(value) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.retrieval {
  padding: 0;
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

/* Presets Grid */
.presets-grid {
  display: flex;
  flex-direction: column;
  gap: var(--page-gap);
}

/* Preset Card */
.preset-card {
  padding: 0;
  overflow: hidden;
  transition: box-shadow var(--rp-transition-base);
}

.preset-card:hover {
  box-shadow: var(--rp-shadow-md);
}

.preset-card.expanded {
  box-shadow: var(--rp-shadow-lg);
}

/* Preset Header */
.preset-header {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 24px;
  cursor: pointer;
  transition: background var(--rp-transition-fast);
}

.preset-header:hover {
  background: var(--color-surface-hover);
}

.preset-icon-wrapper {
  width: 56px;
  height: 56px;
  border-radius: var(--rp-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.preset-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preset-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.preset-name-row h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-heading);
}

.preset-badge {
  padding: 4px 12px;
  border-radius: var(--rp-radius-full);
  font-size: 12px;
  font-weight: 600;
  text-transform: capitalize;
}

.preset-desc {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.preset-toggle {
  flex-shrink: 0;
}

.toggle-icon {
  color: var(--color-text-tertiary);
  transition: transform var(--rp-transition-base);
}

.toggle-icon.rotated {
  transform: rotate(90deg);
}

/* Preset Details */
.preset-details {
  padding: 0 24px 24px;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.detail-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  border: 1px solid var(--color-border-light);
}

.detail-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--rp-radius-md);
  background: var(--color-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.detail-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.detail-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  word-break: break-word;
}

/* Expand Transition */
.expand-enter-active,
.expand-leave-active {
  transition: all var(--rp-transition-base);
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 800px;
}

/* Responsive */
@media (max-width: 768px) {
  .preset-header {
    flex-wrap: wrap;
  }

  .preset-toggle {
    margin-left: auto;
  }

  .details-grid {
    grid-template-columns: 1fr;
  }
}
</style>
