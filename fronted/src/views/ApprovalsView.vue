<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Paperclip,
  RotateCcw,
  X,
  Check
} from 'lucide-vue-next'
import { DOC_TYPES } from '../data/seed'
import { useAppStore } from '../stores/appStore'
import RiskBadge from '../components/RiskBadge.vue'
import { formatMoney, riskInfo } from '../utils/format'
import { pushToast } from '../composables/useToast'

const router = useRouter()
const store = useAppStore()

const filterType = ref('全部类型')
const selectedId = ref('')
const opinion = ref('')

const queue = computed(() => {
  const all = store.getApprovalQueue()
  if (filterType.value === '全部类型') return all
  return all.filter((doc) => doc.doc_type === filterType.value)
})

watch(
  queue,
  (list) => {
    if (!list.find((doc) => doc.id === selectedId.value)) {
      selectedId.value = list[0]?.id || ''
    }
  },
  { immediate: true }
)

const selected = computed(() => queue.value.find((doc) => doc.id === selectedId.value) || null)
const selectedDetails = computed(() => (selected.value ? store.getDetails(selected.value.id) : []))
const selectedAttachments = computed(() => (selected.value ? store.getAttachments(selected.value.id) : []))
const selectedRisks = computed(() => (selected.value ? store.getRiskItems(selected.value.id) : []))
const selectedAnalysis = computed(() => (selected.value ? store.getRiskAnalysis(selected.value.id) : null))
const selectedRiskInfo = computed(() => riskInfo(selectedAnalysis.value?.overall_level || 'none'))

const progress = computed(() => {
  if (!selected.value) return []
  const currentNode = selected.value.current_node
  const chain = store.getFlowChain(selected.value)
  const doneSet = new Set(
    store.getTasks(selected.value.id).filter((task) => task.status === 'done').map((task) => task.node)
  )
  const short = { 部门负责人审批: '部门负责人', 分管副总审批: '分管副总', 财务审核: '财务审核' }
  return chain.map((name) => ({
    label: name === '申请人提交' ? name : name === '审批完成' ? '审批完成' : short[name] || name,
    state:
      name === '申请人提交' || doneSet.has(name)
        ? 'done'
        : currentNode === name
          ? 'current'
          : 'pending'
  }))
})

const amountLabel = computed(() =>
  ['采购付款', '合同付款'].includes(selected.value?.doc_type) ? '付款金额' : selected.value?.doc_type === '借款单' ? '借款金额' : '报销金额'
)

const chips = ['同意报销', '材料不全，请补充', '金额有误，需更正']

function selectDoc(id) {
  selectedId.value = id
  opinion.value = ''
}

function chooseChip(text) {
  opinion.value = text
}

function handleAction(action) {
  if (!selected.value) return
  const doc = selected.value
  if (action === 'reject') {
    if (!window.confirm('确定驳回该单据吗？驳回后单据流程将终止（终态）。')) return
  }
  if (action === 'approve') {
    const openHigh = selectedRisks.value.some((item) => item.level === 'high' && item.status === 'open')
    if (openHigh && !window.confirm('存在未处理的高风险项，确认仍要通过吗？确认内容将写入审批意见。')) return
  }
  if (action === 'return' && !opinion.value.trim()) {
    opinion.value = '材料需补充，退回申请人修改后重新提交。'
  }
  if (action === 'reject' && !opinion.value.trim()) {
    pushToast('驳回必须填写意见', 'error')
    return
  }
  store.approveDocument(doc.id, action, opinion.value)
  opinion.value = ''
  const actionText = action === 'approve' ? '已通过' : action === 'return' ? '已退回' : '已驳回'
  pushToast(`${doc.doc_no} ${actionText}`)
}

function viewRiskDetail() {
  if (selected.value) router.push(`/documents/${selected.value.id}?tab=risk`)
}

function viewAttachments() {
  if (selected.value) router.push(`/documents/${selected.value.id}?tab=attachments`)
}
</script>

<template>
  <div class="approvals">
    <header class="page-header h59">
      <div class="title-row">
        <h1 class="header-title">待我审批</h1>
        <span class="badge badge-blue">{{ queue.length }}</span>
      </div>
      <div class="header-actions">
        <div class="filter-wrap">
          <select v-model="filterType" class="filter-select" aria-label="按单据类型筛选">
            <option>全部类型</option>
            <option v-for="type in DOC_TYPES" :key="type">{{ type }}</option>
          </select>
          <ChevronDown :size="13" class="filter-icon" />
        </div>
      </div>
    </header>

    <div class="approval-body">
      <section class="queue-card card">
        <h2 class="section-title">审批队列</h2>
        <button
          v-for="doc in queue"
          :key="doc.id"
          type="button"
          class="queue-item"
          :class="{ active: doc.id === selectedId }"
          @click="selectDoc(doc.id)"
        >
          <div class="queue-row1">
            <span class="queue-no">{{ doc.doc_no }}</span>
            <RiskBadge :level="doc.risk_level" />
          </div>
          <div class="queue-row2">
            <span class="queue-title">{{ doc.title }}</span>
            <span class="queue-applicant">{{ doc.applicant_name }}</span>
            <span class="queue-amount">{{ formatMoney(doc.total_amount) }}</span>
            <span class="queue-time">{{ doc.queue_time }}</span>
          </div>
        </button>
        <div v-if="!queue.length" class="empty-state">
          <Check :size="30" />
          <span>暂无待审批单据</span>
        </div>
      </section>

      <section v-if="selected" class="detail-card card">
        <div class="detail-head">
          <div class="detail-title">
            <div class="detail-name">{{ selected.doc_no }} · {{ selected.title }}</div>
            <div class="detail-sub">当前节点：{{ selected.current_node }} · 提交时间 {{ selected.submit_time }}</div>
          </div>
          <div class="progress">
            <div v-for="(step, index) in progress" :key="step.label" class="progress-step">
              <span class="p-dot" :class="step.state"></span>
              <span class="p-label" :class="{ current: step.state === 'current' }">{{ step.label }}</span>
              <ChevronRight v-if="index < progress.length - 1" :size="13" class="p-arrow" />
            </div>
          </div>
        </div>

        <div class="divider"></div>

        <div class="summary">
          <h3 class="summary-title">单据摘要</h3>
          <div class="sum-row">
            <div class="sum-cell">
              <span>单据类型</span>
              <strong>{{ selected.doc_type }}</strong>
            </div>
            <div class="sum-cell">
              <span>申请人</span>
              <strong>{{ selected.applicant_name }} · {{ selected.dept_name }}</strong>
            </div>
          </div>
          <div class="sum-row">
            <div class="sum-cell">
              <span>{{ amountLabel }}</span>
              <strong>{{ formatMoney(selected.total_amount, true) }}</strong>
            </div>
            <div class="sum-cell">
              <span>明细条数</span>
              <strong>{{ selectedDetails.length }} 条</strong>
            </div>
          </div>
          <div class="sum-row">
            <div class="sum-cell">
              <span>附件数量</span>
              <strong>{{ selectedAttachments.length }} 个（PDF/PNG/JPG）</strong>
            </div>
            <div class="sum-cell">
              <span>提交时间</span>
              <strong>{{ selected.submit_time }}</strong>
            </div>
          </div>
        </div>

        <div
          class="risk-box"
          :style="{
            background: selectedRiskInfo.bg,
            borderColor: selectedRiskInfo.line
          }"
        >
          <div class="risk-box-head">
            <ShieldAlert :size="16" :style="{ color: selectedRiskInfo.color }" />
            <span class="risk-box-title" :style="{ color: selectedRiskInfo.color }">
              风险提示（{{ selectedRisks.length }} 项 · 整体{{ selectedRiskInfo.text }}）
            </span>
            <span class="risk-spacer"></span>
            <button class="link link-sm" type="button" @click="viewRiskDetail">查看详情</button>
          </div>
          <div v-for="risk in selectedRisks.slice(0, 3)" :key="risk.id" class="risk-line">
            <span class="risk-dot" :style="{ background: riskInfo(risk.level).color }"></span>
            <strong class="risk-name">{{ risk.title }}</strong>
            <span class="risk-text">{{ risk.basis }}</span>
          </div>
          <div v-if="!selectedRisks.length" class="risk-line">
            <span class="risk-dot" style="background: #16a34a"></span>
            <span class="risk-text">未发现明显风险，可正常审批。</span>
          </div>
        </div>

        <div class="files-row">
          <Paperclip :size="15" />
          <span class="files-text">附件：{{ selectedAttachments.map((file) => file.file_name).join(' · ') || '无' }}</span>
          <button class="link link-sm" type="button" @click="viewAttachments">查看全部</button>
        </div>

        <div class="opinion">
          <h3 class="summary-title">审批意见</h3>
          <textarea
            v-model="opinion"
            class="textarea"
            placeholder="填写审批意见（可选）"
          ></textarea>
          <div class="chips">
            <button v-for="chip in chips" :key="chip" type="button" class="chip" @click="chooseChip(chip)">
              {{ chip }}
            </button>
          </div>
        </div>

        <div class="action-buttons">
          <button class="btn btn-lg btn-outline" type="button" @click="handleAction('return')">
            <RotateCcw :size="15" />
            <span>退回</span>
          </button>
          <button class="btn btn-lg btn-danger-soft" type="button" @click="handleAction('reject')">
            <X :size="15" />
            <span>驳回</span>
          </button>
          <button class="btn btn-lg btn-primary" type="button" @click="handleAction('approve')">
            <Check :size="15" />
            <span>通过</span>
          </button>
        </div>
      </section>

      <section v-else class="detail-card card empty-detail">
        <div class="empty-state">
          <Check :size="34" />
          <span>审批队列已清空</span>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.approvals {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  margin: 0;
  font-size: 18px;
  line-height: 22px;
}

.filter-wrap {
  position: relative;
  width: 94px;
  height: 31px;
}

.filter-select {
  width: 100%;
  height: 31px;
  padding: 8px 30px 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card);
  appearance: none;
  font-size: 12px;
  color: var(--text-secondary);
  outline: none;
  cursor: pointer;
}

.filter-select:focus {
  border-color: var(--primary);
}

.filter-icon {
  position: absolute;
  right: 10px;
  top: 9px;
  color: var(--text-secondary);
  pointer-events: none;
}

.approval-body {
  flex: 1;
  padding: 24px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.queue-card {
  width: 400px;
  flex: none;
  min-height: 793px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.queue-item {
  width: 100%;
  min-height: 70px;
  padding: 13px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 7px;
  text-align: left;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.queue-item:hover {
  border-color: #d0d5dd;
}

.queue-item.active {
  background: var(--primary-weak);
  border-color: var(--primary-line);
}

.queue-row1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 21px;
}

.queue-no {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.queue-row2 {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.queue-title {
  font-size: 13px;
  line-height: 16px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.queue-applicant {
  font-size: 12px;
  color: var(--text-secondary);
  flex: none;
}

.queue-amount {
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-left: auto;
  flex: none;
}

.queue-time {
  font-size: 11px;
  color: #98a2b3;
  flex: none;
}

.detail-card {
  flex: 1;
  min-width: 0;
  min-height: 793px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty-detail {
  align-items: center;
  justify-content: center;
}

.detail-head {
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.detail-title {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.detail-name {
  font-size: 15px;
  line-height: 18px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-sub {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.progress {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 6px;
}

.p-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #d0d5dd;
  flex: none;
}

.p-dot.done {
  background: var(--low);
}

.p-dot.current {
  background: var(--primary);
}

.p-label {
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  color: var(--text-secondary);
  white-space: nowrap;
}

.p-label.current {
  color: var(--primary);
}

.p-arrow {
  color: #98a2b3;
}

.divider {
  height: 1px;
  background: var(--border);
}

.summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-title {
  margin: 0;
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.sum-row {
  display: flex;
  gap: 20px;
}

.sum-cell {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  line-height: 15px;
}

.sum-cell span {
  color: var(--text-secondary);
  white-space: nowrap;
}

.sum-cell strong {
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.risk-box {
  border: 1px solid;
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.risk-box-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.risk-box-title {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
}

.risk-spacer {
  flex: 1;
}

.risk-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  line-height: 15px;
  min-width: 0;
}

.risk-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex: none;
}

.risk-name {
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  flex: none;
}

.risk-text {
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.files-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 15px;
  min-width: 0;
}

.files-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.files-row .link {
  flex: none;
}

.opinion {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.opinion .textarea {
  height: 84px;
  min-height: 84px;
  resize: none;
}

.chips {
  display: flex;
  gap: 8px;
}

.chip {
  height: 25px;
  padding: 5px 12px;
  border: none;
  border-radius: 6px;
  background: #f2f4f7;
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.chip:hover {
  background: #e9edf2;
  color: var(--text-primary);
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
