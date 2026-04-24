<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const isRegister = ref(false)
const form = ref({
  email: 'admin@example.com',
  password: 'admin',
  username: '',
})

const getErrorMessage = (error: unknown) => {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') {
      return response.data.detail
    }
  }
  return '操作失败'
}

const submit = async () => {
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(form.value.email, form.value.password, form.value.username || undefined)
      ElMessage.success('注册成功，请登录')
      isRegister.value = false
    }
    else {
      await auth.login(form.value.email, form.value.password)
      ElMessage.success('登录成功')
      await router.push('/')
    }
  }
  catch (error: unknown) {
    ElMessage.error(getErrorMessage(error))
  }
  finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- Decorative background elements -->
    <div class="bg-gradient-orb orb-1"></div>
    <div class="bg-gradient-orb orb-2"></div>
    <div class="bg-gradient-orb orb-3"></div>
    
    <div class="login-container">
      <!-- Left panel: Brand & Benefits -->
      <div class="brand-panel">
        <div class="brand-content">
          <div class="brand-logo">
            <div class="logo-icon">
              <el-icon size="32"><Collection /></el-icon>
            </div>
            <span class="logo-text">RAG Platform</span>
          </div>
          
          <h1 class="brand-headline">
            构建你的<br/>
            <span class="gradient-text">智能知识库</span>
          </h1>
          
          <p class="brand-description">
            私有化部署的专业知识问答平台，让 AI 读懂你的文档
          </p>
          
          <div class="benefits-list">
            <div class="benefit-item">
              <div class="benefit-icon blue">
                <el-icon><Document /></el-icon>
              </div>
              <div class="benefit-text">
                <div class="benefit-title">多源文档接入</div>
                <div class="benefit-desc">支持 PDF、Word、Markdown 等多种格式</div>
              </div>
            </div>
            
            <div class="benefit-item">
              <div class="benefit-icon green">
                <el-icon><Search /></el-icon>
              </div>
              <div class="benefit-text">
                <div class="benefit-title">智能检索增强</div>
                <div class="benefit-desc">向量 + 关键词 + 全文多路召回</div>
              </div>
            </div>
            
            <div class="benefit-item">
              <div class="benefit-icon purple">
                <el-icon><ChatDotRound /></el-icon>
              </div>
              <div class="benefit-text">
                <div class="benefit-title">自然语言问答</div>
                <div class="benefit-desc">基于知识库的精准 AI 对话</div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="brand-footer">
          <div class="tech-badges">
            <span class="badge">SQLite / PostgreSQL / ES</span>
            <span class="badge">三级资源适配</span>
          </div>
        </div>
      </div>
      
      <!-- Right panel: Auth Form -->
      <div class="auth-panel">
        <div class="auth-card">
          <div class="auth-header">
            <div class="auth-tabs">
              <button 
                class="auth-tab" 
                :class="{ active: !isRegister }"
                @click="isRegister = false"
              >
                登录
                <div class="tab-indicator" v-if="!isRegister"></div>
              </button>
              <button 
                class="auth-tab" 
                :class="{ active: isRegister }"
                @click="isRegister = true"
              >
                注册
                <div class="tab-indicator" v-if="isRegister"></div>
              </button>
            </div>
          </div>
          
          <div class="auth-body">
            <div class="welcome-text">
              <h2>{{ isRegister ? '创建账号' : '欢迎回来' }}</h2>
              <p>{{ isRegister ? '开始你的知识管理之旅' : '登录以访问你的知识库' }}</p>
            </div>
            
            <el-form :model="form" class="auth-form" @submit.prevent="submit">
              <div class="form-group">
                <label class="form-label">邮箱地址</label>
                <el-input 
                  v-model="form.email" 
                  placeholder="请输入邮箱"
                  size="large"
                  class="auth-input"
                >
                  <template #prefix>
                    <el-icon><Message /></el-icon>
                  </template>
                </el-input>
              </div>
              
              <div class="form-group" v-if="isRegister">
                <label class="form-label">用户名</label>
                <el-input 
                  v-model="form.username" 
                  placeholder="请输入用户名（可选）"
                  size="large"
                  class="auth-input"
                >
                  <template #prefix>
                    <el-icon><User /></el-icon>
                  </template>
                </el-input>
              </div>
              
              <div class="form-group">
                <label class="form-label">密码</label>
                <el-input 
                  v-model="form.password" 
                  type="password" 
                  show-password
                  placeholder="请输入密码"
                  size="large"
                  class="auth-input"
                  @keyup.enter="submit"
                >
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </div>
              
              <el-button 
                type="primary" 
                size="large"
                class="submit-btn" 
                :loading="loading" 
                @click="submit"
              >
                <span class="btn-text">{{ isRegister ? '创建账号' : '立即登录' }}</span>
                <el-icon class="btn-icon"><ArrowRight /></el-icon>
              </el-button>
            </el-form>
            
            <div class="auth-footer">
              <p class="switch-text">
                {{ isRegister ? '已有账号？' : '还没有账号？' }}
                <el-link type="primary" @click="isRegister = !isRegister" class="switch-link">
                  {{ isRegister ? '立即登录' : '免费注册' }}
                </el-link>
              </p>
            </div>
          </div>
        </div>
        
        <div class="auth-trust">
          <div class="trust-item">
            <el-icon><CircleCheck /></el-icon>
            <span>私有化部署</span>
          </div>
          <div class="trust-divider"></div>
          <div class="trust-item">
            <el-icon><Lock /></el-icon>
            <span>数据安全</span>
          </div>
          <div class="trust-divider"></div>
          <div class="trust-item">
            <el-icon><Unlock /></el-icon>
            <span>开源免费</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fafbfc 0%, #f0f4f8 50%, #e8f4f8 100%);
  position: relative;
  overflow: hidden;
  padding: 24px;
}

/* Decorative orbs */
.bg-gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
  animation: float 20s ease-in-out infinite;
}

.orb-1 {
  width: 600px;
  height: 600px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(147, 197, 253, 0.2));
  top: -200px;
  right: -100px;
  animation-delay: 0s;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(196, 181, 253, 0.15));
  bottom: -100px;
  left: -100px;
  animation-delay: -7s;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(134, 239, 172, 0.1));
  top: 50%;
  left: 30%;
  animation-delay: -14s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(30px, -30px) scale(1.05); }
  50% { transform: translate(-20px, 20px) scale(0.95); }
  75% { transform: translate(20px, 30px) scale(1.02); }
}

/* Main container */
.login-container {
  display: flex;
  width: 100%;
  max-width: 1100px;
  min-height: 640px;
  background: var(--rp-white);
  border-radius: var(--rp-radius-xl);
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.05),
    0 10px 15px -3px rgba(0, 0, 0, 0.08),
    0 25px 50px -12px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* Brand panel */
.brand-panel {
  flex: 1;
  background: linear-gradient(160deg, #1e3a5f 0%, #0f172a 50%, #1e1b4b 100%);
  padding: 48px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  color: var(--rp-white);
  position: relative;
  overflow: hidden;
}

.brand-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.15) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.1) 0%, transparent 50%);
  pointer-events: none;
}

.brand-content {
  position: relative;
  z-index: 1;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 40px;
}

.logo-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--rp-primary-500), var(--rp-primary-600));
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--rp-white);
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand-headline {
  font-size: 42px;
  font-weight: 800;
  line-height: 1.15;
  margin-bottom: 16px;
  letter-spacing: -0.03em;
}

.gradient-text {
  background: linear-gradient(135deg, #60a5fa, #a78bfa, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-description {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  margin-bottom: 48px;
  max-width: 360px;
}

.benefits-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.benefit-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.benefit-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--rp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 20px;
}

.benefit-icon.blue {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.benefit-icon.green {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.benefit-icon.purple {
  background: rgba(139, 92, 246, 0.2);
  color: #a78bfa;
}

.benefit-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.benefit-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
}

.brand-footer {
  position: relative;
  z-index: 1;
}

.tech-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.badge {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--rp-radius-full);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}

/* Auth panel */
.auth-panel {
  flex: 0 0 440px;
  padding: 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: var(--rp-white);
}

.auth-card {
  width: 100%;
}

.auth-header {
  margin-bottom: 32px;
}

.auth-tabs {
  display: flex;
  gap: 8px;
  background: var(--rp-gray-100);
  padding: 4px;
  border-radius: var(--rp-radius-md);
}

.auth-tab {
  flex: 1;
  padding: 10px 16px;
  border: none;
  background: transparent;
  color: var(--rp-gray-500);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--rp-radius-sm);
  transition: all var(--rp-transition-fast);
  position: relative;
}

.auth-tab:hover {
  color: var(--rp-gray-700);
}

.auth-tab.active {
  background: var(--rp-white);
  color: var(--rp-primary-600);
  box-shadow: var(--rp-shadow-sm);
}

.tab-indicator {
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 20px;
  height: 3px;
  background: var(--rp-primary-500);
  border-radius: 2px;
}

.auth-body {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.welcome-text h2 {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-heading);
  margin-bottom: 6px;
  letter-spacing: -0.02em;
}

.welcome-text p {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-heading);
}

.auth-input :deep(.el-input__wrapper) {
  border-radius: var(--rp-radius-md);
  box-shadow: 0 0 0 1px var(--rp-gray-200) inset;
  padding: 0 12px;
}

.auth-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--rp-primary-300) inset;
}

.auth-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--rp-primary-500) inset;
}

.auth-input :deep(.el-input__inner) {
  height: 44px;
  font-size: 14px;
}

.auth-input :deep(.el-input__prefix) {
  color: var(--rp-gray-400);
  margin-right: 8px;
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--rp-radius-md);
  margin-top: 8px;
  background: linear-gradient(135deg, var(--rp-primary-500), var(--rp-primary-600));
  border: none;
  position: relative;
  overflow: hidden;
}

.submit-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.submit-btn:hover::before {
  left: 100%;
}

.btn-text {
  margin-right: 4px;
}

.btn-icon {
  transition: transform var(--rp-transition-fast);
}

.submit-btn:hover .btn-icon {
  transform: translateX(3px);
}

.auth-footer {
  text-align: center;
  padding-top: 8px;
}

.switch-text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.switch-link {
  font-weight: 600;
}

/* Trust badges */
.auth-trust {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--rp-gray-100);
}

.trust-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--rp-gray-500);
}

.trust-item .el-icon {
  font-size: 14px;
  color: var(--rp-success-500);
}

.trust-divider {
  width: 4px;
  height: 4px;
  background: var(--rp-gray-300);
  border-radius: 50%;
}

/* Responsive */
@media (max-width: 900px) {
  .login-container {
    flex-direction: column;
    max-width: 440px;
  }
  
  .brand-panel {
    display: none;
  }
  
  .auth-panel {
    flex: 1;
    padding: 40px 32px;
  }
}

@media (max-width: 480px) {
  .login-page {
    padding: 16px;
    background: var(--rp-white);
  }
  
  .login-container {
    box-shadow: none;
    border-radius: 0;
    min-height: auto;
  }
  
  .auth-panel {
    padding: 24px 20px;
  }
  
  .auth-trust {
    flex-wrap: wrap;
    gap: 12px;
  }
  
  .trust-divider {
    display: none;
  }
}
</style>
