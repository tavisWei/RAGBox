<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

onMounted(async () => {
  if (auth.token && !auth.user) {
    await auth.fetchUser()
  }
})

const isPublicPage = computed(() => route.path === '/login')

const menuItems = [
  { path: '/', icon: 'HomeFilled', title: '首页' },
  { path: '/account', icon: 'User', title: '账户' },
  { path: '/workspace', icon: 'OfficeBuilding', title: '工作区' },
  { path: '/knowledge-bases', icon: 'Collection', title: '知识库' },
  { path: '/chat', icon: 'ChatDotRound', title: '对话' },
  { path: '/agent', icon: 'Cpu', title: '智能体' },
  { path: '/apps', icon: 'Grid', title: '应用' },
  { path: '/workflows', icon: 'Share', title: '工作流' },
  { path: '/prompts', icon: 'Document', title: '提示词' },
  { path: '/retrieval', icon: 'Search', title: '检索配置' },
  { path: '/resource-configs', icon: 'Setting', title: 'RAG 方案' },
  { path: '/component-configs', icon: 'Connection', title: '组件配置' },
  { path: '/model-providers', icon: 'Connection', title: '模型提供商' },
  { path: '/monitoring', icon: 'TrendCharts', title: '监控' },
]

const handleCommand = async (command: string) => {
  if (command === 'account') {
    await router.push('/account')
    return
  }
  if (command === 'logout') {
    await auth.logout()
    await router.push('/login')
  }
}
</script>

<template>
  <router-view v-if="isPublicPage" />
  <el-container v-else class="layout-container">
    <el-aside :width="'var(--sidebar-width)'" class="sidebar">
      <div class="logo">
        <div class="logo-mark">
          <el-icon size="22" color="var(--rp-primary-500)"><Collection /></el-icon>
        </div>
        <span class="logo-text">RAG Platform</span>
      </div>

      <div class="sidebar-menu">
        <div
          v-for="item in menuItems"
          :key="item.path"
          class="menu-item"
          :class="{ active: route.path === item.path }"
          @click="router.push(item.path)"
        >
          <el-icon size="18">
            <component :is="item.icon" />
          </el-icon>
          <span class="menu-title">{{ item.title }}</span>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="footer-hint">
          <el-icon size="14"><InfoFilled /></el-icon>
          <span>v1.0.0</span>
        </div>
      </div>
    </el-aside>

    <el-container class="main-wrapper">
      <el-header class="header">
        <div class="header-left">
          <span class="page-breadcrumb">{{ menuItems.find(m => m.path === route.path)?.title || '' }}</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand" popper-class="user-dropdown">
            <div class="user-info">
              <div class="user-avatar">
                <el-icon size="18"><User /></el-icon>
              </div>
              <span class="user-name">{{ auth.user?.name || auth.user?.username || '用户' }}</span>
              <el-icon size="14" class="user-chevron"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="account">
                  <el-icon><User /></el-icon>
                  <span>个人设置</span>
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <div class="page-canvas">
          <router-view :key="route.fullPath" />
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-container {
  height: 100vh;
  width: 100vw;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  margin: 0;
  padding: 0;
  overflow: hidden;
  background: var(--color-background);
}

/* ---- Sidebar ---- */
.sidebar {
  background: var(--color-background-sidebar);
  border-right: 1px solid var(--sidebar-border);
  display: flex;
  flex-direction: column;
  transition: width var(--rp-transition-base);
}

.logo {
  height: var(--header-height);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  border-bottom: 1px solid var(--sidebar-border);
  flex-shrink: 0;
}

.logo-mark {
  width: 36px;
  height: 36px;
  border-radius: var(--rp-radius-md);
  background: var(--rp-primary-50);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-heading);
  letter-spacing: -0.02em;
}

.sidebar-menu {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  height: 42px;
  cursor: pointer;
  color: var(--sidebar-text);
  border-radius: var(--rp-radius-md);
  transition: all var(--rp-transition-fast);
  font-size: 14px;
  font-weight: 500;
}

.menu-item:hover {
  background-color: var(--sidebar-bg-hover);
  color: var(--sidebar-text-hover);
}

.menu-item.active {
  background-color: var(--sidebar-bg-active);
  color: var(--sidebar-text-active);
  font-weight: 600;
}

.menu-item.active .el-icon {
  color: var(--sidebar-text-active);
}

.menu-title {
  line-height: 1;
}

.sidebar-footer {
  padding: 12px 18px;
  border-top: 1px solid var(--sidebar-border);
  flex-shrink: 0;
}

.footer-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* ---- Main wrapper ---- */
.main-wrapper {
  background: var(--color-background-canvas);
}

/* ---- Header ---- */
.header {
  height: var(--header-height);
  background: var(--color-background-header);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--page-padding);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
}

.page-breadcrumb {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--rp-radius-md);
  transition: background var(--rp-transition-fast);
}

.user-info:hover {
  background: var(--color-surface-muted);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--rp-radius-full);
  background: var(--rp-primary-50);
  color: var(--rp-primary-600);
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
}

.user-chevron {
  color: var(--color-text-tertiary);
  transition: transform var(--rp-transition-fast);
}

.user-info:hover .user-chevron {
  transform: translateY(1px);
}

/* ---- Main Content ---- */
.main-content {
  padding: var(--page-padding);
  overflow-y: auto;
  height: calc(100vh - var(--header-height));
  width: 100%;
}

.page-canvas {
  max-width: 1280px;
  margin: 0 auto;
}
</style>
