import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CreateKnowledgeBaseRequest, KnowledgeBase } from '@/types'
import { knowledgeBaseApi } from '@/api'

export const useKnowledgeBaseStore = defineStore('knowledgeBase', () => {
  const knowledgeBases = ref<KnowledgeBase[]>([])
  const loading = ref(false)
  const currentKb = ref<KnowledgeBase | null>(null)

  const fetchKnowledgeBases = async () => {
    loading.value = true
    try {
      const response = await knowledgeBaseApi.list()
      knowledgeBases.value = response.data
    } finally {
      loading.value = false
    }
  }

  const createKnowledgeBase = async (data: CreateKnowledgeBaseRequest) => {
    const response = await knowledgeBaseApi.create(data)
    knowledgeBases.value.push(response.data)
    return response.data
  }

  const deleteKnowledgeBase = async (id: string) => {
    await knowledgeBaseApi.delete(id)
    knowledgeBases.value = knowledgeBases.value.filter(kb => kb.id !== id)
  }

  const setCurrentKb = (kb: KnowledgeBase | null) => {
    currentKb.value = kb
  }

  return {
    knowledgeBases,
    loading,
    currentKb,
    fetchKnowledgeBases,
    createKnowledgeBase,
    deleteKnowledgeBase,
    setCurrentKb,
  }
})
