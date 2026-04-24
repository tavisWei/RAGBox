<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api'
import { useClientPagination } from '@/composables/useClientPagination'

const auth = useAuthStore()
const users = ref<any[]>([])
const passwordForm = ref({ old_password: '', new_password: '' })
const resetPassword = ref('')
const savingUserId = ref<string | null>(null)

const {
  currentPage,
  total,
  paginatedItems: paginatedUsers,
  shouldPaginate,
  resetPagination,
} = useClientPagination(users, 15)

const currentUser = computed(() => auth.user)
const isAdmin = computed(() => ['owner', 'admin'].includes(currentUser.value?.role || ''))

const fetchUsers = async () => {
  if (!isAdmin.value) return
  const response = await authApi.users()
  users.value = response.data.users || []
}

const changePassword = async () => {
  await authApi.changePassword(passwordForm.value)
  ElMessage.success('密码已修改，请妥善保存新密码')
  passwordForm.value = { old_password: '', new_password: '' }
}

const updateUser = async (user: any) => {
  savingUserId.value = user.id
  try {
    await authApi.updateUser(user.id, { role: user.role, status: user.status, name: user.name })
    ElMessage.success('用户权限已更新')
    await fetchUsers()
  } finally {
    savingUserId.value = null
  }
}

const resetUserPassword = async (user: any) => {
  if (!resetPassword.value) {
    ElMessage.warning('请输入新密码')
    return
  }
  await authApi.resetUserPassword(user.id, { new_password: resetPassword.value })
  ElMessage.success('用户密码已重置')
  resetPassword.value = ''
}

const roleMeta: Record<string, { label: string; type: any }> = {
  owner: { label: 'Owner', type: 'danger' },
  admin: { label: 'Admin', type: 'warning' },
  member: { label: 'Member', type: 'info' },
}

const statusMeta: Record<string, { label: string; type: any }> = {
  active: { label: '启用', type: 'success' },
  disabled: { label: '禁用', type: 'info' },
}

onMounted(async () => {
  if (!auth.user)
    await auth.fetchUser()
  await fetchUsers().catch(() => ElMessage.warning('无法加载用户列表'))
})

watch(users, () => {
  resetPagination()
})
</script>

<template>
  <div class="account-view">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">账户与用户</h1>
        <p class="page-subtitle">管理你的账户信息和团队成员权限</p>
      </div>
    </div>

    <div class="account-grid">
      <!-- Left Column -->
      <div class="account-left">
        <!-- Current User Card -->
        <div class="surface-card user-card">
          <div class="card-header-row">
            <div class="user-avatar">
              {{ currentUser?.name?.charAt(0)?.toUpperCase() || currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}
            </div>
            <div class="user-info">
              <h3 class="user-name">{{ currentUser?.name || currentUser?.username }}</h3>
              <el-tag size="small" :type="roleMeta[currentUser?.role || '']?.type || 'info'">
                {{ roleMeta[currentUser?.role || '']?.label || currentUser?.role }}
              </el-tag>
            </div>
          </div>

          <div class="user-details">
            <div class="detail-row">
              <span class="detail-label">用户名</span>
              <span class="detail-value">{{ currentUser?.username }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">邮箱</span>
              <span class="detail-value">{{ currentUser?.email || '-' }}</span>
            </div>
          </div>
        </div>

        <!-- Change Password Card -->
        <div class="surface-card password-card">
          <h3 class="section-title">
            <el-icon class="section-icon"><Lock /></el-icon>
            修改我的密码
          </h3>
          <el-form :model="passwordForm" label-width="0" class="password-form">
            <el-form-item>
              <el-input
                v-model="passwordForm.old_password"
                type="password"
                show-password
                placeholder="当前密码"
                prefix-icon="Key"
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="passwordForm.new_password"
                type="password"
                show-password
                placeholder="新密码"
                prefix-icon="Lock"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" class="full-width" @click="changePassword">
                <el-icon><Check /></el-icon> 修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- Right Column -->
      <div class="account-right">
        <!-- Admin Users Table -->
        <div v-if="isAdmin" class="surface-card users-card">
          <h3 class="section-title">
            <el-icon class="section-icon"><UserFilled /></el-icon>
            用户与权限管理
          </h3>

          <el-table :data="paginatedUsers" stripe style="width: 100%">
            <el-table-column prop="username" label="用户名" min-width="120">
              <template #default="{ row }">
                <div class="user-cell">
                  <div class="user-cell-avatar">{{ row.username?.charAt(0)?.toUpperCase() }}</div>
                  <span class="user-cell-name">{{ row.username }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="姓名" width="140">
              <template #default="{ row }">
                <el-input v-model="row.name" size="small" placeholder="姓名" />
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="160">
              <template #default="{ row }">
                <span class="text-secondary">{{ row.email || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="角色" width="130">
              <template #default="{ row }">
                <el-select v-model="row.role" size="small">
                  <el-option label="Owner" value="owner" />
                  <el-option label="Admin" value="admin" />
                  <el-option label="Member" value="member" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-select v-model="row.status" size="small">
                  <el-option label="启用" value="active" />
                  <el-option label="禁用" value="disabled" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <div class="user-actions">
                  <el-button
                    size="small"
                    type="primary"
                    :loading="savingUserId === row.id"
                    @click="updateUser(row)"
                  >
                    <el-icon><Check /></el-icon> 保存
                  </el-button>
                  <el-popover placement="top" width="260" trigger="click">
                    <template #reference>
                      <el-button size="small">
                        <el-icon><RefreshRight /></el-icon> 重置
                      </el-button>
                    </template>
                    <div class="reset-popover">
                      <p class="reset-hint">为 {{ row.username }} 设置新密码</p>
                      <el-input
                        v-model="resetPassword"
                        type="password"
                        show-password
                        placeholder="输入新密码"
                        size="small"
                      />
                      <el-button
                        class="reset-confirm"
                        size="small"
                        type="primary"
                        @click="resetUserPassword(row)"
                      >
                        确认重置
                      </el-button>
                    </div>
                  </el-popover>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="shouldPaginate" class="page-pagination">
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

        <!-- Non-admin Info -->
        <div v-else class="surface-card info-card">
          <div class="info-content">
            <el-icon size="48" color="var(--rp-primary-300)"><InfoFilled /></el-icon>
            <h3>权限提示</h3>
            <p>普通用户只能管理自己的账户和密码；用户权限由管理员维护。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.account-view {
  padding: var(--page-padding);
}

.account-grid {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: var(--page-gap);
  align-items: start;
}

@media (max-width: 960px) {
  .account-grid {
    grid-template-columns: 1fr;
  }
}

.account-left {
  display: flex;
  flex-direction: column;
  gap: var(--page-gap);
}

.user-card {
  padding: 24px;
}

.card-header-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
}

.user-avatar {
  width: 56px;
  height: 56px;
  border-radius: var(--rp-radius-lg);
  background: linear-gradient(135deg, var(--rp-primary-400), var(--rp-primary-600));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
}

.user-name {
  font-size: 17px;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0 0 6px 0;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--color-surface-muted);
  border-radius: var(--rp-radius-md);
}

.detail-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.detail-value {
  font-size: 13px;
  color: var(--color-text);
  font-weight: 500;
}

.password-card {
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

.password-form :deep(.el-input__wrapper) {
  padding-left: 12px;
}

.full-width {
  width: 100%;
}

.account-right {
  min-width: 0;
}

.users-card {
  padding: 24px;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-cell-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--rp-radius-sm);
  background: var(--rp-primary-100);
  color: var(--rp-primary-600);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-cell-name {
  font-weight: 500;
  color: var(--color-heading);
}

.user-actions {
  display: flex;
  gap: 8px;
}

.reset-popover {
  padding: 4px;
}

.reset-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0 0 10px 0;
}

.reset-confirm {
  margin-top: 10px;
  width: 100%;
}

.info-card {
  padding: 60px 40px;
}

.info-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}

.info-content h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--color-heading);
  margin: 0;
}

.info-content p {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
  max-width: 360px;
}
</style>
