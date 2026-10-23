<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search,
  Bell,
  Plus,
  ClipboardList,
  ShieldAlert,
  Loader,
  CircleCheck
} from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import RiskBadge from '../components/RiskBadge.vue'
import StatusBadge from '../components/StatusBadge.vue'
import DonutChart from '../components/DonutChart.vue'
import { formatMoney } from '../utils/format'
import { pushToast } from '../composables/useToast'
import { syncStats, syncDocuments, syncApprovals } from '../api/realSync'

const router = useRouter()
const store = useAppStore()
const { state, markAllNotificationsRead } = store

const search = ref('')
const bellOpen = ref(false)
const bellRef = ref(null)

// 统计口径按角色数据权限过滤（Spec 4.2）
const scopedDocs = computed(() => store.visibleDocuments())

const riskDistribution = computed(() => {
  const rows = store.visibleRiskItems()
  return {
    high: rows.filter((item) => item.level === 'high').length,
    mid: rows.filter((item) => item.level === 'mid').length,
    low: rows.filter((item) => item.level === 'low').length
  }
})

const kpis = computed(() => [
  { key: 'pending', label: '待我审批', value: store.getApprovalQueue().length, icon: ClipboardList, color: '#2563EB', bg: '#2563EB1F' },
  { key: 'high', label: '高风险单据', value: scopedDocs.value.filter((doc) => doc.risk_level === 'high').length, icon: ShieldAlert, color: '#DC2626', bg: '#DC26261F' },
  { key: 'progress', label: '审批中单据', value: scopedDocs.value.filter((doc) => ['submitted', 'analyzing', 'pending_approval'].includes(doc.status)).length, icon: Loader, color: '#F59E0B', bg: '#F59E0B1F' },
  { key: 'done', label: '已完成单据', value: scopedDocs.value.filter((doc) => doc.status === 'completed').length, icon: CircleCheck, color: '#16A34A', bg: '#16A34A1F' }
])

const recentDocs = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  const rows = scopedDocs.value.slice(0, 6)
  if (!keyword) return rows
  return rows.filter((doc) =>
    [doc.doc_no, doc.title, doc.applicant_name, doc.doc_type].some((value) =>
      value.toLowerCase().includes(keyword)
    )
  )
})

const unreadCount = computed(() => state.notifications.filter((item) => !item.read).length)

function openDoc(id) {
  router.push(`/documents/${id}`)
}

function openNotifications() {
  bellOpen.value = !bellOpen.value
  if (bellOpen.value && unreadCount.value > 0) {
    markAllNotificationsRead()
  }
}

function openNotification(docId) {
  bellOpen.value = false
  router.push(`/documents/${docId}`)
}

function viewAllRisks() {
  router.push('/risks')
}

function openTodo(docId) {
  router.push(`/documents/${docId}`)
}

function handleBellOutside(event) {
  if (bellRef.value && !bellRef.value.contains(event.target)) {
    bellOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleBellOutside)
  if (store.state.notifications === undefined) {
    pushToast('演示数据已初始化', 'info')
  }
  Promise.all([syncStats(), syncDocuments(), syncApprovals()])
})
onBeforeUnmount(() => document.removeEventListener('click', handleBellOutside))
</script>

<template>
  <div class="dashboard">
    <header class="page-header">
      <div class="header-title-box">
        <div class="header-title">工作台</div>
        <div class="header-subtitle">财务单据智能风险审核系统</div>
      </div>

      <div class="header-actions">
        <div class="search-box">
          <Search :size="15" />
          <input v-model="search" type="text" placeholder="搜索单据编号 / 申请人" />
        </div>
        <div ref="bellRef" class="bell-wrap">
          <button class="bell-btn" type="button" aria-label="通知" @click.stop="openNotifications">
            <Bell :size="19" />
            <span v-if="unreadCount" class="bell-dot"></span>
          </button>
          <transition name="dropdown">
            <div v-if="bellOpen" class="bell-panel">
              <div class="bell-head">
                <span>通知</span>
                <span class="muted-sm">{{ state.notifications.length }} 条</span>
              </div>
              <button
                v-for="item in state.notifications"
                :key="item.id"
                type="button"
                class="bell-item"
                @click="openNotification(item.doc_id)"
              >
                <span class="bell-item-dot" :class="{ read: item.read }"></span>
                <span class="bell-item-body">
                  <span class="bell-item-title">{{ item.title }}</span>
                  <span class="bell-item-time">{{ item.time }}</span>
                </span>
              </button>
            </div>
          </transition>
        </div>
        <button class="btn btn-primary" type="button" @click="router.push('/documents/new')">
          <Plus :size="15" />
          <span>新建单据</span>
        </button>
      </div>
    </header>

    <div class="page-body dashboard-body">
      <div class="kpis">
        <div v-for="kpi in kpis" :key="kpi.key" class="kpi-card card">
          <div class="kpi-icon" :style="{ background: kpi.bg, color: kpi.color }">
            <component :is="kpi.icon" :size="22" />
          </div>
          <div class="kpi-text">
            <div class="kpi-value">{{ kpi.value }}</div>
            <div class="kpi-label">{{ kpi.label }}</div>
          </div>
        </div>
      </div>

      <div class="bottom">
        <section class="recent-card card">
          <h2 class="section-title">最近单据</h2>
          <div class="table-wrap recent-table-wrap">
            <div class="recent-table">
              <div class="table-row table-head">
                <div class="cell">单据编号</div>
                <div class="cell">类型</div>
                <div class="cell">申请人</div>
                <div class="cell">金额</div>
                <div class="cell">风险等级</div>
                <div class="cell">状态</div>
                <div class="cell">操作</div>
              </div>
              <div v-for="doc in recentDocs" :key="doc.id" class="table-row">
                <div class="cell strong">{{ doc.doc_no }}</div>
                <div class="cell">{{ doc.doc_type }}</div>
                <div class="cell">{{ doc.applicant_name }}</div>
                <div class="cell money">{{ formatMoney(doc.total_amount) }}</div>
                <div class="cell"><RiskBadge :level="doc.risk_level" /></div>
                <div class="cell"><StatusBadge :status="doc.status" /></div>
                <div class="cell"><button class="link" type="button" @click="openDoc(doc.id)">查看</button></div>
              </div>
              <div v-if="!recentDocs.length" class="empty-state">没有匹配的单据</div>
            </div>
          </div>
        </section>

        <aside class="risk-card card">
          <div class="risk-head">
            <h2 class="section-title">风险概览</h2>
            <button class="link link-sm" type="button" @click="viewAllRisks">查看全部</button>
          </div>

          <div class="donut-box">
            <DonutChart
              :high="riskDistribution.high"
              :mid="riskDistribution.mid"
              :low="riskDistribution.low"
            />
          </div>

          <div class="legend-row">
            <span class="dot" style="background: #dc2626"></span>
            <span class="legend-label">高风险</span>
            <span></span>
            <span class="legend-bar"><i style="background: #dc2626" :style="{ width: `${riskDistribution.high}px` }"></i></span>
            <span class="legend-count">{{ riskDistribution.high }}</span>
          </div>
          <div class="legend-row">
            <span class="dot" style="background: #f59e0b"></span>
            <span class="legend-label">中风险</span>
            <span></span>
            <span class="legend-bar"><i style="background: #f59e0b" :style="{ width: `${riskDistribution.mid}px` }"></i></span>
            <span class="legend-count">{{ riskDistribution.mid }}</span>
          </div>
          <div class="legend-row">
            <span class="dot" style="background: #16a34a"></span>
            <span class="legend-label">低风险</span>
            <span></span>
            <span class="legend-bar"><i style="background: #16a34a" :style="{ width: `${riskDistribution.low}px` }"></i></span>
            <span class="legend-count">{{ riskDistribution.low }}</span>
          </div>

          <h3 class="todo-title">待办提醒</h3>
          <button v-for="todo in state.todos" :key="todo.id" type="button" class="todo" @click="openTodo(todo.doc_id)">
            <span class="todo-dot" :style="{ background: todo.level === 'high' ? '#DC2626' : todo.level === 'mid' ? '#F59E0B' : '#667085' }"></span>
            <span>{{ todo.text }}</span>
          </button>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.dashboard-body {
  flex: 1;
  gap: 18px;
}

.search-box {
  width: 230px;
  height: 31px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
}

.search-box:focus-within {
  border-color: var(--primary);
  background: #fff;
}

.search-box input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 12px;
  color: var(--text-primary);
}

.search-box input::placeholder {
  color: #98a2b3;
}

.bell-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.bell-btn {
  position: relative;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  padding: 0;
}

.bell-dot {
  position: absolute;
  top: 0;
  right: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--high);
  border: 1px solid #fff;
}

.bell-panel {
  position: absolute;
  top: 34px;
  right: -60px;
  width: 300px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 12px 30px rgba(16, 24, 40, 0.14);
  padding: 8px;
  z-index: 50;
}

.bell-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px 8px;
  font-size: 13px;
  font-weight: 700;
}

.bell-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 9px 8px;
  border: none;
  background: transparent;
  border-radius: 6px;
  text-align: left;
}

.bell-item:hover {
  background: var(--bg);
}

.bell-item-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  margin-top: 5px;
  flex: none;
}

.bell-item-dot.read {
  background: #d0d5dd;
}

.bell-item-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bell-item-title {
  font-size: 12px;
  line-height: 16px;
  color: var(--text-primary);
}

.bell-item-time {
  font-size: 11px;
  color: #98a2b3;
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  flex: none;
}

.kpi-card {
  height: 84px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.kpi-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.kpi-value {
  font-size: 24px;
  line-height: 29px;
  font-weight: 700;
  color: var(--text-primary);
}

.kpi-label {
  font-size: 13px;
  line-height: 16px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.bottom {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.recent-card {
  flex: 1;
  min-width: 0;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.recent-table-wrap {
  flex: 1;
  min-height: 0;
}

.recent-table {
  min-width: 774px;
  display: flex;
  flex-direction: column;
}

.table-row {
  display: grid;
  grid-template-columns: 175px 104px 70px 130px 86px 82px minmax(127px, 1fr);
  align-items: center;
  height: 46px;
  border-bottom: 1px solid var(--border);
}

.table-row.table-head {
  height: 40px;
  background: #f9fafb;
  border-radius: 8px;
  border-bottom: none;
}

.cell {
  padding: 0 8px;
  font-size: 13px;
  line-height: 16px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-head .cell {
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  color: var(--text-secondary);
}

.cell.strong {
  font-weight: 700;
  overflow: visible;
}

.cell.money {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  overflow: visible;
}

.risk-card {
  width: 330px;
  flex: none;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.donut-box {
  height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.legend-row {
  display: grid;
  grid-template-columns: 8px 40px 1fr 192px 17px;
  align-items: center;
  gap: 8px;
  height: 16px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-label {
  font-size: 13px;
  line-height: 16px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.legend-bar {
  width: 192px;
  height: 6px;
  border-radius: 3px;
  background: #f2f4f7;
  overflow: hidden;
}

.legend-bar i {
  display: block;
  height: 6px;
  border-radius: 3px;
  max-width: 100%;
}

.legend-count {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.todo-title {
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.todo {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.todo:hover {
  color: var(--primary);
}

.todo-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex: none;
}

.todo span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
