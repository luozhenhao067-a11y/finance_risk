<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, FileText, FileSpreadsheet, FileClock, Inbox } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { formatMoney, riskInfo } from '../utils/format'
import { pushToast } from '../composables/useToast'
import { syncReports, syncDocuments } from '../api/realSync'

const router = useRouter()
const store = useAppStore()
const { canExportReport } = store

onMounted(() => {
  syncReports()
  syncDocuments()
})

const keyword = ref('')
const levelFilter = ref('全部等级')

// 数据权限（Spec 4.8）：申请人仅见本人单据报告
const reports = computed(() =>
  [...store.visibleReports()]
    .map((report) => {
      const doc = store.getDocument(report.doc_id)
      return { ...report, doc }
    })
    .filter((report) => report.doc)
    .sort((a, b) => b.generated_at.localeCompare(a.generated_at))
)

const filtered = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return reports.value.filter((report) => {
    const matchLevel = levelFilter.value === '全部等级' || riskInfo(report.overall_level).text === levelFilter.value
    const matchText =
      !text ||
      [report.report_no, report.doc.doc_no, report.doc.title, report.doc.applicant_name].some((value) =>
        String(value || '').toLowerCase().includes(text)
      )
    return matchLevel && matchText
  })
})

// Spec 4.8：单据 approved/completed 后可生成报告
const pendingReports = computed(() =>
  store
    .visibleDocuments()
    .filter((doc) => ['approved', 'completed'].includes(doc.status) && !store.getReportByDoc(doc.id))
)

const summary = computed(() => [
  { label: '报告总数', value: reports.value.length, color: '#2563EB', bg: '#EFF6FF' },
  {
    label: '高风险报告',
    value: reports.value.filter((report) => report.overall_level === 'high').length,
    color: '#DC2626',
    bg: '#FEF2F2'
  },
  {
    label: '已完成单据',
    value: store.visibleDocuments().filter((doc) => doc.status === 'completed').length,
    color: '#16A34A',
    bg: '#F0FDF4'
  },
  { label: '待生成报告', value: pendingReports.value.length, color: '#F59E0B', bg: '#FFFBEB' }
])

function openReport(docId) {
  router.push(`/reports/${docId}`)
}

function generatePending() {
  if (!canExportReport()) {
    pushToast('仅财务审核人与系统管理员可生成报告', 'error')
    return
  }
  const doc = pendingReports.value[0]
  if (!doc) return
  const report = store.ensureReport(doc.id)
  if (report) {
    pushToast(`已生成报告 ${report.report_no}`)
    openReport(doc.id)
  }
}

function exportSummary() {
  if (!canExportReport()) {
    pushToast('仅财务审核人与系统管理员可导出报告', 'error')
    return
  }
  const rows = [
    ['报告编号', '单据编号', '单据类型', '申请人', '单据金额', '整体风险', '生成时间', '复核人'],
    ...reports.value.map((report) => [
      report.report_no,
      report.doc.doc_no,
      report.doc.doc_type,
      report.doc.applicant_name,
      formatMoney(report.doc.total_amount),
      riskInfo(report.overall_level).text,
      report.generated_at,
      report.reviews?.[0]?.name || '—'
    ])
  ]
  const csv = rows.map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `风险审核报告汇总-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  pushToast('报告汇总已导出')
}
</script>

<template>
  <div class="reports-page">
    <header class="page-header">
      <div class="header-title-box">
        <h1 class="header-title">报告中心</h1>
        <div class="header-subtitle">风险审核报告归档与导出 · 报告内容随单据快照留痕</div>
      </div>
      <div class="header-actions">
        <div class="search-box">
          <Search :size="15" />
          <input v-model="keyword" type="text" placeholder="搜索报告编号 / 单据编号" />
        </div>
        <div class="select-wrap">
          <select v-model="levelFilter" class="select" aria-label="整体风险">
            <option>全部等级</option>
            <option>高风险</option>
            <option>中风险</option>
            <option>低风险</option>
            <option>无风险</option>
          </select>
        </div>
        <button v-if="canExportReport()" class="btn btn-outline" type="button" @click="exportSummary">
          <FileSpreadsheet :size="15" />
          <span>导出汇总</span>
        </button>
      </div>
    </header>

    <div class="page-body">
      <div class="summary">
        <div v-for="item in summary" :key="item.label" class="summary-card card">
          <span class="summary-value" :style="{ color: item.color }">{{ item.value }}</span>
          <span class="summary-label">{{ item.label }}</span>
        </div>
      </div>

      <div v-if="pendingReports.length" class="pending-banner">
        <div class="pending-icon"><FileClock :size="18" /></div>
        <div class="pending-text">
          <strong>{{ pendingReports.length }} 张已完成单据尚未生成报告</strong>
          <span>{{ pendingReports.map((doc) => doc.doc_no).join('、') }}</span>
        </div>
        <button v-if="canExportReport()" class="btn btn-soft" type="button" @click="generatePending">生成报告</button>
      </div>

      <section class="list-card card">
        <div class="list-head">
          <div class="list-title-box">
            <h2 class="section-title">历史报告</h2>
            <span class="muted-sm">共 {{ filtered.length }} 份</span>
          </div>
          <span class="list-hint">报告生成后不可修改 · 可导出 Excel / PDF</span>
        </div>

        <div class="table-wrap">
          <table class="data-table report-table">
            <thead>
              <tr>
                <th style="width: 170px">报告编号</th>
                <th style="width: 158px">关联单据</th>
                <th style="min-width: 190px">单据标题</th>
                <th style="width: 106px">单据类型</th>
                <th style="width: 112px">申请人</th>
                <th style="width: 128px">单据金额</th>
                <th style="width: 92px">整体风险</th>
                <th style="width: 142px">生成时间</th>
                <th style="width: 84px">复核人</th>
                <th style="width: 76px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="report in filtered" :key="report.id">
                <td>
                  <button class="report-no" type="button" @click="openReport(report.doc_id)">
                    {{ report.report_no }}
                  </button>
                </td>
                <td>{{ report.doc.doc_no }}</td>
                <td class="title-cell" :title="report.doc.title">{{ report.doc.title }}</td>
                <td>{{ report.doc.doc_type }}</td>
                <td>{{ report.doc.applicant_name }}</td>
                <td class="money">{{ formatMoney(report.doc.total_amount) }}</td>
                <td>
                  <span class="badge" :class="riskInfo(report.overall_level).className">
                    {{ riskInfo(report.overall_level).text }}
                  </span>
                </td>
                <td class="time-cell">{{ report.generated_at }}</td>
                <td>{{ report.reviews?.[0]?.name || '—' }}</td>
                <td>
                  <button class="link" type="button" @click="openReport(report.doc_id)">查看</button>
                </td>
              </tr>
              <tr v-if="!filtered.length">
                <td colspan="10">
                  <div class="empty-state">
                    <Inbox :size="30" />
                    <span>还没有风险审核报告</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="tip-bar">
        <FileText :size="14" />
        <span>报告数据来源：单据快照、附件解析结果、风险规则引擎与人工复核意见。</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reports-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.search-box {
  width: 236px;
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
  width: 108px;
}

.select-wrap .select {
  height: 34px;
  font-size: 12px;
}

.summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  flex: none;
}

.summary-card {
  height: 72px;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
}

.summary-value {
  font-size: 22px;
  line-height: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.summary-label {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
}

.pending-banner {
  min-height: 58px;
  padding: 12px 16px;
  background: #fffbeb;
  border: 1px solid var(--mid-line);
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
}

.pending-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: #fff;
  color: var(--mid);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.pending-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.pending-text strong {
  font-size: 13px;
  color: var(--text-primary);
}

.pending-text span {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.report-table {
  min-width: 1120px;
}

.report-no {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  font-variant-numeric: tabular-nums;
}

.report-no:hover {
  text-decoration: underline;
}

.title-cell {
  max-width: 230px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.time-cell {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.link {
  background: transparent;
  border: none;
  padding: 0;
  font-size: 12px;
}

.tip-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  flex: none;
}
</style>
