<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, FileSpreadsheet, History, Inbox } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { pushToast } from '../composables/useToast'
import { syncLogs } from '../api/realSync'

const router = useRouter()
const store = useAppStore()
const { canViewLogs } = store

onMounted(() => {
  syncLogs()
})

const keyword = ref('')
const actionFilter = ref('全部操作')

// 权限（Spec 4.9）：仅财务与管理员可见
if (!canViewLogs()) {
  router.replace('/dashboard')
}

const logs = computed(() =>
  [...store.visibleLogs()]
    .map((log) => ({ ...log, doc: store.getDocument(log.doc_id) }))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
)

const actions = computed(() => [...new Set(logs.value.map((log) => log.action))])

const filtered = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return logs.value.filter((log) => {
    const matchAction = actionFilter.value === '全部操作' || log.action === actionFilter.value
    const matchText =
      !text ||
      [log.action, log.operator, log.role, log.detail, log.doc?.doc_no, log.doc?.title].some((value) =>
        String(value || '').toLowerCase().includes(text)
      )
    return matchAction && matchText
  })
})

function actionClass(action) {
  if (['审批通过', '审批完成'].includes(action)) return 'badge-green'
  if (['驳回单据'].includes(action)) return 'badge-red'
  if (['退回单据', '撤回单据', '风险分析完成'].includes(action)) return 'badge-amber'
  if (['提交审批', '重新提交', '生成报告', '上传附件'].includes(action)) return 'badge-blue'
  return 'badge-gray'
}

function openDoc(log) {
  if (log.doc) router.push(`/documents/${log.doc_id}`)
}

function exportLogs() {
  const rows = [
    ['操作时间', '操作类型', '单据编号', '单据标题', '操作人', '角色', '详情'],
    ...filtered.value.map((log) => [
      log.created_at,
      log.action,
      log.doc?.doc_no || log.doc_id,
      log.doc?.title || '—',
      log.operator,
      log.role,
      log.detail
    ])
  ]
  const csv = rows.map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `审计日志-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  pushToast('审计日志已导出')
}
</script>

<template>
  <div class="logs-page">
    <header class="page-header">
      <div class="header-title-box">
        <h1 class="header-title">审计日志</h1>
        <div class="header-subtitle">全流程操作留痕 · 共 {{ logs.length }} 条记录 · 日志只读不可修改</div>
      </div>
      <div class="header-actions">
        <div class="search-box">
          <Search :size="15" />
          <input v-model="keyword" type="text" placeholder="搜索操作人 / 单据编号 / 详情" />
        </div>
        <div class="select-wrap">
          <select v-model="actionFilter" class="select" aria-label="操作类型">
            <option>全部操作</option>
            <option v-for="action in actions" :key="action">{{ action }}</option>
          </select>
        </div>
        <button class="btn btn-outline" type="button" @click="exportLogs">
          <FileSpreadsheet :size="15" />
          <span>导出日志</span>
        </button>
      </div>
    </header>

    <div class="page-body">
      <section class="list-card card">
        <div class="list-head">
          <div class="list-title-box">
            <div class="title-icon"><History :size="17" /></div>
            <div>
              <h2 class="section-title">操作记录</h2>
              <span class="muted-sm">当前显示 {{ filtered.length }} 条</span>
            </div>
          </div>
          <span class="list-hint">系统自动记录创建、提交、审批、风险分析与报告生成等关键操作</span>
        </div>

        <div class="table-wrap">
          <table class="data-table logs-table">
            <thead>
              <tr>
                <th style="width: 150px">操作时间</th>
                <th style="width: 122px">操作类型</th>
                <th style="width: 158px">单据编号</th>
                <th style="min-width: 190px">单据标题</th>
                <th style="width: 90px">操作人</th>
                <th style="width: 86px">角色</th>
                <th style="min-width: 300px">操作详情</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in filtered" :key="log.id">
                <td class="time-cell">{{ log.created_at }}</td>
                <td><span class="badge" :class="actionClass(log.action)">{{ log.action }}</span></td>
                <td>
                  <button v-if="log.doc" class="doc-no" type="button" @click="openDoc(log)">
                    {{ log.doc.doc_no }}
                  </button>
                  <span v-else>—</span>
                </td>
                <td class="title-cell" :title="log.doc?.title">{{ log.doc?.title || '—' }}</td>
                <td>{{ log.operator }}</td>
                <td>
                  <span class="role-text" :class="{ system: log.role === '系统' }">{{ log.role }}</span>
                </td>
                <td class="detail-cell" :title="log.detail">{{ log.detail }}</td>
              </tr>
              <tr v-if="!filtered.length">
                <td colspan="7">
                  <div class="empty-state">
                    <Inbox :size="30" />
                    <span>没有匹配的审计日志</span>
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
.logs-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.search-box {
  width: 260px;
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
  width: 124px;
}

.select-wrap .select {
  height: 34px;
  font-size: 12px;
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

.title-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--primary-weak);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.muted-sm {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.list-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.logs-table {
  min-width: 1100px;
}

.time-cell {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.doc-no {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
}

.doc-no:hover {
  text-decoration: underline;
}

.title-cell {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role-text {
  display: inline-flex;
  align-items: center;
  height: 21px;
  padding: 3px 8px;
  border-radius: 4px;
  background: var(--bg);
  color: var(--text-secondary);
  font-size: 11px;
}

.role-text.system {
  background: #eef2ff;
  color: #4f46e5;
}

.detail-cell {
  max-width: 420px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
