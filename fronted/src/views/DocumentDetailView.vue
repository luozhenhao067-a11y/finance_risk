<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Download,
  RotateCcw,
  ChevronDown,
  FileSearch,
  Lightbulb,
  Eye,
  FileText,
  Image as ImageIcon,
  X,
  CircleCheck,
  Clock,
  RefreshCw,
  LoaderCircle,
  CheckCircle2,
  XCircle,
  Bot,
  Send
} from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import RiskBadge from '../components/RiskBadge.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { formatMoney, riskInfo, riskCountText, statusInfo } from '../utils/format'
import { pushToast } from '../composables/useToast'
import { syncDetail } from '../api/realSync'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const {
  state,
  getFlowChain,
  canWithdraw,
  canResubmit,
  canApprove,
  canConfirmComplete,
  canRestore,
  canHandleRisk,
  canRerunAnalysis,
  canExportReport
} = store

const tabKeys = ['base', 'details', 'attachments', 'risk', 'flow', 'logs', 'qa']
const activeTab = ref(tabKeys.includes(route.query.tab) ? route.query.tab : 'risk')
const sortDesc = ref(true)
const selectedPage = ref(1)
const previewOpen = ref(false)

const qaMessages = ref([])
const qaInput = ref('')
const qaLoading = ref(false)
const qaSuggestions = [
  '这张单为什么被标记为高风险？',
  '主要触发了哪些规则？',
  '给出处理建议'
]

const doc = computed(() => state.documents.find((item) => item.id === route.params.id))
const details = computed(() => (doc.value ? store.getDetails(doc.value.id) : []))
const attachments = computed(() => (doc.value ? store.getAttachments(doc.value.id) : []))
const analysis = computed(() => (doc.value ? store.getRiskAnalysis(doc.value.id) : null))
const riskItems = computed(() => (doc.value ? store.getRiskItems(doc.value.id) : []))
const parseResults = computed(() => (doc.value ? store.getParseResults(doc.value.id) : []))
const logs = computed(() => (doc.value ? store.getLogs(doc.value.id) : []))
const opinions = computed(() => (doc.value ? store.getOpinions(doc.value.id) : []))
const tasks = computed(() => (doc.value ? store.getTasks(doc.value.id) : []))
const parseResult = computed(() => parseResults.value[0] || null)

const sortedRiskItems = computed(() => {
  const rank = { high: 3, mid: 2, low: 1 }
  const list = [...riskItems.value]
  list.sort((a, b) => (sortDesc.value ? rank[b.level] - rank[a.level] : rank[a.level] - rank[b.level]))
  return list
})

const riskBadgeInfo = computed(() => riskInfo(analysis.value?.overall_level || 'none'))

const tabs = computed(() => [
  { key: 'base', label: '基本信息' },
  { key: 'details', label: '费用明细' },
  { key: 'attachments', label: '附件与解析' },
  { key: 'risk', label: '风险分析' },
  { key: 'flow', label: '审批流转' },
  { key: 'logs', label: '审计日志' },
  { key: 'qa', label: '智能问答' }
])

const flowNodes = computed(() => {
  if (!doc.value) return []
  // 审批链（Spec 5.4：金额 ≥ ¥300,000 插入分管副总审批节点）
  const nodeOrder = getFlowChain(doc.value)
  const current = doc.value.current_node
  const completedNodes = new Set(
    tasks.value.filter((task) => task.status === 'done').map((task) => task.node)
  )
  if (['approved', 'completed'].includes(doc.value.status)) {
    nodeOrder.forEach((node) => completedNodes.add(node))
  }
  return nodeOrder.map((name) => {
    let status = 'pending'
    if (name === '申请人提交') status = 'done'
    else if (completedNodes.has(name) || ['approved', 'completed'].includes(doc.value.status)) status = 'done'
    else if (current === name) status = 'current'
    const opinion = [...opinions.value].reverse().find((row) => row.node === name)
    const task = tasks.value.find((row) => row.node === name)
    return {
      name,
      status,
      opinion,
      task,
      person:
        name === '申请人提交'
          ? doc.value.applicant_name
          : name === '审批完成'
            ? '系统'
            : task?.assignee || '待分配'
    }
  })
})

const fileIcon = (file) => (file.file_type === 'image' ? ImageIcon : FileText)

function switchTab(key) {
  activeTab.value = key
}

function goBack() {
  router.push('/documents')
}

async function exportReport() {
  if (!doc.value) return
  if (!canExportReport()) {
    pushToast('仅财务审核人与系统管理员可导出报告', 'error')
    return
  }
  if (doc.value.status === 'draft') {
    pushToast('草稿尚未提交审批，暂不能生成风险报告', 'info')
    return
  }
  const report = await store.ensureReport(doc.value.id)
  await syncDetail(doc.value.id)
  if (report) {
    pushToast(`报告 ${report.report_no} 已生成`)
    router.push(`/reports/${doc.value.id}`)
  }
}

async function withdraw() {
  if (!doc.value) return
  if (!window.confirm('确定撤回该单据吗？撤回后将进入已退回状态，可修改后重新提交。')) return
  await store.withdrawDocument(doc.value.id)
  await syncDetail(doc.value.id)
  pushToast('单据已撤回')
}

async function resubmit() {
  if (!doc.value) return
  await store.resubmitDocument(doc.value.id)
  await syncDetail(doc.value.id)
  pushToast('单据已重新提交，版本号 +1')
}

async function confirmDone() {
  if (!doc.value) return
  if (!window.confirm('确认单据完成归档吗？完成后单据进入终态。')) return
  await store.confirmComplete(doc.value.id)
  await syncDetail(doc.value.id)
  pushToast('单据已完成归档')
}

async function restoreDoc() {
  if (!doc.value) return
  const reason = window.prompt('请输入恢复原因（将写入审计日志）：')
  if (!reason || !reason.trim()) return
  await store.restoreDocument(doc.value.id, reason.trim())
  await syncDetail(doc.value.id)
  pushToast('单据已恢复为草稿')
}

async function rerunRisk() {
  if (!doc.value) return
  await store.rerunAnalysis(doc.value.id)
  await syncDetail(doc.value.id)
  pushToast('已触发重新分析')
}

async function approveCurrent() {
  if (!doc.value) return
  const openHigh = sortedRiskItems.value.some((item) => item.level === 'high' && item.status === 'open')
  if (openHigh && !window.confirm('存在未处理的高风险项，确认仍要通过吗？确认内容将写入审批意见。')) return
  await store.approveDocument(doc.value.id, 'approve', '同意，审批通过。')
  await syncDetail(doc.value.id)
  pushToast('已通过，流转下一节点')
}

async function returnCurrent() {
  if (!doc.value) return
  const opinion = window.prompt('退回意见（必填）：')
  if (!opinion || !opinion.trim()) {
    pushToast('退回必须填写意见', 'error')
    return
  }
  await store.approveDocument(doc.value.id, 'return', opinion.trim())
  await syncDetail(doc.value.id)
  pushToast('单据已退回申请人')
}

async function rejectCurrent() {
  if (!doc.value) return
  const opinion = window.prompt('驳回意见（必填）：')
  if (!opinion || !opinion.trim()) {
    pushToast('驳回必须填写意见', 'error')
    return
  }
  await store.approveDocument(doc.value.id, 'reject', opinion.trim())
  await syncDetail(doc.value.id)
  pushToast('单据已驳回')
}

async function handleRisk(item, status) {
  const label = status === 'handled' ? '处理' : '排除'
  const opinion = window.prompt(`${label}意见（必填）：`)
  if (!opinion || !opinion.trim()) {
    pushToast(`${label}意见必填`, 'error')
    return
  }
  await store.handleRiskItem(item.id, status, opinion.trim())
  await syncDetail(doc.value.id)
  pushToast(`风险项已${label}`)
}

function toggleSort() {
  sortDesc.value = !sortDesc.value
  pushToast(sortDesc.value ? '已按风险等级从高到低排序' : '已按风险等级从低到高排序', 'info')
}

async function askQuestion(text) {
  const question = (text ?? qaInput.value).trim()
  if (!question || qaLoading.value || !doc.value) return
  qaInput.value = ''
  qaMessages.value.push({ role: 'user', content: question })
  qaLoading.value = true
  try {
    const result = await store.askAi(doc.value.id, question)
    qaMessages.value.push({
      role: 'assistant',
      content: result?.answer || '未获取到回答，请稍后重试。',
      codes: result?.related_risk_codes || []
    })
  } catch (error) {
    qaMessages.value.push({
      role: 'assistant',
      content: `问答失败：${error?.message || '服务不可用'}`,
      codes: []
    })
  } finally {
    qaLoading.value = false
  }
}

function openPreview() {
  if (!attachments.value.length) {
    pushToast('暂无附件可预览', 'info')
    return
  }
  previewOpen.value = true
}

function parseFieldWidth(confidence) {
  return `${Math.round((confidence / 100) * 44)}px`
}

function statusLabel() {
  return statusInfo(doc.value?.status).text
}

watch(
  () => route.query.tab,
  (tab) => {
    if (tabKeys.includes(tab)) activeTab.value = tab
  }
)

onMounted(() => {
  syncDetail(route.params.id)
})
</script>

<template>
  <div v-if="doc" class="document-detail">
    <header class="page-header">
      <div class="head-left">
        <button class="back-btn" type="button" aria-label="返回单据列表" @click="goBack">
          <ArrowLeft :size="18" />
        </button>
        <div class="title-box">
          <div class="title-row">
            <span class="doc-no">{{ doc.doc_no }}</span>
            <StatusBadge :status="doc.status" />
          </div>
          <div class="doc-subtitle">{{ doc.title }} · {{ doc.applicant_name }} · {{ doc.dept_name }}</div>
        </div>
      </div>
      <div class="header-actions">
        <button
          v-if="canExportReport()"
          class="btn btn-outline"
          type="button"
          @click="exportReport"
        >
          <Download :size="15" />
          <span>导出报告</span>
        </button>
        <button
          v-if="canConfirmComplete(doc)"
          class="btn btn-primary"
          type="button"
          @click="confirmDone"
        >
          <CircleCheck :size="14" />
          <span>确认完成</span>
        </button>
        <button
          v-if="canWithdraw(doc)"
          class="btn btn-danger-soft"
          type="button"
          @click="withdraw"
        >
          <RotateCcw :size="14" />
          <span>撤回单据</span>
        </button>
        <button
          v-else-if="canResubmit(doc)"
          class="btn btn-primary"
          type="button"
          @click="resubmit"
        >
          <RefreshCw :size="14" />
          <span>重新提交</span>
        </button>
        <button
          v-else-if="canRestore(doc)"
          class="btn btn-outline"
          type="button"
          @click="restoreDoc"
        >
          <RefreshCw :size="14" />
          <span>恢复为草稿</span>
        </button>
      </div>
    </header>

    <nav class="tabbar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span>{{ tab.label }}</span>
        <i></i>
      </button>
    </nav>

    <div class="page-body detail-body">
      <div v-if="doc.status === 'submitted' || doc.status === 'analyzing'" class="analyzing-banner">
        <LoaderCircle :size="16" class="spin" />
        <span v-if="doc.status === 'submitted'">单据已提交，正在创建快照与解析任务…</span>
        <span v-else>智能风险分析中：附件解析完成，规则引擎执行中…</span>
      </div>

      <template v-if="activeTab === 'risk'">
        <section class="risk-summary card">
          <div
            class="summary-icon"
            :style="{ background: riskBadgeInfo.bg, color: riskBadgeInfo.color }"
          >
            <FileSearch :size="26" />
          </div>
          <div class="summary-left">
            <div class="summary-label">整体风险等级</div>
            <div class="summary-value-row">
              <span class="summary-value" :style="{ color: riskBadgeInfo.color }">
                {{ riskBadgeInfo.text }}
              </span>
              <span class="summary-desc">{{ analysis ? riskCountText(analysis) : '暂无风险分析结果' }}</span>
            </div>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-stat">
            <span class="stat-value" style="color: #dc2626">{{ analysis?.high_count || 0 }}</span>
            <span class="stat-label">高风险</span>
          </div>
          <div class="summary-stat">
            <span class="stat-value" style="color: #f59e0b">{{ analysis?.mid_count || 0 }}</span>
            <span class="stat-label">中风险</span>
          </div>
          <div class="summary-stat">
            <span class="stat-value" style="color: #16a34a">{{ analysis?.low_count || 0 }}</span>
            <span class="stat-label">低风险</span>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-advice">
            <span class="advice-pill" :style="{ background: '#F59E0B1F', color: '#F59E0B' }">
              建议：{{ analysis?.recommendation_label || '人工复核' }}
            </span>
            <span class="advice-text">{{ analysis?.summary || '暂无风险分析结论' }}</span>
          </div>
          <button
            v-if="canRerunAnalysis() && !['submitted', 'analyzing'].includes(doc.status)"
            class="btn btn-outline rerun-btn"
            type="button"
            @click="rerunRisk"
          >
            <RefreshCw :size="14" />
            <span>重新分析</span>
          </button>
        </section>

        <div class="risk-content">
          <section class="risk-list-card card">
            <div class="list-head">
              <span class="section-title">风险项（{{ riskItems.length }}）</span>
              <button class="sort-btn" type="button" @click="toggleSort">
                <span>按等级排序</span>
                <ChevronDown :size="13" />
              </button>
            </div>

            <div
              v-for="item in sortedRiskItems"
              :key="item.id"
              class="risk-item"
              :style="{
                background: riskInfo(item.level).bg,
                borderColor: riskInfo(item.level).color
              }"
            >
              <div class="risk-item-row1">
                <RiskBadge :level="item.level" white />
                <span class="risk-rule">{{ item.rule_code }}</span>
                <span class="risk-title">{{ item.title }}</span>
                <span
                  class="badge"
                  :class="item.status === 'handled' ? 'badge-green' : item.status === 'dismissed' ? 'badge-gray' : 'badge-amber'"
                >{{ { open: '待处理', handled: '已处理', dismissed: '已排除' }[item.status] || '待处理' }}</span>
                <span class="risk-basis">依据：{{ item.basis }}</span>
              </div>
              <div class="risk-evidence">
                <FileSearch :size="14" />
                <span>证据：{{ item.evidence }}</span>
              </div>
              <div class="risk-suggestion">
                <Lightbulb :size="14" />
                <span>建议：{{ item.suggestion }}</span>
              </div>
              <div v-if="item.status !== 'open' && item.handle_opinion" class="risk-handled">
                <span>{{ item.handled_by }} · {{ item.handled_at }}：{{ item.handle_opinion }}</span>
              </div>
              <div v-if="canHandleRisk() && item.status === 'open'" class="risk-actions">
                <button class="btn btn-soft btn-xs" type="button" @click="handleRisk(item, 'handled')">
                  <CheckCircle2 :size="13" />
                  <span>标记已处理</span>
                </button>
                <button class="btn btn-soft btn-xs" type="button" @click="handleRisk(item, 'dismissed')">
                  <XCircle :size="13" />
                  <span>排除风险</span>
                </button>
              </div>
            </div>

            <div v-if="!sortedRiskItems.length" class="empty-state">
              <CircleCheck :size="30" />
              <span>未发现风险项</span>
            </div>
          </section>

          <aside class="risk-right">
            <section class="parse-card card">
              <h2 class="panel-title">附件解析结果</h2>
              <template v-if="parseResult">
                <div class="file-chip">
                  <FileText :size="15" style="color: #dc2626" />
                  <span class="file-chip-name">{{ parseResult.file_name }} · 第 {{ parseResult.page }} 页</span>
                  <span class="file-chip-conf">置信度 {{ parseResult.confidence }}%</span>
                </div>
                <div v-for="field in parseResult.fields" :key="field.label" class="parse-field">
                  <span class="parse-label">{{ field.label }}</span>
                  <span class="parse-value">{{ field.value }}</span>
                  <span class="conf-bar">
                    <i
                      :style="{
                        width: parseFieldWidth(field.confidence),
                        background: field.confidence >= 90 ? '#16A34A' : '#F59E0B'
                      }"
                    ></i>
                  </span>
                </div>
              </template>
              <div v-else class="empty-inline">暂无附件解析结果</div>
            </section>

            <section class="view-card card">
              <h2 class="panel-title">证据定位</h2>
              <div class="thumbs">
                <button
                  v-for="page in 3"
                  :key="page"
                  type="button"
                  class="thumb"
                  :class="{ active: selectedPage === page }"
                  @click="selectedPage = page"
                >
                  第 {{ page }} 页
                </button>
              </div>
              <button class="btn btn-soft view-btn" type="button" @click="openPreview">
                <Eye :size="15" />
                <span>查看原始附件</span>
              </button>
            </section>
          </aside>
        </div>
      </template>

      <template v-else-if="activeTab === 'base'">
        <section class="info-card card">
          <h2 class="section-title">单据信息</h2>
          <div class="info-grid">
            <div class="info-item"><span>单据编号</span><strong>{{ doc.doc_no }}</strong></div>
            <div class="info-item"><span>单据类型</span><strong>{{ doc.doc_type }}</strong></div>
            <div class="info-item"><span>单据标题</span><strong>{{ doc.title }}</strong></div>
            <div class="info-item"><span>申请人</span><strong>{{ doc.applicant_name }}</strong></div>
            <div class="info-item"><span>申请部门</span><strong>{{ doc.dept_name }}</strong></div>
            <div class="info-item"><span>费用项目</span><strong>{{ doc.project }}</strong></div>
            <div class="info-item"><span>合计金额</span><strong class="money">{{ formatMoney(doc.total_amount) }}</strong></div>
            <div class="info-item"><span>当前状态</span><span><StatusBadge :status="doc.status" /></span></div>
            <div class="info-item"><span>当前审批节点</span><strong>{{ doc.current_node || '—' }}</strong></div>
            <div class="info-item"><span>版本号</span><strong>v{{ doc.version }}</strong></div>
            <div class="info-item"><span>创建时间</span><strong>{{ doc.create_time }}</strong></div>
            <div class="info-item"><span>提交时间</span><strong>{{ doc.submit_time || '—' }}</strong></div>
          </div>
          <div class="info-footer">
            <div class="snapshot-note">
              <Clock :size="15" />
              <span>审批与风险分析均基于提交时快照，历史版本不可修改。</span>
            </div>
            <span class="muted-sm">快照版本 v{{ doc.version }}</span>
          </div>
        </section>
      </template>

      <template v-else-if="activeTab === 'details'">
        <section class="detail-card card">
          <div class="card-head">
            <h2 class="section-title">费用明细</h2>
            <span class="muted-sm">共 {{ details.length }} 条 · 合计 {{ formatMoney(doc.total_amount) }}</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>费用类型</th>
                <th>费用日期</th>
                <th>金额</th>
                <th>发票号</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in details" :key="row.id">
                <td class="strong">{{ row.expense_type }}</td>
                <td>{{ row.expense_date }}</td>
                <td class="money">{{ formatMoney(row.amount) }}</td>
                <td>{{ row.invoice_no }}</td>
                <td>{{ row.remark }}</td>
              </tr>
            </tbody>
          </table>
          <div class="detail-total">
            <span>合计金额</span>
            <strong>{{ formatMoney(doc.total_amount, true) }}</strong>
          </div>
        </section>
      </template>

      <template v-else-if="activeTab === 'attachments'">
        <div class="attachment-layout">
          <section class="attachment-card card">
            <div class="card-head">
              <h2 class="section-title">附件（{{ attachments.length }}）</h2>
              <span class="muted-sm">PDF / PNG / JPG · 单文件 ≤ 10MB</span>
            </div>
            <div class="attachment-list">
              <div v-for="file in attachments" :key="file.id" class="attachment-item">
                <div class="attachment-icon" :style="{ color: file.file_type === 'image' ? '#2563EB' : '#DC2626' }">
                  <component :is="fileIcon(file)" :size="20" />
                </div>
                <div class="attachment-meta">
                  <div class="attachment-name">{{ file.file_name }}</div>
                  <div class="attachment-sub">{{ file.size_label }} · {{ file.mime }} · {{ file.uploaded_at }}</div>
                </div>
                <span class="badge badge-green">解析完成</span>
                <button class="link link-sm" type="button" @click="openPreview">查看</button>
              </div>
              <div v-if="!attachments.length" class="empty-state">暂无附件</div>
            </div>
          </section>

          <section class="attachment-parse card">
            <h2 class="section-title">解析字段</h2>
            <template v-if="parseResult">
              <div class="parse-meta">
                <span>{{ parseResult.file_name }}</span>
                <span class="badge badge-green">置信度 {{ parseResult.confidence }}%</span>
              </div>
              <div v-for="field in parseResult.fields" :key="field.label" class="parse-line">
                <span>{{ field.label }}</span>
                <strong>{{ field.value }}</strong>
                <span class="parse-mini-bar"><i :style="{ width: `${field.confidence}%` }"></i></span>
              </div>
            </template>
            <div v-else class="empty-state">暂无解析数据</div>
          </section>
        </div>
      </template>

      <template v-else-if="activeTab === 'flow'">
        <section class="flow-detail-card card">
          <div class="card-head">
            <h2 class="section-title">审批流转</h2>
            <span class="badge" :class="statusInfo(doc.status).className">{{ statusLabel() }}</span>
          </div>
          <div class="timeline">
            <div v-for="(node, index) in flowNodes" :key="node.name" class="timeline-item">
              <div class="timeline-rail">
                <span
                  class="timeline-dot"
                  :class="{
                    done: node.status === 'done',
                    current: node.status === 'current'
                  }"
                ></span>
                <span v-if="index < flowNodes.length - 1" class="timeline-line"></span>
              </div>
              <div class="timeline-body">
                <div class="timeline-head">
                  <span class="timeline-name" :class="{ current: node.status === 'current' }">{{ node.name }}</span>
                  <span v-if="node.status === 'current'" class="badge badge-blue">当前节点</span>
                  <span v-else-if="node.status === 'done'" class="badge badge-green">已完成</span>
                </div>
                <div class="timeline-meta">
                  <span>{{ node.person }}</span>
                  <span v-if="node.opinion">· {{ node.opinion.created_at }}</span>
                </div>
                <p v-if="node.opinion" class="timeline-opinion">{{ node.opinion.opinion }}</p>
              </div>
            </div>
          </div>

          <div v-if="canApprove(doc)" class="approve-panel">
            <div class="approve-panel-title">
              审批操作 · 当前节点：{{ doc.current_node }}
              <span class="muted-sm">通过 / 退回 / 驳回（退回与驳回意见必填）</span>
            </div>
            <div class="approve-panel-actions">
              <button class="btn btn-primary" type="button" @click="approveCurrent">通过</button>
              <button class="btn btn-outline" type="button" @click="returnCurrent">退回</button>
              <button class="btn btn-danger-soft" type="button" @click="rejectCurrent">驳回</button>
            </div>
          </div>
        </section>
      </template>

      <template v-else-if="activeTab === 'logs'">
        <section class="logs-card card">
          <div class="card-head">
            <h2 class="section-title">审计日志</h2>
            <span class="muted-sm">共 {{ logs.length }} 条记录</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>操作时间</th>
                <th>操作类型</th>
                <th>操作人</th>
                <th>角色</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs" :key="log.id">
                <td class="muted">{{ log.created_at }}</td>
                <td class="strong">{{ log.action }}</td>
                <td>{{ log.operator }}</td>
                <td>{{ log.role }}</td>
                <td>{{ log.detail }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!logs.length" class="empty-state">暂无操作记录</div>
        </section>
      </template>

      <template v-else-if="activeTab === 'qa'">
        <section class="qa-card card">
          <div class="qa-head">
            <Bot :size="18" style="color: var(--primary)" />
            <h2 class="section-title">智能问答</h2>
            <span class="muted-sm">AI 结合单据信息与风险分析结果作答，引用规则编号</span>
          </div>
          <div class="qa-messages">
            <div v-if="!qaMessages.length && !qaLoading" class="qa-empty">
              针对本单据提问，AI 将结合风险项、解析结果与处理建议作答。
            </div>
            <div v-for="(msg, index) in qaMessages" :key="index" class="qa-msg" :class="msg.role">
              <div class="qa-bubble">{{ msg.content }}</div>
              <div v-if="msg.codes && msg.codes.length" class="qa-codes">
                <span v-for="code in msg.codes" :key="code" class="risk-rule">{{ code }}</span>
              </div>
            </div>
            <div v-if="qaLoading" class="qa-msg assistant">
              <div class="qa-bubble typing">
                <LoaderCircle :size="14" class="spin" />
                <span>思考中…</span>
              </div>
            </div>
          </div>
          <div class="qa-suggestions">
            <button
              v-for="item in qaSuggestions"
              :key="item"
              type="button"
              class="qa-chip"
              @click="askQuestion(item)"
            >
              {{ item }}
            </button>
          </div>
          <form class="qa-input-row" @submit.prevent="askQuestion()">
            <input
              v-model="qaInput"
              type="text"
              placeholder="输入问题，例如：为什么标记为高风险？"
              maxlength="500"
            />
            <button
              class="qa-send"
              type="submit"
              :disabled="!qaInput.trim() || qaLoading"
              aria-label="发送问题"
            >
              <Send :size="15" />
            </button>
          </form>
        </section>
      </template>
    </div>

    <transition name="fade">
      <div v-if="previewOpen" class="modal-mask" @click.self="previewOpen = false">
        <div class="preview-modal">
          <div class="preview-head">
            <span>附件预览 · 第 {{ selectedPage }} 页</span>
            <button class="icon-btn" type="button" aria-label="关闭" @click="previewOpen = false">
              <X :size="18" />
            </button>
          </div>
          <div class="preview-body">
            <div class="preview-placeholder">
              <FileText :size="40" />
              <span>{{ attachments[0]?.file_name || '未上传附件' }}</span>
              <span class="muted-sm">演示环境仅保存附件元数据，原始文件路径已记录。</span>
            </div>
            <div class="preview-meta">
              <div><span>文件路径</span><strong>{{ attachments[0]?.path || '—' }}</strong></div>
              <div><span>上传时间</span><strong>{{ attachments[0]?.uploaded_at || '—' }}</strong></div>
              <div><span>解析状态</span><strong>已完成</strong></div>
              <div v-if="parseResult"><span>识别置信度</span><strong>{{ parseResult.confidence }}%</strong></div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>

  <div v-else class="missing-state">
    <div class="card">
      <h2>单据不存在</h2>
      <p class="muted">该单据可能已被删除，请返回单据列表。</p>
      <button class="btn btn-primary" type="button" @click="router.push('/documents')">返回单据管理</button>
    </div>
  </div>
</template>

<style scoped>
.document-detail {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: 6px;
  color: var(--text-secondary);
  padding: 0;
}

.back-btn:hover {
  background: var(--bg);
}

.title-box {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-no {
  font-size: 16px;
  line-height: 19px;
  font-weight: 700;
}

.doc-subtitle {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-body {
  gap: 16px;
}

.analyzing-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #eff6ff;
  border: 1px solid var(--primary-line);
  border-radius: 8px;
  color: var(--primary);
  font-size: 13px;
  flex: none;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.rerun-btn {
  flex: none;
  height: 32px;
}

.risk-rule {
  padding: 2px 7px;
  border-radius: 4px;
  background: #fff;
  border: 1px solid var(--border);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  flex: none;
}

.risk-handled {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  padding-left: 2px;
}

.risk-actions {
  display: flex;
  gap: 8px;
  padding-left: 2px;
}

.btn-xs {
  height: 26px;
  padding: 4px 10px;
  font-size: 12px;
  gap: 5px;
}

.approve-panel {
  margin-top: 8px;
  padding: 14px 16px;
  background: #f9fafb;
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.approve-panel-title {
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.approve-panel-actions {
  display: flex;
  gap: 10px;
}

.risk-summary {
  min-height: 88px;
  padding: 18px 22px;
  display: flex;
  align-items: center;
  gap: 22px;
  flex-wrap: nowrap;
  overflow: hidden;
}

.summary-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.summary-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: none;
}

.summary-label {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.summary-value-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-value {
  font-size: 24px;
  line-height: 29px;
  font-weight: 700;
}

.summary-desc {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.summary-divider {
  width: 1px;
  height: 40px;
  background: var(--border);
  flex: none;
}

.summary-stat {
  width: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex: none;
}

.stat-value {
  font-size: 22px;
  line-height: 27px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.summary-advice {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.advice-pill {
  height: 30px;
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  flex: none;
}

.advice-text {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.risk-content {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.risk-list-card {
  flex: 1;
  min-width: 0;
  min-height: 635px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sort-btn {
  height: 29px;
  padding: 7px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-secondary);
  font-size: 12px;
}

.sort-btn:hover {
  border-color: #d0d5dd;
}

.risk-item {
  min-height: 95px;
  padding: 14px 16px;
  border: 1px solid;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.risk-item-row1 {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  height: 21px;
}

.risk-title {
  font-size: 14px;
  line-height: 17px;
  font-weight: 700;
  color: var(--text-primary);
  flex: none;
}

.risk-basis {
  font-size: 13px;
  line-height: 16px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.risk-evidence,
.risk-suggestion {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  line-height: 15px;
  padding-left: 2px;
}

.risk-evidence {
  color: var(--text-secondary);
}

.risk-suggestion {
  color: var(--mid);
}

.risk-evidence svg {
  color: var(--text-secondary);
  flex: none;
}

.risk-suggestion svg {
  color: var(--mid);
  flex: none;
}

.risk-right {
  width: 340px;
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.parse-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-title {
  margin: 0;
  font-size: 14px;
  line-height: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.file-chip {
  height: 31px;
  padding: 8px 12px;
  background: var(--bg);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-chip-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.file-chip-conf {
  margin-left: auto;
  font-size: 12px;
  font-weight: 700;
  color: var(--low);
  white-space: nowrap;
}

.parse-field {
  height: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.parse-label {
  width: 76px;
  flex: none;
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.parse-value {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conf-bar {
  width: 44px;
  height: 5px;
  background: #f2f4f7;
  border-radius: 3px;
  overflow: hidden;
  flex: none;
}

.conf-bar i {
  display: block;
  height: 5px;
  border-radius: 3px;
}

.empty-inline {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 12px 0;
}

.view-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.thumbs {
  display: flex;
  gap: 10px;
}

.thumb {
  flex: 1;
  height: 64px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #f9fafb;
  color: var(--text-secondary);
  font-size: 12px;
}

.thumb.active {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-weak);
}

.view-btn {
  width: 100%;
  height: 36px;
  padding: 10px 0;
}

.info-card {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 40px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 18px;
  font-size: 13px;
}

.info-item > span:first-child {
  width: 104px;
  flex: none;
  color: var(--text-secondary);
}

.info-item strong {
  font-weight: 700;
}

.info-item .money {
  color: var(--text-primary);
}

.info-footer {
  padding-top: 16px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.snapshot-note {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.detail-card,
.logs-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.qa-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.qa-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.qa-head .section-title {
  flex: none;
}

.qa-messages {
  min-height: 340px;
  max-height: 460px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 2px;
}

.qa-empty {
  margin: auto;
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  max-width: 420px;
  line-height: 22px;
}

.qa-msg {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 78%;
}

.qa-msg.user {
  align-self: flex-end;
  align-items: flex-end;
}

.qa-msg.assistant {
  align-self: flex-start;
  align-items: flex-start;
}

.qa-bubble {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 20px;
  white-space: pre-wrap;
  word-break: break-word;
}

.qa-msg.user .qa-bubble {
  background: var(--primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.qa-msg.assistant .qa-bubble {
  background: var(--bg);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.qa-bubble.typing {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--text-secondary);
}

.qa-codes {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.qa-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-chip {
  height: 26px;
  padding: 4px 12px;
  border: 1px solid var(--primary-line);
  border-radius: 13px;
  background: var(--primary-weak);
  color: var(--primary);
  font-size: 12px;
}

.qa-chip:hover {
  background: #dbeafe;
}

.qa-input-row {
  display: flex;
  gap: 10px;
}

.qa-input-row input {
  flex: 1;
  min-width: 0;
  height: 36px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  color: var(--text-primary);
}

.qa-input-row input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.qa-send {
  width: 36px;
  height: 36px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
}

.qa-send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.detail-total {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.detail-total strong {
  font-size: 18px;
  color: var(--high);
}

.attachment-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.attachment-card {
  flex: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.attachment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
}

.attachment-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.attachment-meta {
  flex: 1;
  min-width: 0;
}

.attachment-name {
  font-size: 13px;
  font-weight: 700;
}

.attachment-sub {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.attachment-parse {
  width: 360px;
  flex: none;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.parse-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  font-weight: 700;
}

.parse-line {
  display: grid;
  grid-template-columns: 90px 1fr 80px;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.parse-line strong {
  color: var(--text-primary);
  font-size: 12px;
}

.parse-mini-bar {
  height: 5px;
  background: #f2f4f7;
  border-radius: 3px;
  overflow: hidden;
}

.parse-mini-bar i {
  display: block;
  height: 5px;
  background: var(--low);
}

.flow-detail-card {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.timeline {
  display: flex;
  flex-direction: column;
}

.timeline-item {
  display: flex;
  gap: 14px;
  min-height: 84px;
}

.timeline-rail {
  width: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: none;
}

.timeline-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid #d0d5dd;
  background: #fff;
  flex: none;
  margin-top: 2px;
}

.timeline-dot.done {
  background: var(--low);
  border-color: var(--low);
}

.timeline-dot.current {
  background: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.timeline-line {
  width: 2px;
  flex: 1;
  background: var(--border);
}

.timeline-body {
  flex: 1;
  padding-bottom: 20px;
}

.timeline-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.timeline-name {
  font-size: 13px;
  font-weight: 700;
}

.timeline-name.current {
  color: var(--primary);
}

.timeline-meta {
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  gap: 4px;
}

.timeline-opinion {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #f9fafb;
  border-radius: 8px;
  font-size: 12px;
  line-height: 18px;
  color: var(--text-secondary);
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 24, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.preview-modal {
  width: 640px;
  max-width: calc(100vw - 48px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 24px 60px rgba(16, 24, 40, 0.24);
  overflow: hidden;
}

.preview-head {
  height: 52px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  font-weight: 700;
}

.preview-body {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.preview-placeholder {
  height: 260px;
  border: 1px dashed var(--border);
  border-radius: 10px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.preview-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}

.preview-meta div {
  display: flex;
  gap: 12px;
}

.preview-meta span {
  width: 90px;
  color: var(--text-secondary);
}

.preview-meta strong {
  font-weight: 500;
  color: var(--text-primary);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.missing-state {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.missing-state .card {
  padding: 40px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
</style>
