<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ShieldCheck, User, Lock, Check, ChevronDown } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { pushToast } from '../composables/useToast'

const router = useRouter()
const route = useRoute()
const { state, login } = useAppStore()

const accounts = computed(() =>
  state.users.map((row) => ({ ...row, label: `${row.name}（${row.role} · ${row.dept}）` }))
)
const username = ref(state.rememberedUser || '')
const password = ref('')
const remember = ref(Boolean(state.rememberedUser))
const loading = ref(false)

function handleSubmit() {
  if (loading.value) return
  loading.value = true
  try {
    login(username.value, password.value, remember.value)
    pushToast('登录成功，欢迎回来')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    router.push(redirect)
  } catch (error) {
    pushToast(error.message || '登录失败，请重试', 'error')
  } finally {
    loading.value = false
  }
}

function forgotPassword() {
  pushToast('请联系系统管理员重置密码', 'info')
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="mark">
        <ShieldCheck :size="30" :stroke-width="2" />
      </div>
      <h1 class="login-title">财务单据智能风险审核系统</h1>
      <p class="login-subtitle">登录以继续使用 · 账号由管理员分配</p>

      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="field">
          <label class="label" for="username">用户名（演示账号）</label>
          <div class="input-wrap">
            <User :size="16" class="input-icon" />
            <select id="username" v-model="username" class="login-input login-select">
              <option value="" disabled>请选择登录账号</option>
              <option v-for="account in accounts" :key="account.id" :value="account.name">
                {{ account.label }}
              </option>
            </select>
            <ChevronDown :size="14" class="select-arrow" />
          </div>
        </div>

        <div class="field">
          <label class="label" for="password">密码</label>
          <div class="input-wrap">
            <Lock :size="16" class="input-icon" />
            <input
              id="password"
              v-model="password"
              class="login-input"
              type="password"
              autocomplete="current-password"
              placeholder="••••••••••"
            />
          </div>
        </div>

        <div class="options-row">
          <button class="remember" type="button" @click="remember = !remember">
            <span class="checkbox" :class="{ checked: remember }">
              <Check v-if="remember" :size="11" :stroke-width="3" />
            </span>
            <span>记住我</span>
          </button>
          <button class="forgot" type="button" @click="forgotPassword">忘记密码？</button>
        </div>

        <button class="login-btn" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登 录' }}
        </button>
      </form>

      <p class="login-foot">© 2026 财务风审平台 · 数据安全 · 全程审计</p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(180deg, #eff6ff 0%, #f4f6fa 100%);
}

.login-card {
  width: 420px;
  max-width: 100%;
  background: var(--card);
  border-radius: 16px;
  padding: 40px 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  box-shadow: 0 8px 32px rgba(16, 24, 40, 0.08);
}

.mark {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-title {
  margin: 0;
  font-size: 22px;
  line-height: 27px;
  font-weight: 700;
  color: var(--text-primary);
  text-align: center;
}

.login-subtitle {
  margin: 0;
  font-size: 13px;
  line-height: 16px;
  color: var(--text-secondary);
  text-align: center;
}

.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.label {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.input-wrap {
  height: 38px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 14px;
  background: #f9fafb;
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.input-wrap:focus-within {
  background: #fff;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.input-icon {
  color: var(--text-secondary);
  flex: none;
}

.login-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
}

.login-input::placeholder {
  color: #98a2b3;
}

.login-select {
  appearance: none;
  cursor: pointer;
}

.select-arrow {
  color: var(--text-secondary);
  flex: none;
  pointer-events: none;
}

.options-row {
  height: 15px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.remember {
  display: flex;
  align-items: center;
  gap: 7px;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.checkbox {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid #d0d5dd;
  background: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.checkbox.checked {
  background: var(--primary);
  border-color: var(--primary);
}

.forgot {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  color: var(--primary);
}

.login-btn {
  height: 42px;
  border: none;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  transition: background 0.15s ease;
}

.login-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}

.login-foot {
  margin: 0;
  font-size: 11px;
  line-height: 13px;
  color: #98a2b3;
  text-align: center;
}
</style>
