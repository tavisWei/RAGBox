export interface KnowledgeBase {
  id: string
  name: string
  description?: string
  embedding_model: string
  document_count: number
  hardware_tier?: string
  rag_plan?: string
  embedding_provider?: string
  recommended_backend?: string
  vector_backend?: string
  rag_architecture?: string
  reindex_required?: boolean
  splitter_config?: Record<string, any>
  retrieval_config?: Record<string, any>
}

export interface CreateKnowledgeBaseRequest {
  name: string
  description?: string
  embedding_model?: string
  rag_plan?: string
}

export interface RagPlanPreset {
  key: string
  name: string
  summary: string
  cost_level: string
  quality_level: string
  datastore_note?: string
  best_for: string[]
  tradeoffs: string[]
  hardware_tier: string
  architecture?: string
  recommended_backend?: string
  vector_backend?: string
  embedding_provider?: string
  embedding_model: string
  splitter_config: Record<string, any>
  retrieval_config: Record<string, any>
}

export interface App {
  id: string
  name: string
  mode: string
  description?: string
  provider?: string
  model?: string
}

export interface Conversation {
  id: string
  app_id: string
  name?: string
  message_count: number
  role_id?: string
  knowledge_base_id?: string
  knowledge_base_ids?: string[]
  created_at?: string
  updated_at?: string
}

export interface Message {
  id: string
  conversation_id: string
  query: string
  answer?: string
}

export interface ChatResponse {
  answer: string
  sources: Array<{
    content: string
    score: number
    metadata: Record<string, any>
  }>
  conversation_id: string
}

export interface AgentRunResponse {
  answer: string
  iterations: number
}

export interface MemoryMessage {
  role: string
  content: string
}

export interface RetrievalPreset {
  name: string
  config: Record<string, any>
}

export interface User {
  id: string
  username: string
  email?: string
  name?: string
  role: string
  chat_context?: {
    app_id?: string | null
    role_id?: string | null
    conversation_id?: string | null
    updated_at?: string | null
  }
}

export interface ModelProviderCredential {
  id: string
  name: string
  credentials: Record<string, any>
  created_at: string
}

export interface ProviderModel {
  id: string
  name: string
}

export interface ModelProvider {
  provider: string
  label: string
  models: ProviderModel[]
  fields: string[]
  supports_validate: boolean
  credentials: ModelProviderCredential[]
  active_credential_id?: string | null
  default_model?: string | null
  editable?: boolean
}
