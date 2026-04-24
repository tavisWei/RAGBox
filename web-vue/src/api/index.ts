import api from './client'

export const API_BASE_URL = '/api/v1'
import type { KnowledgeBase, CreateKnowledgeBaseRequest } from '@/types'

export const knowledgeBaseApi = {
  list: () => api.get('/knowledge-bases'),
  create: (data: CreateKnowledgeBaseRequest) => api.post('/knowledge-bases', data),
  get: (id: string) => api.get(`/knowledge-bases/${id}`),
  update: (id: string, data: Partial<CreateKnowledgeBaseRequest> & { hardware_tier?: string; rag_plan?: string; reindex_required?: boolean; splitter_config?: Record<string, any>; retrieval_config?: Record<string, any> }) => api.put(`/knowledge-bases/${id}`, data),
  delete: (id: string) => api.delete(`/knowledge-bases/${id}`),
  getRagPlans: () => api.get('/knowledge-bases/rag-plans/presets'),
  addDocument: (id: string, content: string, metadata?: Record<string, any>) =>
    api.post(`/knowledge-bases/${id}/documents`, { content, metadata }),
  uploadDocument: (id: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/knowledge-bases/${id}/documents/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listDocuments: (id: string) => api.get(`/knowledge-bases/${id}/documents`),
  deleteDocument: (id: string, documentId: string) => api.delete(`/knowledge-bases/${id}/documents/${documentId}`),
  hitTest: (id: string, data: { query: string; top_k?: number; provider?: string; model?: string }) => api.post(`/knowledge-bases/${id}/hit-test`, data),
}

export const chatApi = {
  sendMessage: (data: { query: string; knowledge_base_id: string; knowledge_base_ids?: string[]; conversation_id?: string; provider?: string; model?: string }) => api.post('/chat', data),
  qa: (data: { question: string; knowledge_base_id?: string; knowledge_base_ids?: string[]; provider?: string; model?: string }) => api.post('/qa', data),
}

export const agentApi = {
  run: (data: { query: string; system_prompt?: string; max_iterations?: number; provider?: string; model?: string }) => api.post('/agent/run', data),
}

export const memoryApi = {
  get: (conversationId: string) => api.get(`/memory/${conversationId}`),
  add: (conversationId: string, data: { role: string; content: string }) =>
    api.post(`/memory/${conversationId}/add`, data),
}

export const promptApi = {
  format: (data: { template: string; inputs: Record<string, string> }) => api.post('/prompt/format', data),
  listTemplates: () => api.get('/prompt/templates'),
  createTemplate: (data: { name: string; description?: string; template: string; category?: string }) => api.post('/prompt/templates', data),
  updateTemplate: (id: string, data: { name?: string; description?: string; template?: string; category?: string }) => api.put(`/prompt/templates/${id}`, data),
  deleteTemplate: (id: string) => api.delete(`/prompt/templates/${id}`),
  formatTemplate: (id: string, data: { inputs: Record<string, string> }) => api.post(`/prompt/templates/${id}/format`, data),
}

export const retrievalApi = {
  getPresets: () => api.get('/retrieval/config-presets'),
  retrieve: (data: { query: string; knowledge_base_id: string; top_k?: number }) => api.post('/retrieve', data),
}

export const appApi = {
  list: () => api.get('/apps'),
  create: (data: { name: string; mode?: string; description?: string; provider?: string; model?: string }) => api.post('/apps', data),
  get: (id: string) => api.get(`/apps/${id}`),
  update: (id: string, data: { name?: string; description?: string; provider?: string; model?: string }) => api.put(`/apps/${id}`, data),
  delete: (id: string) => api.delete(`/apps/${id}`),
}

export const conversationApi = {
  create: (data: { app_id: string; name?: string; system_prompt?: string; knowledge_base_id?: string; knowledge_base_ids?: string[]; role_id?: string }) => api.post('/conversations', data),
  list: (appId?: string) => api.get('/conversations', { params: { app_id: appId } }),
  get: (id: string) => api.get(`/conversations/${id}`),
  sendMessage: (id: string, data: { query: string; provider?: string; model?: string; knowledge_base_id?: string; knowledge_base_ids?: string[] }) => api.post(`/conversations/${id}/messages`, data),
  getMessages: (id: string) => api.get(`/conversations/${id}/messages`),
}

export const chatRoleApi = {
  list: () => api.get('/chat-roles'),
  create: (data: { request: string; knowledge_base_id?: string; knowledge_base_ids?: string[]; provider?: string; model?: string; name?: string; nickname?: string; role?: string; system_prompt?: string }) => api.post('/chat-roles', data),
  generatePrompt: (data: { role: string; name?: string; nickname?: string; provider?: string; model?: string }) => api.post('/chat-roles/generate-prompt', data),
}

export const authApi = {
  login: (data: { email: string; password: string }) => api.post('/auth/login', data),
  register: (data: { email: string; password: string; username?: string }) => api.post('/auth/register', data),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  updateChatContext: (data: { app_id?: string; role_id?: string; conversation_id?: string }) => api.post('/auth/chat-context', data),
  users: () => api.get('/auth/users'),
  changePassword: (data: { old_password: string; new_password: string }) => api.post('/auth/change-password', data),
  updateUser: (id: string, data: { role?: string; status?: string; name?: string }) => api.put(`/auth/users/${id}`, data),
  resetUserPassword: (id: string, data: { new_password: string }) => api.post(`/auth/users/${id}/reset-password`, data),
}

export const monitoringApi = {
  getStats: () => api.get('/monitoring/stats'),
  getHealth: () => api.get('/health'),
  getSystem: () => api.get('/monitoring/system'),
  getPlatform: () => api.get('/monitoring/platform'),
  getProcesses: () => api.get('/monitoring/processes'),
}

export const resourceConfigApi = {
  list: () => api.get('/resource-configs'),
  create: (data: { name: string; config_type: string; settings: Record<string, any> }) =>
    api.post('/resource-configs', data),
  get: (id: string) => api.get(`/resource-configs/${id}`),
  update: (id: string, data: { name: string; config_type: string; settings: Record<string, any> }) =>
    api.put(`/resource-configs/${id}`, data),
  delete: (id: string) => api.delete(`/resource-configs/${id}`),
}

export const modelProviderApi = {
  list: () => api.get('/model-providers'),
  createProvider: (data: { provider: string; label: string; models: Array<{ id: string; name: string }>; fields: string[]; supports_validate: boolean; credential_name?: string; credentials?: Record<string, any> }) =>
    api.post('/model-providers', data),
  updateProvider: (provider: string, data: { label: string; models: Array<{ id: string; name: string }>; fields: string[]; supports_validate: boolean }) =>
    api.put(`/model-providers/${provider}`, data),
  deleteProvider: (provider: string) => api.delete(`/model-providers/${provider}`),
  createModel: (provider: string, data: { model_id: string; name: string }) => api.post(`/model-providers/${provider}/models`, data),
  updateModel: (provider: string, data: { old_model_id: string; model_id: string; name: string }) => api.put(`/model-providers/${provider}/models`, data),
  deleteModel: (provider: string, data: { model_id: string; name: string }) => api.delete(`/model-providers/${provider}/models`, { data }),
  createCredential: (provider: string, data: { credentials: Record<string, any>; name?: string }) =>
    api.post(`/model-providers/${provider}/credentials`, data),
  updateCredential: (provider: string, data: { credential_id: string; credentials: Record<string, any>; name?: string }) =>
    api.put(`/model-providers/${provider}/credentials`, data),
  deleteCredential: (provider: string, data: { credential_id: string }) =>
    api.delete(`/model-providers/${provider}/credentials`, { data }),
  switchCredential: (provider: string, data: { credential_id: string }) =>
    api.post(`/model-providers/${provider}/credentials/switch`, data),
  validateCredential: (provider: string, data: { credentials: Record<string, any> }) =>
    api.post(`/model-providers/${provider}/credentials/validate`, data),
  setDefaultModel: (provider: string, data: { model: string }) =>
    api.post(`/model-providers/${provider}/default-model`, data),
}

export const componentConfigApi = {
  list: () => api.get('/component-configs'),
  update: (id: string, data: { enabled: boolean; config: Record<string, any> }) => api.put(`/component-configs/${id}`, data),
  test: (id: string) => api.post(`/component-configs/${id}/test`),
}

export const workflowApi = {
  list: (appId?: string) => api.get('/workflows', { params: { app_id: appId } }),
  create: (data: { app_id: string; name: string; description?: string }) => api.post('/workflows', data),
  get: (id: string) => api.get(`/workflows/${id}`),
  update: (id: string, data: { name?: string; description?: string; dsl?: Record<string, any> }) => api.put(`/workflows/${id}`, data),
  delete: (id: string) => api.delete(`/workflows/${id}`),
  versions: (id: string) => api.get(`/workflows/${id}/versions`),
  runs: (id: string) => api.get(`/workflows/${id}/runs`),
  runDetail: (id: string, runId: string) => api.get(`/workflows/${id}/runs/${runId}`),
  resumeRun: (id: string, runId: string, data?: { inputs?: Record<string, any> }) => api.post(`/workflows/${id}/runs/${runId}/resume`, data || {}),
  run: (id: string, data?: { inputs?: Record<string, any>; provider?: string; model?: string }) => api.post(`/workflows/${id}/run`, data || {}),
  streamUrl: (id: string) => `${API_BASE_URL}/workflows/${id}/run/stream`,
}

export const workspaceApi = {
  current: () => api.get('/workspace/current'),
  members: () => api.get('/workspace/members'),
}
