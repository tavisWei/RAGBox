<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { monitoringApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'
import {
  Cpu,
  Memo,
  Folder,
  Timer,
  Upload,
  Download,
  Refresh,
  TrendCharts,
  Platform,
  List,
  Check,
  Warning,
} from '@element-plus/icons-vue'

const systemMetrics = ref<any>({})
const platformMetrics = ref<any>({})
const health = ref<any>({})
const processes = ref<any[]>([])
const loading = ref(false)
const refreshInterval = ref<number | null>(null)
const autoRefresh = ref(false)

const {
  currentPage,
  total,
  paginatedItems: paginatedProcesses,
  shouldPaginate,
  resetPagination,
} = useClientPagination(processes, 20)

const fetchAllMetrics = async () => {
  loading.value = true
  try {
    const [systemRes, platformRes, healthRes, processRes] = await Promise.all([
      monitoringApi.getSystem(),
      monitoringApi.getPlatform(),
      monitoringApi.getHealth(),
      monitoringApi.getProcesses(),
    ])
    systemMetrics.value = systemRes.data
    platformMetrics.value = platformRes.data
    health.value = healthRes.data
    processes.value = processRes.data.processes || []
  } catch (error) {
    ElMessage.error('获取监控数据失败')
  } finally {
    loading.value = false
  }
}

const toggleAutoRefresh = () => {
  if (autoRefresh.value) {
    refreshInterval.value = window.setInterval(fetchAllMetrics, 5000)
  } else {
    if (refreshInterval.value) {
      clearInterval(refreshInterval.value)
      refreshInterval.value = null
    }
  }
}

const formatUptime = (seconds: number) => {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}天${hours}小时${mins}分`
  if (hours > 0) return `${hours}小时${mins}分`
  return `${mins}分钟`
}

const getCpuColor = (percent: number) => {
  if (percent > 80) return 'var(--rp-danger-500)'
  if (percent > 50) return 'var(--rp-warning-500)'
  return 'var(--rp-success-500)'
}

const getMemoryColor = (percent: number) => {
  if (percent > 85) return 'var(--rp-danger-500)'
  if (percent > 60) return 'var(--rp-warning-500)'
  return 'var(--rp-success-500)'
}

const getDiskColor = (percent: number) => {
  if (percent > 90) return 'var(--rp-danger-500)'
  if (percent > 70) return 'var(--rp-warning-500)'
  return 'var(--rp-success-500)'
}

const getStatusBg = (percent: number, type: 'cpu' | 'memory' | 'disk') => {
  const colorFn = type === 'cpu' ? getCpuColor : type === 'memory' ? getMemoryColor : getDiskColor
  const color = colorFn(percent)
  if (color.includes('danger')) return 'var(--rp-danger-50)'
  if (color.includes('warning')) return 'var(--rp-warning-50)'
  return 'var(--rp-success-50)'
}

onMounted(() => {
  fetchAllMetrics()
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})

watch(processes, () => {
  resetPagination()
})
</script>

<template>
  <div class="monitoring">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-text">
          <h2 class="page-title">系统监控</h2>
          <p class="page-subtitle">实时查看系统运行状态与性能指标</p>
        </div>
        <div class="health-badge" :class="{ healthy: health.status === 'healthy' }">
          <el-icon size="14">
            <Check v-if="health.status === 'healthy'" />
            <Warning v-else />
          </el-icon>
          <span>{{ health.status === 'healthy' ? '运行正常' : '异常' }}</span>
        </div>
      </div>
      <div class="header-right">
        <div class="refresh-control">
          <el-icon size="16" class="refresh-icon" :class="{ spinning: loading }"><Refresh /></el-icon>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            inline-prompt
            @change="toggleAutoRefresh"
          />
        </div>
        <el-button :loading="loading" @click="fetchAllMetrics">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- Core Metrics Cards -->
    <div class="metrics-grid">
      <!-- CPU Card -->
      <div class="metric-card surface-card" v-loading="loading">
        <div class="metric-card__header">
          <div class="metric-icon" :style="{ background: getStatusBg(systemMetrics.cpu_percent || 0, 'cpu'), color: getCpuColor(systemMetrics.cpu_percent || 0) }">
            <el-icon size="20"><Cpu /></el-icon>
          </div>
          <span class="metric-name">CPU 使用率</span>
        </div>
        <div class="metric-card__body">
          <div class="metric-value" :style="{ color: getCpuColor(systemMetrics.cpu_percent || 0) }">
            {{ systemMetrics.cpu_percent || 0 }}%
          </div>
          <div class="metric-progress">
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: `${systemMetrics.cpu_percent || 0}%`, background: getCpuColor(systemMetrics.cpu_percent || 0) }"
              />
            </div>
          </div>
          <div class="metric-meta">
            <span>{{ systemMetrics.cpu_count || 0 }} 核心</span>
            <span class="metric-status" :style="{ color: getCpuColor(systemMetrics.cpu_percent || 0) }">
              {{ (systemMetrics.cpu_percent || 0) > 80 ? '高负载' : (systemMetrics.cpu_percent || 0) > 50 ? '中等' : '正常' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Memory Card -->
      <div class="metric-card surface-card" v-loading="loading">
        <div class="metric-card__header">
          <div class="metric-icon" :style="{ background: getStatusBg(systemMetrics.memory_percent || 0, 'memory'), color: getMemoryColor(systemMetrics.memory_percent || 0) }">
            <el-icon size="20"><Memo /></el-icon>
          </div>
          <span class="metric-name">内存使用</span>
        </div>
        <div class="metric-card__body">
          <div class="metric-value" :style="{ color: getMemoryColor(systemMetrics.memory_percent || 0) }">
            {{ systemMetrics.memory_percent || 0 }}%
          </div>
          <div class="metric-progress">
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: `${systemMetrics.memory_percent || 0}%`, background: getMemoryColor(systemMetrics.memory_percent || 0) }"
              />
            </div>
          </div>
          <div class="metric-meta">
            <span>{{ systemMetrics.memory_used_gb || 0 }} / {{ systemMetrics.memory_total_gb || 0 }} GB</span>
            <span class="metric-status" :style="{ color: getMemoryColor(systemMetrics.memory_percent || 0) }">
              {{ (systemMetrics.memory_percent || 0) > 85 ? '紧张' : (systemMetrics.memory_percent || 0) > 60 ? '中等' : '充足' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Disk Card -->
      <div class="metric-card surface-card" v-loading="loading">
        <div class="metric-card__header">
          <div class="metric-icon" :style="{ background: getStatusBg(systemMetrics.disk_percent || 0, 'disk'), color: getDiskColor(systemMetrics.disk_percent || 0) }">
            <el-icon size="20"><Folder /></el-icon>
          </div>
          <span class="metric-name">磁盘使用</span>
        </div>
        <div class="metric-card__body">
          <div class="metric-value" :style="{ color: getDiskColor(systemMetrics.disk_percent || 0) }">
            {{ systemMetrics.disk_percent || 0 }}%
          </div>
          <div class="metric-progress">
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: `${systemMetrics.disk_percent || 0}%`, background: getDiskColor(systemMetrics.disk_percent || 0) }"
              />
            </div>
          </div>
          <div class="metric-meta">
            <span>{{ systemMetrics.disk_used_gb || 0 }} / {{ systemMetrics.disk_total_gb || 0 }} GB</span>
            <span class="metric-status" :style="{ color: getDiskColor(systemMetrics.disk_percent || 0) }">
              {{ (systemMetrics.disk_percent || 0) > 90 ? '告警' : (systemMetrics.disk_percent || 0) > 70 ? '注意' : '正常' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Uptime Card -->
      <div class="metric-card surface-card" v-loading="loading">
        <div class="metric-card__header">
          <div class="metric-icon" style="background: var(--rp-primary-50); color: var(--rp-primary-500)">
            <el-icon size="20"><Timer /></el-icon>
          </div>
          <span class="metric-name">运行时间</span>
        </div>
        <div class="metric-card__body">
          <div class="metric-value">
            {{ formatUptime(platformMetrics.uptime_seconds || 0) }}
          </div>
          <div class="uptime-meta">
            <div class="uptime-item">
              <el-icon size="14" class="text-secondary"><Platform /></el-icon>
              <span>Python {{ platformMetrics.python_version || '-' }}</span>
            </div>
            <div class="uptime-item">
              <el-icon size="14" class="text-secondary"><TrendCharts /></el-icon>
              <span>{{ platformMetrics.platform || '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Secondary Stats Row -->
    <div class="stats-row">
      <!-- Network Stats -->
      <div class="stats-card surface-card" v-loading="loading">
        <div class="stats-card__header">
          <div class="stats-icon" style="background: var(--rp-primary-50); color: var(--rp-primary-500)">
            <el-icon size="20"><TrendCharts /></el-icon>
          </div>
          <span class="stats-title">网络流量</span>
        </div>
        <div class="stats-card__body">
          <div class="network-stats">
            <div class="network-stat">
              <div class="network-icon upload">
                <el-icon size="22"><Upload /></el-icon>
              </div>
              <div class="network-info">
                <span class="network-label">上传</span>
                <span class="network-value">{{ systemMetrics.network_sent_mb || 0 }} MB</span>
              </div>
            </div>
            <div class="network-stat">
              <div class="network-icon download">
                <el-icon size="22"><Download /></el-icon>
              </div>
              <div class="network-info">
                <span class="network-label">下载</span>
                <span class="network-value">{{ systemMetrics.network_recv_mb || 0 }} MB</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Platform Stats -->
      <div class="stats-card surface-card" v-loading="loading">
        <div class="stats-card__header">
          <div class="stats-icon" style="background: var(--rp-success-50); color: var(--rp-success-500)">
            <el-icon size="20"><Platform /></el-icon>
          </div>
          <span class="stats-title">平台统计</span>
        </div>
        <div class="stats-card__body">
          <div class="platform-grid">
            <div class="platform-item">
              <span class="platform-label">总请求数</span>
              <span class="platform-value">{{ platformMetrics.request_count || 0 }}</span>
            </div>
            <div class="platform-item">
              <span class="platform-label">错误数</span>
              <span class="platform-value" :class="{ 'text-danger': (platformMetrics.error_count || 0) > 0 }">
                {{ platformMetrics.error_count || 0 }}
              </span>
            </div>
            <div class="platform-item">
              <span class="platform-label">平均响应</span>
              <span class="platform-value">{{ platformMetrics.avg_response_time_ms || 0 }} ms</span>
            </div>
            <div class="platform-item">
              <span class="platform-label">版本</span>
              <span class="platform-value">{{ health.version || '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Process Table -->
    <div class="process-section surface-card" v-loading="loading">
      <div class="process-header">
        <div class="process-title">
          <div class="process-icon" style="background: var(--rp-warning-50); color: var(--rp-warning-500)">
            <el-icon size="20"><List /></el-icon>
          </div>
          <span>进程监控</span>
          <span class="process-count">Top {{ processes.length }}</span>
        </div>
      </div>
      <el-table :data="paginatedProcesses" size="default" max-height="480" class="process-table">
        <el-table-column prop="pid" label="PID" width="90">
          <template #default="{ row }">
            <span class="pid-value">{{ row.pid }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="进程名" min-width="160">
          <template #default="{ row }">
            <span class="process-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <span class="status-badge" :class="row.status">
              <span class="status-dot" :class="row.status" />
              {{ row.status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="cpu_percent" label="CPU %" width="140">
          <template #default="{ row }">
            <div class="progress-cell">
              <div class="progress-track-sm">
                <div
                  class="progress-fill-sm"
                  :style="{ width: `${Math.min(row.cpu_percent, 100)}%`, background: getCpuColor(row.cpu_percent) }"
                />
              </div>
              <span class="progress-text">{{ row.cpu_percent }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="memory_percent" label="内存 %" width="140">
          <template #default="{ row }">
            <div class="progress-cell">
              <div class="progress-track-sm">
                <div
                  class="progress-fill-sm"
                  :style="{ width: `${Math.min(row.memory_percent, 100)}%`, background: getMemoryColor(row.memory_percent) }"
                />
              </div>
              <span class="progress-text">{{ row.memory_percent }}%</span>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="shouldPaginate && !loading" class="page-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :total="total"
          :page-size="20"
          background
          layout="prev, pager, next"
          :hide-on-single-page="true"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitoring {
  padding: 0;
}

/* Header */
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--rp-radius-full);
  background: var(--rp-danger-50);
  color: var(--rp-danger-600);
  font-size: 13px;
  font-weight: 600;
}

.health-badge.healthy {
  background: var(--rp-success-50);
  color: var(--rp-success-600);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.refresh-control {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  border: 1px solid var(--color-border-light);
}

.refresh-icon {
  color: var(--color-text-secondary);
  transition: transform var(--rp-transition-base);
}

.refresh-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Metrics Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--page-gap);
  margin-bottom: var(--page-gap);
}

/* Metric Card */
.metric-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metric-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.metric-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.metric-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-heading);
}

.metric-card__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-value {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1;
}

.metric-progress {
  width: 100%;
}

.progress-track {
  width: 100%;
  height: 8px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: var(--rp-radius-full);
  transition: width var(--rp-transition-base);
}

.metric-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.metric-status {
  font-weight: 600;
  font-size: 12px;
}

/* Uptime Meta */
.uptime-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.uptime-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--page-gap);
  margin-bottom: var(--page-gap);
}

.stats-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stats-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stats-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-heading);
}

/* Network Stats */
.network-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.network-stat {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-lg);
  border: 1px solid var(--color-border-light);
}

.network-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--rp-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.network-icon.upload {
  background: linear-gradient(135deg, var(--rp-primary-500), var(--rp-primary-400));
}

.network-icon.download {
  background: linear-gradient(135deg, var(--rp-success-500), var(--rp-success-400));
}

.network-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.network-label {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.network-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-heading);
}

/* Platform Grid */
.platform-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.platform-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
  border: 1px solid var(--color-border-light);
}

.platform-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.platform-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-heading);
}

/* Process Section */
.process-section {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.process-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.process-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.process-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.process-title > span:nth-child(2) {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-heading);
}

.process-count {
  margin-left: 8px;
  padding: 4px 12px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-full);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

/* Process Table Customizations */
.process-table :deep(.el-table__header th.el-table__cell) {
  font-weight: 600 !important;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.pid-value {
  font-family: 'SF Mono', monospace;
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.process-name {
  font-weight: 600;
  color: var(--color-heading);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--rp-radius-full);
  font-size: 12px;
  font-weight: 600;
  background: var(--color-surface-muted);
  color: var(--color-text-secondary);
}

.status-badge.running {
  background: var(--rp-success-50);
  color: var(--rp-success-600);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
}

.status-dot.running {
  background: var(--rp-success-500);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-track-sm {
  flex: 1;
  height: 6px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-full);
  overflow: hidden;
}

.progress-fill-sm {
  height: 100%;
  border-radius: var(--rp-radius-full);
  transition: width var(--rp-transition-base);
}

.progress-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  min-width: 36px;
  text-align: right;
  font-family: 'SF Mono', monospace;
}

/* Responsive */
@media (max-width: 1024px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-left {
    flex-wrap: wrap;
  }

  .header-right {
    width: 100%;
    justify-content: space-between;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .stats-row {
    grid-template-columns: 1fr;
  }

  .network-stats {
    grid-template-columns: 1fr;
  }

  .platform-grid {
    grid-template-columns: 1fr;
  }
}
</style>
