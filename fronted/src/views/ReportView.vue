<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { History, FileSpreadsheet, Download } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { formatMoney, riskInfo } from '../utils/format'
import { pushToast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const docId = route.params.docId
const doc = computed(() => store.getDocument(docId))

if (doc.value && !store.getReportByDoc(docId)) {
  store.ensureReport(docId)
}

const report = computed(() => store.getReportByDoc(docId))
const analysis = computed(() => store.getRiskAnalysis(docId))
const riskItems = computed(() => store.getRiskItems(docId))
const evidences = computed(() => store.getRiskEvidences(docId))
const canExport = computed(() => store.canExportReport())
const overall = computed(() => riskInfo(report.value?.overall_level || analysis.value?.overall_level || 'none'))
const reportRiskItems = computed(() => {
  const rank = { high: 3, mid: 2, low: 1 }
  return [...riskItems.value].sort((a, b) => rank[b.level] - rank[a.level])
})

const reviewer = computed(() => report.value?.reviews?.[0] || null)

function attachmentName(evidence) {
  const attachment = store.getAttachments(docId).find((row) => row.id === evidence.attachment_id)
  return attachment?.file_name || '附件'
}

function recommendationText() {
  const label = report.value?.recommendation_label || '人工复核'
  const summary = report.value?.summary || ''
  const suffix = /[。！？]$/.test(summary) ? '' : '。'
  return `处理建议：${label}。${summary}${suffix}`
}

function goHistory() {
  router.push('/reports')
}

function exportExcel() {
  if (!report.value) return
  const lines = []
  lines.push(['财务单据风险审核报告'])
  lines.push(['报告编号', report.value.report_no])
  lines.push(['生成时间', report.value.generated_at])
  lines.push([])
  lines.push(['一、单据摘要'])
  lines.push(['单据编号', doc.value?.doc_no])
  lines.push(['单据类型', doc.value?.doc_type])
  lines.push(['申请人', `${doc.value?.applicant_name} · ${doc.value?.dept_name}`])
  lines.push(['费用项目', doc.value?.project])
  lines.push(['单据金额', formatMoney(doc.value?.total_amount)])
  lines.push(['附件数量', `${store.getAttachments(docId).length} 个`])
  lines.push([])
  lines.push(['二、整体风险结论'])
  lines.push([report.value.overall_text])
  lines.push([recommendationText()])
  lines.push([])
  lines.push(['三、金额核对'])
  lines.push(['核对项目', '单据金额', '解析金额', '差异', '结论'])
  report.value.amount_checks.forEach((row) => {
    lines.push([row.name, formatMoney(row.doc_amount), formatMoney(row.parsed_amount), formatMoney(row.diff), row.conclusion])
  })
  lines.push([])
  lines.push(['四、风险项明细'])
  reportRiskItems.value.forEach((item, index) => {
    lines.push([`${index + 1}. ${item.title}`, riskInfo(item.level).text, item.basis, item.suggestion])
  })
  lines.push([])
  lines.push(['五、供应商风险'])
  if (report.value.vendor) {
    lines.push([report.value.vendor.name, `风险评分 ${report.value.vendor.score} / 100`, report.value.vendor.note])
  } else {
    lines.push(['未发现供应商风险'])
  }
  lines.push([])
  lines.push(['六、证据列表'])
  if (evidences.value.length) {
    evidences.value.forEach((ev) => {
      lines.push([`${attachmentName(ev)} · 第 ${ev.page} 页`, ev.snippet, `置信度 ${ev.confidence}%`])
    })
  } else {
    lines.push(['暂无证据记录'])
  }
  lines.push([])
  lines.push(['七、人工复核记录'])
  if (reviewer.value) {
    lines.push([`${reviewer.value.name}（${reviewer.value.role}）`, reviewer.value.content, reviewer.value.created_at])
  } else {
    lines.push(['暂无人工复核记录'])
  }
  const csv = lines
    .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\r\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${report.value.report_no}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  pushToast('Excel 已导出')
}

function downloadPdf() {
  pushToast('已打开打印窗口，请选择“另存为 PDF”', 'info')
  window.setTimeout(() => window.print(), 200)
}
</script>

<template>
  <div v-if="doc && report" class="report-page">
    <header class="page-header h62 no-print">
      <div class="title-row">
        <h1 class="header-title">风险审核报告</h1>
        <span class="badge badge-gray">{{ report.report_no }}</span>
      </div>
      <div class="header-actions">
        <button class="btn btn-outline" type="button" @click="goHistory">
          <History :size="15" />
          <span>历史报告</span>
        </button>
        <template v-if="canExport">
          <button class="btn btn-outline" type="button" @click="exportExcel">
            <FileSpreadsheet :size="15" />
            <span>导出 Excel</span>
          </button>
          <button class="btn btn-primary" type="button" @click="downloadPdf">
            <Download :size="15" />
            <span>下载 PDF</span>
          </button>
        </template>
      </div>
    </header>

    <div class="report-body">
      <article class="report-paper">
        <div class="doc-head">
          <div class="doc-title">
            <h2>财务单据风险审核报告</h2>
            <p>报告编号 {{ report.report_no }} · 生成时间 {{ report.generated_at }}</p>
          </div>
          <span class="badge" :class="overall.className">整体{{ overall.text }}</span>
        </div>

        <div class="doc-divider"></div>

        <h3 class="section-heading">一、单据摘要</h3>
        <div class="info-block">
          <div class="info-row">
            <div class="info-cell"><span>单据编号</span><strong>{{ doc.doc_no }}</strong></div>
            <div class="info-cell"><span>单据类型</span><strong>{{ doc.doc_type }}</strong></div>
          </div>
          <div class="info-row">
            <div class="info-cell"><span>申请人</span><strong>{{ doc.applicant_name }} · {{ doc.dept_name }}</strong></div>
            <div class="info-cell"><span>费用项目</span><strong>{{ doc.project }}</strong></div>
          </div>
          <div class="info-row">
            <div class="info-cell"><span>报销金额</span><strong>{{ formatMoney(doc.total_amount, true) }}</strong></div>
            <div class="info-cell"><span>附件数量</span><strong>{{ store.getAttachments(docId).length }} 个</strong></div>
          </div>
        </div>

        <h3 class="section-heading">二、整体风险结论</h3>
        <div class="conclusion" :style="{ background: overall.bg, borderColor: overall.line }">
          <div class="conclusion-icon" :style="{ background: overall.bg, color: overall.color }">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shield-icon">
              <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
              <path d="M12 8v4" />
              <path d="M12 16h.01" />
            </svg>
          </div>
          <div class="conclusion-text">
            <div class="conclusion-title" :style="{ color: overall.color }">{{ report.overall_text }}</div>
            <p>{{ recommendationText() }}</p>
          </div>
        </div>

        <h3 class="section-heading">三、金额核对</h3>
        <div class="amt-table-wrap">
          <table class="amt-table">
            <thead>
              <tr>
                <th style="width: 120px">核对项目</th>
                <th style="width: 170px">单据金额</th>
                <th style="width: 170px">解析金额</th>
                <th style="width: 140px">差异</th>
                <th style="width: 92px">结论</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in report.amount_checks" :key="row.name">
                <td :class="{ strong: row.is_total }">{{ row.name }}</td>
                <td>{{ formatMoney(row.doc_amount) }}</td>
                <td>{{ formatMoney(row.parsed_amount) }}</td>
                <td
                  class="strong"
                  :style="{ color: row.diff ? '#DC2626' : '#111827' }"
                >{{ formatMoney(row.diff) }}</td>
                <td
                  class="strong"
                  :style="{ color: row.conclusion === '一致' ? '#16A34A' : '#DC2626' }"
                >{{ row.conclusion }}</td>
              </tr>
              <tr v-if="!report.amount_checks.length">
                <td colspan="5" class="empty-cell">暂无金额核对数据</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3 class="section-heading">四、风险项明细</h3>
        <div class="risk-items">
          <div v-for="(item, index) in reportRiskItems" :key="item.id" class="risk-report-item">
            <span class="risk-num">{{ index + 1 }}.</span>
            <span class="badge" :class="riskInfo(item.level).className">{{ riskInfo(item.level).text }}</span>
            <div class="risk-report-text">
              <div class="risk-report-title">{{ item.title }}</div>
              <div class="risk-report-basis">{{ item.basis }}</div>
              <div class="risk-report-suggestion">建议：{{ item.suggestion }}</div>
            </div>
          </div>
          <div v-if="!reportRiskItems.length" class="risk-empty">未发现风险项</div>
        </div>

        <h3 class="section-heading">五、供应商风险</h3>
        <div
          v-if="report.vendor"
          class="vendor-box"
          :style="{
            background: riskInfo(report.vendor.level).bg,
            borderColor: riskInfo(report.vendor.level).line
          }"
        >
          <span class="vendor-name">{{ report.vendor.name }}</span>
          <span class="vendor-score" :style="{ color: riskInfo(report.vendor.level).color }">
            风险评分 {{ report.vendor.score }} / 100 · {{ riskInfo(report.vendor.level).text }}
          </span>
          <span class="vendor-note">{{ report.vendor.note }}</span>
        </div>
        <div v-else class="vendor-box vendor-empty">
          <span class="vendor-note">未发现供应商风险，暂无关联供应商数据。</span>
        </div>

        <h3 class="section-heading">六、证据列表</h3>
        <div v-if="evidences.length" class="evidences">
          <div v-for="ev in evidences" :key="ev.id" class="evidence-item">
            <span class="evidence-name">{{ attachmentName(ev) }} · 第 {{ ev.page }} 页</span>
            <span class="evidence-snippet">{{ ev.snippet }}</span>
            <span class="evidence-confidence">置信度 {{ ev.confidence }}%</span>
          </div>
        </div>
        <div v-else class="review-box review-empty">暂无证据记录</div>

        <h3 class="section-heading">七、人工复核记录</h3>
        <div v-if="reviewer" class="review-box">
          <span class="review-avatar">{{ reviewer.avatar || reviewer.name.slice(0, 1) }}</span>
          <div class="review-text">
            <div class="review-name">{{ reviewer.name }}（{{ reviewer.role }}）</div>
            <div class="review-content">{{ reviewer.content }}</div>
            <div class="review-time">{{ reviewer.created_at }}</div>
          </div>
        </div>
        <div v-else class="review-box review-empty">暂无人工复核记录</div>

        <div class="report-foot">—— 本报告由财务单据智能风险审核系统自动生成 · 仅供审核参考 ——</div>
      </article>
    </div>
  </div>

  <div v-else class="report-missing">
    <div class="card">
      <h2>报告不存在</h2>
      <p class="muted">未找到对应单据或报告记录。</p>
      <button class="btn btn-primary" type="button" @click="router.push('/reports')">返回报告中心</button>
    </div>
  </div>
</template>

<style scoped>
.report-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
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

.report-body {
  flex: 1;
  padding: 20px 24px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.report-paper {
  width: 780px;
  min-height: 1188px;
  padding: 36px 44px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.doc-head {
  min-height: 43px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.doc-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.doc-title h2 {
  margin: 0;
  font-size: 20px;
  line-height: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.doc-title p {
  margin: 0;
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.doc-divider {
  height: 1px;
  background: var(--border);
}

.section-heading {
  margin: 0;
  font-size: 15px;
  line-height: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.info-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: flex;
  gap: 20px;
}

.info-cell {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  line-height: 16px;
}

.info-cell span {
  color: var(--text-secondary);
  white-space: nowrap;
}

.info-cell strong {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conclusion {
  min-height: 74px;
  padding: 16px;
  border: 1px solid;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.conclusion-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.shield-icon {
  width: 22px;
  height: 22px;
}

.conclusion-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conclusion-title {
  font-size: 14px;
  line-height: 17px;
  font-weight: 700;
}

.conclusion-text p {
  margin: 0;
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.amt-table-wrap {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.amt-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}

.amt-table th {
  height: 38px;
  background: #f9fafb;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  text-align: left;
  padding: 0 12px;
  border-right: 1px solid var(--border);
}

.amt-table th:last-child {
  border-right: none;
}

.amt-table td {
  height: 40px;
  padding: 0 12px;
  border-top: 1px solid var(--border);
  border-right: 1px solid var(--border);
  white-space: nowrap;
}

.amt-table td:last-child {
  border-right: none;
}

.amt-table .strong {
  font-weight: 700;
}

.amt-table .empty-cell {
  text-align: center;
  color: var(--text-secondary);
}

.risk-items {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.risk-report-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 54px;
}

.risk-num {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-secondary);
  flex: none;
}

.risk-report-item .badge {
  flex: none;
}

.risk-report-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.risk-report-title {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.risk-report-basis {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.risk-report-suggestion {
  font-size: 12px;
  line-height: 15px;
  color: var(--mid);
}

.risk-empty {
  font-size: 12px;
  color: var(--text-secondary);
}

.evidences {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-item {
  min-height: 40px;
  padding: 10px 14px;
  background: #f9fafb;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.evidence-name {
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  flex: none;
}

.evidence-snippet {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evidence-confidence {
  font-size: 11px;
  line-height: 13px;
  color: var(--primary);
  font-weight: 700;
  white-space: nowrap;
  flex: none;
}

.vendor-box {
  min-height: 40px;
  padding: 12px 14px;
  border: 1px solid;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.vendor-empty {
  background: #f9fafb;
  border-color: var(--border);
}

.vendor-name {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.vendor-score {
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  white-space: nowrap;
}

.vendor-note {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.review-box {
  min-height: 74px;
  padding: 12px 14px;
  background: #f9fafb;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.review-empty {
  color: var(--text-secondary);
  font-size: 12px;
}

.review-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.review-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.review-name {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
}

.review-content {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.review-time {
  font-size: 11px;
  line-height: 13px;
  color: #98a2b3;
}

.report-foot {
  margin-top: auto;
  padding-top: 8px;
  text-align: center;
  font-size: 11px;
  line-height: 13px;
  color: #98a2b3;
}

.report-missing {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.report-missing .card {
  padding: 40px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
</style>
