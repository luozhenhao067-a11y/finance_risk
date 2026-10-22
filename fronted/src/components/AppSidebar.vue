<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ShieldCheck,
  LayoutDashboard,
  FileText,
  ShieldAlert,
  ClipboardCheck,
  ChartPie,
  History,
  Settings,
  LogOut,
  RotateCcw
} from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { pushToast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const { state, logout, resetDemo, canViewApprovals, canViewLogs, canViewAdmin } = useAppStore()
const menuOpen = ref(false)
const userCardRef = ref(null)

const ALL_ITEMS = [
  { key: 'dashboard', label: '工作台', icon: LayoutDashboard, to: '/dashboard', roles: null },
  { key: 'documents', label: '单据管理', icon: FileText, to: '/documents', roles: null },
  { key: 'risks', label: '风险分析', icon: ShieldAlert, to: '/risks', roles: null },
  { key: 'approvals', label: '审批中心', icon: ClipboardCheck, to: '/approvals', roles: ['DEPT_MANAGER', 'FINANCE', 'ADMIN'] },
  { key: 'reports', label: '报告中心', icon: ChartPie, to: '/reports', roles: null },
  { key: 'logs', label: '审计日志', icon: History, to: '/logs', roles: ['FINANCE', 'ADMIN'] },
  { key: 'admin', label: '系统管理', icon: Settings, to: '/admin', roles: ['ADMIN'] }
]

const items = computed(() =>
  ALL_ITEMS.filter((item) => !item.roles || item.roles.includes(state.user?.role_code))
)

const activeMenu = computed(() => route.meta.menu || '')

function handleLogout() {
  menuOpen.value = false
  logout()
  router.push('/login')
}

function handleReset() {
  if (window.confirm('确定重置演示数据吗？当前修改将被清除。')) {
    resetDemo()
  }
}

function onDocumentClick(event) {
  if (userCardRef.value && !userCardRef.value.contains(event.target)) {
    menuOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))
</script>

<template>
  <aside class="sidebar">
    <div class="logo">
      <ShieldCheck :size="30" class="logo-icon" :stroke-width="2" />
      <span class="logo-text">财务风审平台</span>
    </div>

    <nav class="menu">
      <router-link
        v-for="item in items"
        :key="item.key"
        :to="item.to"
        class="menu-item"
        :class="{ active: activeMenu === item.key }"
      >
        <component :is="item.icon" :size="18" :stroke-width="2" class="menu-icon" />
        <span class="menu-label">{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="spacer"></div>

    <div ref="userCardRef" class="user-card-wrap">
      <transition name="pop">
        <div v-if="menuOpen" class="user-menu">
          <button class="user-menu-item" type="button" @click="handleLogout">
            <LogOut :size="15" />
            <span>退出登录</span>
          </button>
          <button class="user-menu-item" type="button" @click="handleReset">
            <RotateCcw :size="15" />
            <span>重置演示数据</span>
          </button>
        </div>
      </transition>
      <button class="user-card" type="button" @click.stop="menuOpen = !menuOpen">
        <span class="avatar">{{ state.user.avatar || state.user.name.slice(0, 1) }}</span>
        <span class="user-info">
          <span class="user-name">{{ state.user.name }}</span>
          <span class="user-role">{{ state.user.role }}</span>
        </span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 232px;
  height: 100vh;
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  z-index: 30;
  overflow: hidden;
}

.logo {
  height: 86px;
  flex: none;
  padding: 28px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--sidebar-icon-active);
}

.logo-icon {
  flex: none;
}

.logo-text {
  font-size: 17px;
  font-weight: 700;
  line-height: 21px;
  color: #fff;
  white-space: nowrap;
}

.menu {
  flex: none;
  padding: 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.menu-item {
  height: 38px;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 8px;
  color: var(--sidebar-text);
  transition: background 0.15s ease, color 0.15s ease;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #d0d5dd;
}

.menu-item.active {
  background: var(--sidebar-active);
  color: #fff;
}

.menu-item.active .menu-icon {
  color: var(--sidebar-icon-active);
}

.menu-icon {
  flex: none;
  color: inherit;
}

.menu-label {
  font-size: 13px;
  line-height: 16px;
  white-space: nowrap;
}

.menu-item.active .menu-label {
  font-weight: 500;
}

.spacer {
  flex: 1;
}

.user-card-wrap {
  position: relative;
  flex: none;
}

.user-card {
  width: 100%;
  height: 66px;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: transparent;
  border: none;
  text-align: left;
}

.user-card:hover {
  background: rgba(255, 255, 255, 0.04);
}

.avatar {
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: #fff;
}

.user-role {
  font-size: 11px;
  line-height: 13px;
  color: var(--sidebar-text);
  white-space: nowrap;
}

.user-menu {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 72px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 12px 30px rgba(16, 24, 40, 0.22);
  padding: 6px;
  z-index: 40;
}

.user-menu-item {
  width: 100%;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  border-radius: 6px;
  padding: 0 10px;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: left;
}

.user-menu-item:hover {
  background: var(--bg);
  color: var(--text-primary);
}

.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
