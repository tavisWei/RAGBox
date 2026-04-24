<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  ChatLineRound,
  Check,
  Document,
  InfoFilled,
  MagicStick,
  Plus,
  Promotion,
  Search,
  User,
} from '@element-plus/icons-vue'
import { API_BASE_URL, chatRoleApi, conversationApi, knowledgeBaseApi, modelProviderApi, promptApi } from '@/api'
import { withTimeout } from '@/api/client'
import { useClientPagination } from '@/composables/useClientPagination'
import { useAuthStore } from '@/stores/auth'
import type { Conversation, KnowledgeBase, ModelProvider } from '@/types'

interface ChatRole {
  id: string
  name: string
  nickname?: string
  role?: string
  request?: string
  system_prompt?: string
  knowledge_base_id?: string | null
  knowledge_base_ids?: string[]
}

interface ConversationMessageRecord {
  query: string
  answer?: string | null
}

interface ChatMessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
}

const createMessageId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`

const query = ref('')
const route = useRoute()
const auth = useAuthStore()
const messages = ref<ChatMessageItem[]>([])
const loading = ref(false)
const knowledgeBaseIds = ref<string[]>([])
const provider = ref('')
const model = ref('')
const knowledgeBases = ref<KnowledgeBase[]>([])
const providers = ref<ModelProvider[]>([])
const conversations = ref<Conversation[]>([])
const currentConversationId = ref('')
const roles = ref<ChatRole[]>([])
const roleId = ref('')
const roleDialogVisible = ref(false)
const historyDrawerVisible = ref(false)
const generatingPrompt = ref(false)
const roleForm = ref({ name: '', role: '', system_prompt: '', knowledge_base_ids: [] as string[] })
const roleProvider = ref('')
const roleModel = ref('')
const promptTemplates = ref<any[]>([])
const rolePromptTemplateId = ref('')
const chatMessagesRef = ref<HTMLElement | null>(null)

const CHAT_APP_ID_KEY = 'chat:lastAppId'
const CHAT_ROLE_ID_KEY = 'chat:lastRoleId'
const CHAT_CONVERSATION_ID_KEY = 'chat:lastConversationId'

const getRouteAppId = () => (typeof route.query.appId === 'string' && route.query.appId ? route.query.appId : '')

const getStoredChatContext = () => auth.user?.chat_context || {}

const getEffectiveAppId = () => getRouteAppId() || getStoredChatContext().app_id || localStorage.getItem(CHAT_APP_ID_KEY) || ''

const persistChatState = () => {
  const appId = getEffectiveAppId()
  if (appId)
    localStorage.setItem(CHAT_APP_ID_KEY, appId)
  else
    localStorage.removeItem(CHAT_APP_ID_KEY)

  if (roleId.value)
    localStorage.setItem(CHAT_ROLE_ID_KEY, roleId.value)
  else
    localStorage.removeItem(CHAT_ROLE_ID_KEY)

  if (currentConversationId.value)
    localStorage.setItem(CHAT_CONVERSATION_ID_KEY, currentConversationId.value)
  else
    localStorage.removeItem(CHAT_CONVERSATION_ID_KEY)

  authApi.updateChatContext({
    app_id: appId || undefined,
    role_id: roleId.value || undefined,
    conversation_id: currentConversationId.value || undefined,
  }).then((response) => {
    auth.user = response.data.user
  }).catch(() => {
  })
}

const clearConversationSelection = () => {
  currentConversationId.value = ''
  messages.value = []
  localStorage.removeItem(CHAT_CONVERSATION_ID_KEY)
}

const findRecentConversationForRole = () => {
  if (!roleId.value)
    return conversations.value.find(item => !item.role_id) || null
  return conversations.value.find(item => item.role_id === roleId.value) || null
}

const restoreConversationSelection = async () => {
  if (!conversations.value.length) {
    clearConversationSelection()
    return
  }

  const savedConversationId = localStorage.getItem(CHAT_CONVERSATION_ID_KEY) || ''
  const serverConversationId = getStoredChatContext().conversation_id || ''
  const matchesRole = (item: Conversation) => (roleId.value ? item.role_id === roleId.value : !item.role_id)
  const preferredConversationId = savedConversationId || serverConversationId
  const savedConversation = preferredConversationId
    ? conversations.value.find(item => item.id === preferredConversationId && matchesRole(item))
    : null
  const targetConversation = savedConversation || findRecentConversationForRole()

  if (targetConversation)
    await loadConversationMessages(targetConversation.id)
  else
    clearConversationSelection()
}

const currentModels = computed(() => {
  const current = providers.value.find(item => item.provider === provider.value)
  return current?.models || []
})

const currentRoleModels = computed(() => {
  const current = providers.value.find(item => item.provider === roleProvider.value)
  return current?.models || []
})

const currentRole = computed(() => roles.value.find(item => item.id === roleId.value))

const assistantName = computed(() => currentRole.value?.nickname || currentRole.value?.name || 'AI 助手')

const assistantInitial = computed(() => assistantName.value.trim().charAt(0) || 'A')

const effectiveKnowledgeBaseIds = computed(() => {
  return knowledgeBaseIds.value
})

const filteredConversations = computed(() => {
  if (!roleId.value)
    return conversations.value.filter(item => !item.role_id)
  return conversations.value.filter(item => item.role_id === roleId.value)
})

const selectedKnowledgeBaseNames = computed(() => knowledgeBases.value
  .filter(item => knowledgeBaseIds.value.includes(item.id))
  .map(item => item.name))

const onProviderChange = () => {
  model.value = ''
}

const onRoleProviderChange = () => {
  roleModel.value = ''
}

const applyRolePromptTemplate = () => {
  const selected = promptTemplates.value.find(item => item.id === rolePromptTemplateId.value)
  if (!selected) return
  roleForm.value.system_prompt = selected.template
}

const {
  currentPage: conversationPage,
  total: conversationTotal,
  paginatedItems: paginatedConversations,
  shouldPaginate: shouldPaginateConversations,
  resetPagination: resetConversationPagination,
} = useClientPagination(computed(() => filteredConversations.value.slice(0, 60)), 60)

const messageItems = computed(() => messages.value)
const {
  currentPage: messagePage,
  total: messageTotal,
  pageCount: messagePageCount,
  paginatedItems: paginatedMessages,
  shouldPaginate: shouldPaginateMessages,
} = useClientPagination(messageItems, 20)

const fetchOptions = async () => {
  const [kbRes, providerRes, roleRes, templateRes] = await Promise.all([
    knowledgeBaseApi.list(),
    modelProviderApi.list(),
    chatRoleApi.list(),
    promptApi.listTemplates(),
  ])
  knowledgeBases.value = kbRes.data
  providers.value = providerRes.data.data
  roles.value = roleRes.data.data || []
  promptTemplates.value = templateRes.data.data || []
}

const fetchConversations = async () => {
  const appId = getEffectiveAppId()
  if (!appId) {
    conversations.value = []
    return
  }
  localStorage.setItem(CHAT_APP_ID_KEY, appId)
  const response = await conversationApi.list(appId)
  conversations.value = response.data
}

const ensureConversation = async () => {
  if (currentConversationId.value)
    return currentConversationId.value
  const appId = getEffectiveAppId()
  if (!appId)
    return ''
  const role = roles.value.find(item => item.id === roleId.value)
  const kbIds = effectiveKnowledgeBaseIds.value
  const response = await conversationApi.create({
    app_id: appId,
    name: role ? `${role.name}会话` : '新会话',
    system_prompt: role?.system_prompt,
    knowledge_base_id: kbIds[0] || undefined,
    knowledge_base_ids: kbIds,
    role_id: role?.id,
  })
  currentConversationId.value = response.data.id
  persistChatState()
  await fetchConversations()
  return currentConversationId.value
}

const loadConversationMessages = async (conversationId: string) => {
  currentConversationId.value = conversationId
  const response = await conversationApi.getMessages(conversationId)
  messages.value = response.data.flatMap((item: ConversationMessageRecord) => ([
    { id: createMessageId(), role: 'user', content: item.query },
    { id: createMessageId(), role: 'assistant', content: item.answer || '' },
  ]))
  persistChatState()
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
  }
}

watch(messages, () => {
  messagePage.value = messagePageCount.value
  scrollToBottom()
}, { deep: true })
watch(loading, scrollToBottom)

const sendMessage = async () => {
  if (!query.value.trim()) return
  if (!provider.value) {
    ElMessage.warning('请选择模型提供商或先添加供应商')
    return
  }
  if (!model.value) {
    ElMessage.warning('请选择要调用的模型')
    return
  }

  const userMessage = query.value
  let assistantMessage: ChatMessageItem | null = null
  messages.value.push({ id: createMessageId(), role: 'user', content: userMessage })
  query.value = ''
  loading.value = true

  try {
    const conversationId = await ensureConversation()
    if (conversationId) {
      assistantMessage = { id: createMessageId(), role: 'assistant', content: '', isStreaming: true }
      messages.value.push(assistantMessage)
      const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          query: userMessage,
          provider: provider.value || undefined,
          model: model.value || undefined,
          knowledge_base_id: effectiveKnowledgeBaseIds.value[0] || undefined,
          knowledge_base_ids: effectiveKnowledgeBaseIds.value,
        }),
      })
      if (!response.ok || !response.body)
        throw new Error('stream failed')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        assistantMessage.content += decoder.decode(value, { stream: true })
        await nextTick()
        scrollToBottom()
      }
      assistantMessage.isStreaming = false
      await fetchConversations()
    }
    else {
      assistantMessage = { id: createMessageId(), role: 'assistant', content: '', isStreaming: true }
      messages.value.push(assistantMessage)
      const response = await fetch(`${API_BASE_URL}/qa/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          question: userMessage,
          knowledge_base_id: effectiveKnowledgeBaseIds.value[0] || undefined,
          knowledge_base_ids: effectiveKnowledgeBaseIds.value,
          provider: provider.value || undefined,
          model: model.value || undefined,
        }),
      })
      if (!response.ok || !response.body)
        throw new Error('stream failed')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        assistantMessage.content += decoder.decode(value, { stream: true })
        await nextTick()
        scrollToBottom()
      }
      assistantMessage.isStreaming = false
    }
  } catch {
    ElMessage.error('发送失败')
    if (assistantMessage) {
      assistantMessage.isStreaming = false
      assistantMessage.content = '抱歉，发生了错误，请稍后重试。'
    }
    else {
      messages.value.push({
        id: createMessageId(),
        role: 'assistant',
        content: '抱歉，发生了错误，请稍后重试。',
      })
    }
  } finally {
    loading.value = false
  }
}

const generateRolePrompt = async () => {
  if (!roleForm.value.role.trim()) {
    ElMessage.warning('请先输入角色')
    return
  }
  if (!(roleProvider.value || provider.value)) {
    ElMessage.warning('请选择模型提供商或先添加供应商')
    return
  }
  if (!(roleModel.value || model.value)) {
    ElMessage.warning('请选择要调用的模型')
    return
  }
  generatingPrompt.value = true
  try {
    const response = await withTimeout(
      chatRoleApi.generatePrompt({
        name: roleForm.value.name || undefined,
        nickname: roleForm.value.name || undefined,
        role: roleForm.value.role,
        provider: roleProvider.value || provider.value || undefined,
        model: roleModel.value || model.value || undefined,
      }),
      30000,
    )
    roleForm.value.name = roleForm.value.name || response.data.data.name
    roleForm.value.system_prompt = response.data.data.system_prompt
  } catch {
    ElMessage.error('生成角色提示词失败')
  } finally {
    generatingPrompt.value = false
  }
}

const createRole = async () => {
  if (!roleForm.value.name.trim() || !roleForm.value.role.trim()) {
    ElMessage.warning('请输入昵称和角色')
    return
  }
  const response = await chatRoleApi.create({
    name: roleForm.value.name,
    nickname: roleForm.value.name,
    role: roleForm.value.role,
    request: roleForm.value.role,
    system_prompt: roleForm.value.system_prompt || undefined,
    knowledge_base_ids: roleForm.value.knowledge_base_ids,
    provider: roleProvider.value || provider.value || undefined,
    model: roleModel.value || model.value || undefined,
  })
  roles.value.unshift(response.data.data)
  roleId.value = response.data.data.id
  knowledgeBaseIds.value = response.data.data.knowledge_base_ids || []
  roleDialogVisible.value = false
  roleForm.value = { name: '', role: '', system_prompt: '', knowledge_base_ids: [] }
  roleProvider.value = ''
  roleModel.value = ''
  rolePromptTemplateId.value = ''
  clearConversationSelection()
  persistChatState()
  ElMessage.success('角色已创建并切换')
}

const onRoleChange = async () => {
  const role = roles.value.find(item => item.id === roleId.value)
  knowledgeBaseIds.value = role?.knowledge_base_ids || (role?.knowledge_base_id ? [role.knowledge_base_id] : [])
  persistChatState()
  await fetchConversations()
  await restoreConversationSelection()
}

const startNewConversation = () => {
  clearConversationSelection()
}

const openHistory = () => {
  historyDrawerVisible.value = true
}

onMounted(() => {
  fetchOptions().then(() => {
    const savedRoleId = getStoredChatContext().role_id || localStorage.getItem(CHAT_ROLE_ID_KEY) || ''
    const routeProvider = route.query.provider
    const routeModel = route.query.model
    if (typeof routeProvider === 'string')
      provider.value = routeProvider
    if (typeof routeModel === 'string')
      model.value = routeModel
    if (savedRoleId)
      roleId.value = savedRoleId
  }).then(async () => {
    await fetchConversations()
    await restoreConversationSelection()
  })
})

watch(conversations, () => {
  resetConversationPagination()
})

watch(roleId, () => {
  resetConversationPagination()
})

watch(() => route.query.appId, async () => {
  persistChatState()
  await fetchConversations()
  await restoreConversationSelection()
})
</script>

<template>
  <div class="chat-page">
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <div>
          <div class="sidebar-title">角色</div>
          <div class="sidebar-subtitle">创建并切换聊天角色</div>
        </div>
        <el-button type="primary" class="sidebar-new-btn" @click="roleDialogVisible = true">
          <el-icon><Plus /></el-icon>
          创建角色
        </el-button>
      </div>

      <div class="sidebar-section sidebar-roles">
        <div class="sidebar-section-title">角色选择</div>
        <div class="role-list">
          <button :class="['role-list-item', { active: !roleId }]" @click="roleId = ''; onRoleChange()">
            <span class="role-avatar">AI</span>
            <span class="role-meta">
              <strong>默认助手</strong>
              <small>不选择角色</small>
            </span>
          </button>
          <button v-for="role in roles" :key="role.id" :class="['role-list-item', { active: roleId === role.id }]" @click="roleId = role.id; onRoleChange()">
            <span class="role-avatar">{{ (role.nickname || role.name || 'A').trim().charAt(0) }}</span>
            <span class="role-meta">
              <strong>{{ role.name }}</strong>
              <small>{{ role.role || '聊天角色' }}</small>
            </span>
          </button>
        </div>
      </div>
    </aside>

    <div class="chat-container">
      <div class="chat-header">
        <div class="header-left">
          <div class="header-title">
            <el-icon size="20" class="header-icon"><ChatDotRound /></el-icon>
            <span>知识库问答</span>
          </div>
          <div v-if="currentRole" class="header-role">
            <el-tag size="small" type="primary" effect="light">
              <el-icon size="12"><User /></el-icon>
              {{ currentRole.name }}
            </el-tag>
          </div>
        </div>
        <div class="selectors">
          <el-button class="history-btn" @click="openHistory">
            <el-icon><ChatLineRound /></el-icon>
            历史对话
          </el-button>
          <el-select v-model="knowledgeBaseIds" placeholder="选择知识库" multiple collapse-tags collapse-tags-tooltip clearable style="width: 240px">
            <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </div>
      </div>

      <el-drawer v-model="historyDrawerVisible" title="历史对话" size="340px">
        <div class="history-panel">
          <div class="history-summary">
            {{ currentRole ? assistantName : '默认助手' }} · 最近 {{ Math.min(filteredConversations.length, 60) }} 个对话
          </div>
          <div class="conversation-list">
            <div
              v-for="item in paginatedConversations"
              :key="item.id"
              :class="['conversation-item', { active: currentConversationId === item.id }]"
              @click="loadConversationMessages(item.id)"
            >
              <div class="conversation-icon">
                <el-icon size="16"><ChatLineRound /></el-icon>
              </div>
              <div class="conversation-body">
                <div class="conversation-name">{{ item.name || '未命名会话' }}</div>
                <div class="conversation-meta">
                  <span>{{ item.message_count }} 条消息</span>
                  <span class="conversation-dot">·</span>
                  <span>{{ new Date(item.updated_at || item.created_at || Date.now()).toLocaleString() }}</span>
                </div>
              </div>
            </div>
            <el-empty v-if="filteredConversations.length === 0" description="暂无会话" :image-size="60" />

            <div v-if="shouldPaginateConversations" class="sidebar-pagination">
              <el-pagination
                v-model:current-page="conversationPage"
                :total="conversationTotal"
                :page-size="60"
                size="small"
                layout="prev, pager, next"
                :hide-on-single-page="true"
              />
            </div>
          </div>
        </div>
      </el-drawer>

      <div class="chat-messages" ref="chatMessagesRef">
        <div v-if="messages.length === 0 && !loading" class="empty-chat">
          <div class="empty-illustration">
            <el-icon size="56" color="var(--rp-primary-300)"><ChatDotRound /></el-icon>
          </div>
          <div class="empty-title">开始一段新对话</div>
          <div class="empty-desc">
            选择知识库和模型，然后输入您的问题<br>
            AI 将基于知识库内容为您解答
          </div>
          <div class="empty-hints">
            <div class="hint-chip" @click="query = '这个知识库主要包含哪些内容？'">
              <el-icon><Search /></el-icon>
              这个知识库主要包含哪些内容？
            </div>
            <div class="hint-chip" @click="query = '总结一下核心观点'">
              <el-icon><Document /></el-icon>
              总结一下核心观点
            </div>
          </div>
        </div>

        <template v-else>
          <div
            v-for="msg in paginatedMessages"
            :key="msg.id"
            :class="['message-row', msg.role]"
          >
            <div class="message-avatar">
              <div v-if="msg.role === 'user'" class="avatar-user">
                <el-icon size="16"><User /></el-icon>
              </div>
              <div v-else class="avatar-ai">
                {{ assistantInitial }}
              </div>
            </div>
            <div class="message-bubble">
              <div class="message-sender">{{ msg.role === 'user' ? '我' : assistantName }}</div>
              <div v-if="msg.isStreaming && !msg.content" class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <div v-else class="message-text">{{ msg.content }}</div>
            </div>
          </div>
        </template>

        <div v-if="shouldPaginateMessages" class="messages-pagination">
          <el-pagination
            v-model:current-page="messagePage"
            :total="messageTotal"
            :page-size="20"
            size="small"
            layout="prev, pager, next"
            :hide-on-single-page="true"
          />
        </div>
      </div>

      <!-- Input -->
      <div class="chat-input-area">
        <div class="input-config-row">
          <div class="selected-kbs">
            <el-tag v-for="name in selectedKnowledgeBaseNames" :key="name" size="small" effect="plain">{{ name }}</el-tag>
            <span v-if="selectedKnowledgeBaseNames.length === 0" class="muted-config">未选择知识库</span>
          </div>
          <div class="bottom-model-selectors">
            <el-button @click="startNewConversation">
              <el-icon><Plus /></el-icon>
              新建对话
            </el-button>
            <el-select v-model="provider" placeholder="模型提供商" clearable style="width: 150px" @change="onProviderChange">
              <el-option v-for="item in providers" :key="item.provider" :label="item.label" :value="item.provider" />
            </el-select>
            <el-select v-model="model" placeholder="模型" clearable style="width: 180px">
              <el-option v-for="item in currentModels" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </div>
        </div>
        <div class="input-wrapper">
          <el-input
            v-model="query"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="输入您的问题..."
            @keyup.enter.ctrl="sendMessage"
          />
          <div class="input-actions">
            <div class="input-hint">
              <el-icon size="12"><InfoFilled /></el-icon>
              <span>Ctrl + Enter 发送</span>
            </div>
            <el-button
              type="primary"
              :loading="loading"
              :disabled="!query.trim()"
              @click="sendMessage"
              class="send-btn"
            >
              <el-icon><Promotion /></el-icon>
              发送
            </el-button>
          </div>
        </div>
      </div>

      <!-- Role Dialog -->
      <el-dialog v-model="roleDialogVisible" title="创建聊天角色" width="560px" class="role-dialog">
        <div class="role-dialog-body">
          <el-form :model="roleForm" label-width="100px">
            <el-form-item label="昵称">
              <el-input v-model="roleForm.name" placeholder="例如：小投、英语教练、产品顾问" />
            </el-form-item>
            <el-form-item label="角色">
              <el-input
                v-model="roleForm.role"
                type="textarea"
                :rows="3"
                placeholder="例如：一个熟悉我私人知识库的投资顾问 / 英语口语教练 / 产品经理"
              />
            </el-form-item>
            <el-form-item label="生成模型">
              <div class="role-model-row">
                <el-select v-model="roleProvider" placeholder="模型提供商" clearable style="width: 48%" @change="onRoleProviderChange">
                  <el-option v-for="item in providers" :key="item.provider" :label="item.label" :value="item.provider" />
                </el-select>
                <el-select v-model="roleModel" placeholder="模型" clearable style="width: 48%">
                  <el-option v-for="item in currentRoleModels" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
              </div>
            </el-form-item>
            <el-form-item label="角色提示词">
              <div class="prompt-field">
                <el-select v-model="rolePromptTemplateId" placeholder="选择提示词模板（可选）" clearable @change="applyRolePromptTemplate">
                  <el-option v-for="item in promptTemplates" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
                <el-button :loading="generatingPrompt" @click="generateRolePrompt">
                  <el-icon><MagicStick /></el-icon>
                  根据角色生成角色提示词
                </el-button>
                <el-input
                  v-model="roleForm.system_prompt"
                  type="textarea"
                  :rows="5"
                  placeholder="点击上方按钮生成，或手动输入角色定位提示词"
                />
              </div>
            </el-form-item>
            <el-form-item label="私人知识库">
              <el-select v-model="roleForm.knowledge_base_ids" multiple clearable collapse-tags collapse-tags-tooltip style="width: 100%" placeholder="可不选，也可多选">
                <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>
        <template #footer>
          <el-button @click="roleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="createRole">
            <el-icon><Check /></el-icon>
            创建并切换
          </el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: calc(100vh - var(--header-height) - var(--page-padding) * 2);
  min-height: 500px;
  gap: 16px;
}

.chat-sidebar {
  width: 320px;
  min-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--rp-radius-lg);
  box-shadow: var(--rp-shadow-sm);
  overflow: hidden;
}

.sidebar-header,
.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-header {
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border-light);
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
}

.sidebar-subtitle,
.sidebar-count {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.sidebar-new-btn,
.role-create-btn {
  width: 100%;
  font-weight: 500;
}

.sidebar-roles {
  flex: 1;
  min-height: 0;
}

.sidebar-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-heading);
}

.role-list,
.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
}

.role-list {
  max-height: 100%;
}

.role-list-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--rp-radius-md);
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: all var(--rp-transition-fast);
}

.role-list-item:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-border);
}

.role-list-item.active {
  background: var(--color-surface-active);
  border-color: var(--rp-primary-200);
}

.role-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--rp-radius-md);
  background: var(--rp-primary-50);
  color: var(--rp-primary-500);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.role-list-item.active .role-avatar {
  background: var(--rp-primary-500);
  color: var(--rp-white);
}

.role-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.role-meta strong,
.role-meta small {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role-meta small {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.sidebar-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}

.conversation-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border-radius: var(--rp-radius-md);
  cursor: pointer;
  transition: all var(--rp-transition-fast);
  border: 1px solid transparent;
}

.conversation-item:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-border);
}

.conversation-item.active {
  background: var(--color-surface-active);
  border-color: var(--rp-primary-200);
}

.conversation-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--rp-radius-md);
  background: var(--rp-primary-50);
  color: var(--rp-primary-500);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.conversation-item.active .conversation-icon {
  background: var(--rp-primary-500);
  color: var(--rp-white);
}

.conversation-body {
  flex: 1;
  min-width: 0;
}

.conversation-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-meta {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.conversation-dot {
  opacity: 0.5;
}

/* ---- Chat Container ---- */
.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--rp-radius-lg);
  box-shadow: var(--rp-shadow-sm);
  overflow: hidden;
}

/* ---- Header ---- */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-heading);
}

.header-icon {
  color: var(--rp-primary-500);
}

.header-role :deep(.el-tag) {
  border-radius: var(--rp-radius-sm);
  font-weight: 500;
}

.selectors {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.selector-divider {
  width: 1px;
  height: 24px;
  background: var(--color-border);
}

.history-btn,
.role-btn {
  font-weight: 500;
}

/* ---- Messages ---- */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  background: var(--color-background-canvas);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.messages-pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

/* Empty state */
.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  padding: 40px 20px;
}

.empty-illustration {
  width: 96px;
  height: 96px;
  border-radius: var(--rp-radius-xl);
  background: var(--rp-primary-50);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-heading);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.7;
  margin-bottom: 24px;
}

.empty-hints {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.hint-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--rp-radius-full);
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--rp-transition-fast);
}

.hint-chip:hover {
  background: var(--color-surface-active);
  border-color: var(--rp-primary-300);
  color: var(--rp-primary-600);
}

/* Message rows */
.message-row {
  display: flex;
  gap: 12px;
  animation: messageIn 0.3s ease-out;
}

.message-row.user {
  flex-direction: row-reverse;
}

@keyframes messageIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-avatar {
  flex-shrink: 0;
}

.avatar-user,
.avatar-ai {
  width: 36px;
  height: 36px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-user {
  background: var(--rp-primary-500);
  color: var(--rp-white);
}

.avatar-ai {
  background: var(--rp-coral-50);
  color: var(--rp-coral-500);
  border: 1px solid var(--rp-coral-100);
  font-size: 14px;
  font-weight: 700;
}

.message-bubble {
  max-width: 75%;
  padding: 14px 18px;
  border-radius: var(--rp-radius-lg);
  line-height: 1.7;
}

.message-row.user .message-bubble {
  background: var(--rp-primary-500);
  color: var(--rp-white);
  border-bottom-right-radius: var(--rp-radius-sm);
}

.message-row.assistant .message-bubble {
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: var(--rp-radius-sm);
}

.message-sender {
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 6px;
  opacity: 0.7;
}

.message-text {
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Loading indicator */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--rp-primary-300);
  animation: typingBounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ---- Input Area ---- */
.chat-input-area {
  padding: 16px 20px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-surface);
  flex-shrink: 0;
}

.input-config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.selected-kbs,
.bottom-model-selectors {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.muted-config {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-wrapper :deep(.el-textarea__inner) {
  border-radius: var(--rp-radius-md) !important;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.input-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.send-btn {
  font-weight: 500;
  padding: 8px 20px;
}

/* ---- Role Dialog ---- */
.role-dialog-body {
  padding: 8px 0;
}

.prompt-field {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.role-model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

/* Responsive */
@media (max-width: 1024px) {
  .chat-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .chat-page {
    flex-direction: column;
    height: auto;
  }

  .chat-sidebar {
    width: 100%;
    min-width: 0;
    max-height: 360px;
  }

  .selectors {
    width: 100%;
    justify-content: flex-start;
  }

  .input-config-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
