import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/knowledge-bases',
      name: 'knowledge-bases',
      component: () => import('@/views/KnowledgeBaseView.vue'),
    },
    {
      path: '/knowledge-bases/:id',
      name: 'knowledge-base-detail',
      component: () => import('@/views/KnowledgeBaseDetailView.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
    },
    {
      path: '/agent',
      name: 'agent',
      component: () => import('@/views/AgentView.vue'),
    },
    {
      path: '/apps',
      name: 'apps',
      component: () => import('@/views/AppsView.vue'),
    },
    {
      path: '/apps/:id',
      name: 'app-detail',
      component: () => import('@/views/AppDetailView.vue'),
    },
    {
      path: '/workflows',
      name: 'workflows',
      component: () => import('@/views/WorkflowView.vue'),
    },
    {
      path: '/prompts',
      name: 'prompts',
      component: () => import('@/views/PromptView.vue'),
    },
    {
      path: '/retrieval',
      name: 'retrieval',
      component: () => import('@/views/RetrievalView.vue'),
    },
    {
      path: '/resource-configs',
      name: 'resource-configs',
      component: () => import('@/views/ResourceConfigView.vue'),
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/AccountView.vue'),
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: () => import('@/views/WorkspaceView.vue'),
    },
    {
      path: '/model-providers',
      name: 'model-providers',
      component: () => import('@/views/ModelProvidersView.vue'),
    },
    {
      path: '/component-configs',
      name: 'component-configs',
      component: () => import('@/views/ComponentConfigsView.vue'),
    },
    {
      path: '/monitoring',
      name: 'monitoring',
      component: () => import('@/views/MonitoringView.vue'),
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public)
    return true
  if (!auth.token) {
    return '/login'
  }
  if (!auth.user) {
    try {
      await auth.fetchUser()
    }
    catch {
      return '/login'
    }
  }
  return true
})

export default router
