import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref(localStorage.getItem('token'))
  const isAuthenticated = computed(() => !!token.value)

  const login = async (email: string, password: string) => {
    const response = await authApi.login({ email, password })
    const data = response.data
    if (data.access_token) {
      token.value = data.access_token
      localStorage.setItem('token', data.access_token)
      user.value = data.user
    }
    return data
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } catch {
    }
    user.value = null
    token.value = null
    localStorage.removeItem('token')
  }

  const register = async (email: string, password: string, username?: string) => {
    return authApi.register({ email, password, username })
  }

  const fetchUser = async () => {
    try {
      const response = await authApi.me()
      user.value = response.data
    } catch {
      await logout()
    }
  }

  const setUser = (nextUser: User | null) => {
    user.value = nextUser
  }

  return { user, token, isAuthenticated, login, logout, register, fetchUser, setUser }
})
