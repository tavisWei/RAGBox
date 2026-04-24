import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { App, Conversation, Message } from '@/types'
import { appApi, conversationApi } from '@/api'

export const useAppStore = defineStore('app', () => {
  const apps = ref<App[]>([])
  const conversations = ref<Conversation[]>([])
  const messages = ref<Message[]>([])
  const currentApp = ref<App | null>(null)
  const currentConversation = ref<Conversation | null>(null)

  const fetchApps = async () => {
    const response = await appApi.list()
    apps.value = response.data
  }

  const createApp = async (data: { name: string; mode?: string; description?: string }) => {
    const response = await appApi.create(data)
    apps.value.push(response.data)
    return response.data
  }

  const fetchConversations = async (_appId: string) => {
    conversations.value = []
  }

  const createConversation = async (appId: string, name?: string) => {
    const response = await conversationApi.create({ app_id: appId, name })
    conversations.value.push(response.data)
    return response.data
  }

  const sendMessage = async (conversationId: string, query: string) => {
    const response = await conversationApi.sendMessage(conversationId, { query })
    messages.value.push(response.data)
    return response.data
  }

  return {
    apps,
    conversations,
    messages,
    currentApp,
    currentConversation,
    fetchApps,
    createApp,
    fetchConversations,
    createConversation,
    sendMessage,
  }
})
