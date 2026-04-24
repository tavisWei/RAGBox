<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { workspaceApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'

const workspace = ref<any>(null)
const members = ref<any[]>([])
const loading = ref(false)

const {
  currentPage,
  total,
  paginatedItems: paginatedMembers,
  shouldPaginate,
  resetPagination,
} = useClientPagination(members, 15)

const fetchData = async () => {
  loading.value = true
  try {
    const [workspaceRes, membersRes] = await Promise.all([
      workspaceApi.current(),
      workspaceApi.members(),
    ])
    workspace.value = workspaceRes.data
    members.value = membersRes.data.data || []
  } finally {
    loading.value = false
  }
}

const roleMeta: Record<string, { label: string; type: any }> = {
  owner: { label: 'Owner', type: 'danger' },
  admin: { label: 'Admin', type: 'warning' },
  member: { label: 'Member', type: 'info' },
}

onMounted(() => {
  fetchData()
})

watch(members, () => {
  resetPagination()
})
</script>

<template>
  <div class="workspace-view">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">工作区</h1>
        <p class="page-subtitle">查看当前工作区信息和团队成员</p>
      </div>
    </div>

    <div class="workspace-grid">
      <!-- Workspace Info Card -->
      <div class="surface-card workspace-card">
        <h3 class="section-title">
          <el-icon class="section-icon"><OfficeBuilding /></el-icon>
          当前工作区
        </h3>

        <div class="workspace-info">
          <div class="info-block">
            <div class="info-label">工作区名称</div>
            <div class="info-value">{{ workspace?.name || '-' }}</div>
          </div>
          <div class="info-block">
            <div class="info-label">我的角色</div>
            <div class="info-value">
              <el-tag :type="roleMeta[workspace?.role]?.type || 'info'" size="small">
                {{ roleMeta[workspace?.role]?.label || workspace?.role || '-' }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- Members Table Card -->
      <div class="surface-card members-card">
        <h3 class="section-title">
          <el-icon class="section-icon"><User /></el-icon>
          成员
        </h3>

        <el-table :data="paginatedMembers" stripe v-loading="loading" style="width: 100%">
          <el-table-column label="用户" min-width="160">
            <template #default="{ row }">
              <div class="member-cell">
                <div class="member-avatar">{{ row.username?.charAt(0)?.toUpperCase() }}</div>
                <div class="member-info">
                  <span class="member-name">{{ row.username }}</span>
                  <span v-if="row.name" class="member-real-name">{{ row.name }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="email" label="邮箱" min-width="200">
            <template #default="{ row }">
              <span class="text-secondary">{{ row.email || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="角色" width="120">
            <template #default="{ row }">
              <el-tag :type="roleMeta[row.role]?.type || 'info'" size="small">
                {{ roleMeta[row.role]?.label || row.role }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="members.length === 0 && !loading" class="table-empty">
          <el-icon size="40" color="var(--rp-gray-300)"><User /></el-icon>
          <p class="empty-text">暂无成员</p>
        </div>

        <div v-if="shouldPaginate && !loading" class="page-pagination">
          <el-pagination
            v-model:current-page="currentPage"
            :total="total"
            :page-size="15"
            background
            layout="prev, pager, next"
            :hide-on-single-page="true"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace-view {
  padding: var(--page-padding);
}

.workspace-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: var(--page-gap);
  align-items: start;
}

@media (max-width: 960px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}

.workspace-card {
  padding: 24px;
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

.workspace-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-block {
  padding: 14px 16px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
}

.info-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-heading);
}

.members-card {
  padding: 24px;
  min-width: 0;
}

.member-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.member-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--rp-radius-md);
  background: linear-gradient(135deg, var(--rp-primary-300), var(--rp-primary-500));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
}

.member-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.member-name {
  font-weight: 500;
  color: var(--color-heading);
  font-size: 14px;
}

.member-real-name {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.table-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 20px;
  text-align: center;
}

.empty-text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 8px 0 0 0;
}
</style>
