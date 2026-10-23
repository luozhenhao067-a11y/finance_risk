// 真实后端模式：把后端接口数据灌入本地 state，视图绑定保持不变。
// mock 模式（VITE_USE_MOCK 未设 false）下所有函数直接返回，不发任何请求。
import { USE_MOCK, client } from './client'
import { state, resetForBackend } from '../mock/db'

export function isRealMode() {
  return !USE_MOCK
}

function upsert(list, row) {
  const index = list.findIndex((item) => item.id === row.id)
  if (index >= 0) list[index] = row
  else list.push(row)
}

function replaceDocSlice(list, docId, rows) {
  for (let index = list.length - 1; index >= 0; index -= 1) {
    if (list[index].doc_id === docId) list.splice(index, 1)
  }
  list.push(...rows)
}

export function applyLogin(user, token) {
  if (USE_MOCK) return
  localStorage.setItem('finance-risk-audit-token', token)
  resetForBackend()
  state.user = { ...user }
  state.auth = true
}

export async function restoreSession() {
  if (USE_MOCK) return false
  const token = localStorage.getItem('finance-risk-audit-token')
  if (!token) return false
  try {
    const data = await client.get('/auth/me')
    resetForBackend()
    state.user = { ...data.user }
    state.auth = true
    return true
  } catch {
    return false
  }
}

export async function syncDocuments(params = {}) {
  if (USE_MOCK) return
  const page = await client.get('/documents', { params: { page_size: 100, ...params } })
  state.documents = page.list || []
}

export async function syncStats() {
  if (USE_MOCK) return
  const stats = await client.get('/dashboard/stats')
  state.stats = { ...stats.kpis }
  state.riskDistribution = { ...stats.risk_distribution }
  state.todos = stats.todos || []
  state.notifications = (stats.notifications || []).map((row) => ({
    id: row.id,
    doc_id: row.doc_id,
    title: row.title,
    time: row.time || '',
    read: !!row.read
  }))
  for (const doc of stats.recent_documents || []) upsert(state.documents, doc)
}

export async function syncDetail(docId) {
  if (USE_MOCK) return
  const id = String(docId)
  const detail = await client.get(`/documents/${docId}`)
  upsert(state.documents, detail.doc)
  replaceDocSlice(state.details, id, detail.details || [])
  replaceDocSlice(state.attachments, id, detail.attachments || [])
  replaceDocSlice(state.parseResults, id, detail.parse_results || [])
  if (detail.risk_analysis) {
    upsert(state.riskAnalyses, detail.risk_analysis)
  }
  replaceDocSlice(state.riskItems, id, detail.risk_items || [])
  const evidences = []
  for (const item of detail.risk_items || []) {
    for (const ev of item.evidences || []) {
      evidences.push({
        id: ev.id,
        risk_item_id: ev.risk_item_id,
        doc_id: id,
        attachment_id: ev.attachment_id,
        page: ev.page,
        snippet: ev.snippet,
        confidence: ev.confidence
      })
    }
  }
  replaceDocSlice(state.riskEvidences, id, evidences)
  const flow = detail.approval_flow || {}
  if (flow.instance) upsert(state.approvalInstances, flow.instance)
  replaceDocSlice(
    state.approvalTasks,
    id,
    (flow.tasks || []).map((task) => ({ ...task, doc_id: String(task.doc_id) }))
  )
  replaceDocSlice(
    state.approvalOpinions,
    id,
    (flow.opinions || []).map((op) => ({ ...op, doc_id: String(op.doc_id) }))
  )
  state.backendChains[id] = (flow.chain || []).map((node) => node.node)
  replaceDocSlice(state.operationLogs, id, detail.logs || [])
  if (detail.report) upsert(state.reports, detail.report)
}

export async function syncApprovals() {
  if (USE_MOCK) return
  const todo = await client.get('/approvals/todo')
  for (const row of todo || []) {
    upsert(state.documents, row.doc)
    upsert(state.approvalTasks, {
      id: row.task_id,
      instance_id: '',
      doc_id: String(row.doc.id),
      node: row.node,
      assignee: state.user.name,
      status: 'pending',
      action: null,
      finished_at: null
    })
    if (row.risk_analysis) {
      const analysis = { ...row.risk_analysis, id: row.doc.id, doc_id: String(row.doc.id) }
      upsert(state.riskAnalyses, analysis)
    }
  }
}

export async function syncRiskItems() {
  if (USE_MOCK) return
  const page = await client.get('/risk-items', { params: { page_size: 100 } })
  const items = []
  for (const row of page.list || []) {
    upsert(state.documents, row.doc)
    items.push({ ...row.item, doc: row.doc })
  }
  state.riskItems = items
}

export async function syncReports() {
  if (USE_MOCK) return
  const page = await client.get('/reports', { params: { page_size: 100 } })
  const reports = []
  for (const row of page.list || []) {
    upsert(state.documents, row.doc)
    reports.push({ ...row.report, doc: row.doc })
  }
  state.reports = reports
}

export async function syncLogs() {
  if (USE_MOCK) return
  const page = await client.get('/logs', { params: { page_size: 200 } })
  state.operationLogs = page.list || []
}

export async function syncRules() {
  if (USE_MOCK) return
  const rules = await client.get('/admin/risk-rules')
  if (Array.isArray(rules)) state.riskRules = rules
}
