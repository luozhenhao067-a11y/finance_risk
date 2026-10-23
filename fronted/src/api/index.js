// API 层：与 Spec 第 6 章接口一一对应。mock 模式调用 mock/db.js，真实模式走 axios。
import { client, USE_MOCK } from './client'
import * as db from '../mock/db'

const call = (mockFn, axiosFn) => {
  if (USE_MOCK) {
    return Promise.resolve().then(() => mockFn())
  }
  return axiosFn()
}

// 认证
export const login = (username, password, remember) =>
  call(
    () => db.login(username, password, remember),
    () => client.post('/auth/login', { username, password })
  )
export const logout = () =>
  call(
    () => db.logout(),
    () => client.post('/auth/logout')
  )

// 单据
export const createDocument = (form, submit) =>
  call(
    () => db.createDocument(form, submit),
    () => client.post('/documents', { ...form, submit })
  )
export const submitDocument = (id) =>
  call(
    () => db.submitDraft(id),
    () => client.post(`/documents/${id}/submit`)
  )
export const resubmitDocument = (id) =>
  call(
    () => db.resubmitDocument(id),
    () => client.post(`/documents/${id}/resubmit`)
  )
export const withdrawDocument = (id) =>
  call(
    () => db.withdrawDocument(id),
    () => client.post(`/documents/${id}/withdraw`)
  )

// 审批
export const approveTask = (docId, action, opinion) =>
  call(
    () => db.approveDocument(docId, action, opinion),
    () => client.post(`/documents/${docId}/approve`, { action, opinion })
  )
export const confirmComplete = (id) =>
  call(
    () => db.confirmComplete(id),
    () => client.post(`/documents/${id}/complete`)
  )
export const restoreDocument = (id, reason) =>
  call(
    () => db.restoreDocument(id, reason),
    () => client.post(`/documents/${id}/restore`, { reason })
  )

// 风险
export const handleRiskItem = (itemId, status, opinion) =>
  call(
    () => db.handleRiskItem(itemId, status, opinion),
    () => client.put(`/risk-items/${itemId}/handle`, { status, opinion })
  )
export const rerunAnalysis = (docId, reason) =>
  call(
    () => db.rerunAnalysis(docId, reason),
    () => client.post(`/documents/${docId}/risk-analysis/rerun`, { reason })
  )

// 报告
export const generateReport = (docId) =>
  call(
    () => db.ensureReport(docId),
    () => client.post(`/documents/${docId}/report`)
  )

// 智能问答
export const askAi = (docId, question) =>
  call(
    () => db.askAi(docId, question),
    () => client.post(`/documents/${docId}/ai-qa`, { question }, { timeout: 60000 })
  )

// 通知
export const markNotificationsRead = () =>
  call(
    () => db.markAllNotificationsRead(),
    () => client.put('/notifications/read-all')
  )

// 系统管理
export const updateRiskRule = (code, patch) =>
  call(
    () => db.updateRiskRule(code, patch),
    () => client.put(`/admin/risk-rules/${code}`, patch)
  )
