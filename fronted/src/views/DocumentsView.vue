<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Plus, FileText, Inbox } from 'lucide-vue-next'
import { DOC_TYPES } from '../data/seed'
import { useAppStore } from '../stores/appStore'
import RiskBadge from '../components/RiskBadge.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { formatMoney, statusInfo } from '../utils/format'
import { pushToast } from '../composables/useToast'

const router = useRouter()
const store = useAppStore()

const keyword = ref('')
const typeFilter = ref('全部类型')
const statusFilter = ref('全部状态')

const STATUS_FILTERS = [
  { value: 'draft', label: '草稿' },
  { value: 'submitted', label: '已提交' },
  { value: 'analyzing', label: '分析中' },
  { value: 'pending_approval', label: '审批中' },
  { value: 'returned', label: '已退回' },
  { value: 'rejected', label: '已驳回' },
  { value: 'approved', label: '已通过' },
  { value: 'completed', label: '已完成' }
]

// 数据权限（Spec 4.3）：按角色过滤可见单据
const documents = computed(() =>
  [...store.visibleDocuments()].sort((a, b) => (b.create_time || '').localeCompare(a.create_time || ''))
)

const filtered = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return documents.value.filter((doc) => {
    const matchType = typeFilter.value === '全部类型' || doc.doc_type === typeFilter.value
    const matchStatus = statusFilter.value === '全部状态' || doc.status === statusFilter.value
    const matchText =
      !text ||
      [doc.doc_no, doc.title, doc.applicant_name, doc.dept_name, doc.project].some((value) =>
        String(value || '').toLowerCase().includes(text)
      )
    return matchType && matchStatus && matchText
  })
})

const overview = computed(() => [
  { label: '全部单据', value: documents.value.length, color: '#2563EB', bg: '#EFF6FF' },
  {
    label: '审批中',
    value: documents.value.filter((doc) => doc.status === 'pending_approval').length,
    color: '#F59E0B',
    bg: '#FFFBEB'
  },
  {
    label: '高风险单据',
    value: documents.value.filter((doc) => doc.risk_level === 'high').length,
    color: '#DC2626',
    bg: '#FEF2F2'
  },
  {
    label: '已完成',
    value: documents.value.filter((doc) => doc.status === 'completed').length,
    color: '#16A34A',
    bg: '#F0FDF4'
  }
])

function openDoc(id) {
  router.push(`/documents/${id}`)
}

function hasReport(id) {
  return Boolean(store.getReportByDoc(id))
}

function editDoc(doc) {
  router.push(`/documents/${doc.id}`)
}

function withdrawDoc(doc) {
  if (!window.confirm('确定撤回该单据吗？撤回后将进入已退回状态，可修改后重新提交。')) return
  store.withdrawDocument(doc.id)
  pushToast('单据已撤回')
}

function resubmitDoc(doc) {
  store.resubmitDocument(doc.id)
  pushToast('单据已重新提交，版本号 +1')
}
</script>

<template>
  <div class="documents-page">
    <header class="page-header">
      <div class="header-title-box">
        <h1 class="header-title">单据管理</h1>
        <div class="header-subtitle">共 {{ documents.length }} 张单据 · 覆盖创建、审批、风险分析与归档全流程</div>
      </div>
      <div class="header-actions">
        <div class="search-box">
          <Search :size="15" />
          <input v-model="keyword" type="text" placeholder="搜索单据编号 / 标题 / 申请人" />
        </div>
        <div class="select-wrap">
          <select v-model="typeFilter" class="select" aria-label="单据类型">
            <option>全部类型</option>
            <option v-for="type in DOC_TYPES" :key="type">{{ type }}</option>
          </select>
        </div>
        <div class="select-wrap status-select">
          <select v-model="statusFilter" class="select" aria-label="单据状态">
            <option>全部状态</option>
            <option v-for="item in STATUS_FILTERS" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </div>
        <button class="btn btn-primary" type="button" @click="router.push('/documents/new')">
          <Plus :size="15" />
          <span>新建单据</span>
        </button>
      </div>
    </header>

    <div class="page-body">
      <div class="overview">
        <div v-for="item in overview" :key="item.label" class="overview-card card">
          <span class="overview-value" :style="{ color: item.color }">{{ item.value }}</span>
          <span class="overview-label">{{ item.label }}</span>
          <span class="overview-mark" :style="{ background: item.bg, color: item.color }">
            <FileText :size="17" />
          </span>
        </div>
      </div>

      <section class="list-card card">
        <div class="list-head">
          <div class="list-title-box">
            <h2 class="section-title">单据列表</h2>
            <span class="muted-sm">筛选结果 {{ filtered.length }} 张</span>
          </div>
          <span class="list-hint">金额由明细自动汇总 · 风险等级实时更新</span>
        </div>

        <div class="table-wrap">
          <table class="data-table doc-table">
            <thead>
              <tr>
                <th style="width: 158px">单据编号</th>
                <th style="width: 106px">单据类型</th>
                <th style="min-width: 190px">单据标题</th>
                <th style="width: 130px">申请人 / 部门</th>
                <th style="width: 124px">单据金额</th>
                <th style="width: 92px">风险等级</th>
                <th style="width: 90px">状态</th>
                <th style="width: 130px">当前节点</th>
                <th style="width: 142px">提交时间</th>
                <th style="width: 112px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="doc in filtered" :key="doc.id">
                <td>
                  <button class="doc-no" type="button" @click="openDoc(doc.id)">{{ doc.doc_no }}</button>
                </td>
                <td>{{ doc.doc_type }}</td>
                <td class="title-cell">
                  <span class="doc-title-text">{{ doc.title }}</span>
                  <span class="sub-text">{{ doc.project }}</span>
                </td>
                <td>
                  <span class="applicant">{{ doc.applicant_name }}</span>
                  <span class="sub-text">{{ doc.dept_name }}</span>
                </td>
                <td class="money">{{ formatMoney(doc.total_amount) }}</td>
                <td><RiskBadge :level="doc.risk_level" /></td>
                <td><StatusBadge :status="doc.status" /></td>
                <td class="node-cell">{{ doc.current_node || statusInfo(doc.status).text }}</td>
                <td class="time-cell">{{ doc.submit_time || '—' }}</td>
                <td>
                  <div class="row-actions">
                    <button class="link" type="button" @click="openDoc(doc.id)">查看</button>
                    <button
                      v-if="store.canEditDoc(doc)"
                      class="link"
                      type="button"
                      @click="editDoc(doc)"
                    >编辑</button>
                    <button
                      v-if="store.canWithdraw(doc)"
                      class="link"
                      type="button"
                      @click="withdrawDoc(doc)"
                    >撤回</button>
                    <button
                      v-if="store.canResubmit(doc)"
                      class="link"
                      type="button"
                      @click="resubmitDoc(doc)"
                    >重新提交</button>
                    <button
                      v-if="hasReport(doc.id)"
                      class="link"
                      type="button"
                      @click="router.push(`/reports/${doc.id}`)"
                    >报告</button>
                  </div>
                </td>
              </tr>
              <tr v-if="!filtered.length">
                <td colspan="10">
                  <div class="empty-state">
                    <Inbox :size="30" />
                    <span>没有匹配的单据，请调整筛选条件</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.documents-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.search-box {
  width: 248px;
  height: 34px;
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
  color: var(--text-muted);
}

.select-wrap {
  width: 116px;
}

.status-select {
  width: 110px;
}

.select-wrap .select {
  height: 34px;
  font-size: 12px;
}

.overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  flex: none;
}

.overview-card {
  position: relative;
  height: 78px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  overflow: hidden;
}

.overview-value {
  font-size: 24px;
  line-height: 28px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.overview-label {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.overview-mark {
  position: absolute;
  right: 18px;
  top: 20px;
  width: 36px;
  height: 36px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.list-card {
  flex: 1;
  min-width: 0;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.list-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.muted-sm {
  font-size: 12px;
  color: var(--text-muted);
}

.list-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.doc-table {
  min-width: 1120px;
}

.doc-no {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--primary);
}

.doc-no:hover {
  text-decoration: underline;
}

.title-cell {
  max-width: 260px;
}

.doc-title-text {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub-text {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  line-height: 13px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.applicant {
  display: block;
}

.node-cell {
  color: var(--text-secondary);
}

.time-cell {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.row-actions {
  display: flex;
  gap: 12px;
}

.row-actions .link {
  background: transparent;
  border: none;
  padding: 0;
  font-size: 12px;
}
</style>
