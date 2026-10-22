// Mock 数据库与业务逻辑层（对应后端 service 层，Spec 第 6 章接口的本地实现）
// 接入真实后端后：api/ 层切换为 axios 请求，本文件整体废弃
import { reactive } from 'vue'
import { seedState, FLOW_CONFIG } from '../data/seed'

const STORAGE_KEY = 'finance-risk-audit-state-v1'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function loadState() {
  if (typeof localStorage === 'undefined') return clone(seedState)
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return clone(seedState)
    const parsed = JSON.parse(raw)
    if (parsed.schemaVersion !== seedState.schemaVersion) return clone(seedState)
    return parsed
  } catch {
    return clone(seedState)
  }
}

export const state = reactive(loadState())

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* storage can be unavailable in private mode */
  }
}

const pad = (n) => String(n).padStart(2, '0')

export function nowStamp(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function todayCompact() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`
}

function uid(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
}

function nextDocNo() {
  const prefix = `FY${todayCompact()}-`
  const used = state.documents
    .filter((doc) => doc.doc_no.startsWith(prefix))
    .map((doc) => Number(doc.doc_no.slice(prefix.length)))
    .filter((n) => Number.isFinite(n))
  const next = used.length ? Math.max(...used) + 1 : 1
  return `${prefix}${String(next).padStart(3, '0')}`
}

function nextReportNo() {
  const nums = state.reports
    .map((report) => Number(String(report.report_no).slice(-4)))
    .filter((n) => Number.isFinite(n))
  const next = nums.length ? Math.max(...nums) + 1 : 88
  return `RPT-${todayCompact()}-${String(next).padStart(4, '0')}`
}

// ---------------- 查询 ----------------

export function getDocument(id) {
  return state.documents.find((doc) => doc.id === id)
}

export function getDetails(docId) {
  return state.details.filter((row) => row.doc_id === docId)
}

export function getAttachments(docId) {
  return state.attachments.filter((row) => row.doc_id === docId)
}

export function getRiskAnalysis(docId) {
  return state.riskAnalyses.find((row) => row.doc_id === docId)
}

export function getRiskItems(docId) {
  return state.riskItems.filter((row) => row.doc_id === docId)
}

export function getParseResults(docId) {
  return state.parseResults.filter((row) => row.doc_id === docId)
}

export function getOpinions(docId) {
  return state.approvalOpinions
    .filter((row) => row.doc_id === docId)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
}

export function getLogs(docId) {
  return state.operationLogs
    .filter((row) => row.doc_id === docId)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
}

export function getTasks(docId) {
  return state.approvalTasks.filter((row) => row.doc_id === docId)
}

export function getReportByDoc(docId) {
  return state.reports.find((report) => report.doc_id === docId)
}

export function getRiskEvidences(docId) {
  return state.riskEvidences.filter((row) => row.doc_id === docId)
}

// 审批链（Spec 5.4：基础链 + 金额条件加签）
export function getFlowChain(doc) {
  const chain = [...FLOW_CONFIG.baseNodes]
  if (Number(doc.total_amount) >= FLOW_CONFIG.extraNode.threshold) {
    chain.splice(2, 0, FLOW_CONFIG.extraNode.node)
  }
  return chain
}

const NODE_ASSIGNEE = {
  部门负责人审批: '李明',
  分管副总审批: '赵刚',
  财务审核: '王芳'
}

// ---------------- 权限（Spec 5.3 流转规则矩阵 + 数据权限） ----------------

export function canViewDoc(user, doc) {
  if (!user) return false
  if (['FINANCE', 'ADMIN'].includes(user.role_code)) return true
  if (user.role_code === 'DEPT_MANAGER') return doc.dept_id === user.dept_id
  if (user.role_code === 'APPLICANT') return doc.applicant_id === user.id
  return false
}

export function visibleDocuments() {
  return state.documents.filter((doc) => canViewDoc(state.user, doc))
}

export function visibleRiskItems() {
  return state.riskItems.filter((item) => {
    const doc = getDocument(item.doc_id)
    return doc && canViewDoc(state.user, doc)
  })
}

export function visibleLogs() {
  return state.operationLogs.filter((log) => {
    const doc = getDocument(log.doc_id)
    return !doc || canViewDoc(state.user, doc)
  })
}

export function visibleReports() {
  return state.reports.filter((report) => {
    const doc = getDocument(report.doc_id)
    return doc && canViewDoc(state.user, doc)
  })
}

function isApplicantOwn(user, doc) {
  return user.role_code === 'APPLICANT' && doc.applicant_id === user.id
}

export function canEditDoc(doc) {
  const user = state.user
  return isApplicantOwn(user, doc) && ['draft', 'returned'].includes(doc.status)
}

export function canWithdraw(doc) {
  return isApplicantOwn(state.user, doc) && doc.status === 'pending_approval'
}

export function canResubmit(doc) {
  return isApplicantOwn(state.user, doc) && doc.status === 'returned'
}

export function canApprove(doc) {
  if (doc.status !== 'pending_approval') return false
  const task = state.approvalTasks.find(
    (row) => row.doc_id === doc.id && row.status === 'pending' && row.node === doc.current_node
  )
  return Boolean(task && task.assignee === state.user.name)
}

export function canConfirmComplete(doc) {
  return doc.status === 'approved' && ['FINANCE', 'ADMIN'].includes(state.user.role_code)
}

export function canRestore(doc) {
  return doc.status === 'rejected' && state.user.role_code === 'ADMIN'
}

export function canHandleRisk() {
  return ['FINANCE', 'DEPT_MANAGER', 'ADMIN'].includes(state.user.role_code)
}

export function canRerunAnalysis() {
  return ['FINANCE', 'ADMIN'].includes(state.user.role_code)
}

export function canExportReport() {
  return ['FINANCE', 'ADMIN'].includes(state.user.role_code)
}

export function canViewLogs() {
  return ['FINANCE', 'ADMIN'].includes(state.user.role_code)
}

export function canViewApprovals() {
  return ['DEPT_MANAGER', 'FINANCE', 'ADMIN'].includes(state.user.role_code)
}

export function canViewAdmin() {
  return state.user.role_code === 'ADMIN'
}

// 待我审批队列（Spec 4.7：按 assignee = 当前用户过滤）
export function getApprovalQueue() {
  const assigned = new Set(
    state.approvalTasks
      .filter((task) => task.status === 'pending' && task.assignee === state.user.name)
      .map((task) => task.doc_id)
  )
  return state.documents.filter((doc) => assigned.has(doc.id) && doc.status === 'pending_approval')
}

// ---------------- 校验（Spec 4.4 字段与校验规则） ----------------

const INVOICE_PATTERN = /^(\d{8}|\d{10}|(INV|HT)-\d+)$/i

export function validateSubmitForm(form) {
  if (!form.title || !String(form.title).trim()) return { ok: false, message: '请填写单据标题' }
  if (!form.project || !String(form.project).trim()) return { ok: false, message: '请填写费用项目' }
  if (!form.details || !form.details.length) return { ok: false, message: '请至少添加一条费用明细' }
  const today = todayCompact()
  for (const row of form.details) {
    if (!row.expense_type || !row.expense_date || !(Number(row.amount) > 0)) {
      return { ok: false, message: '请补全费用明细的类型、日期与金额' }
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row.expense_date)) {
      return { ok: false, message: '费用日期格式应为 YYYY-MM-DD' }
    }
    if (row.expense_date > today) return { ok: false, message: '费用日期不能晚于今天' }
    const decimals = String(Number(row.amount)).split('.')[1]
    if (decimals && decimals.length > 2) return { ok: false, message: '金额最多保留 2 位小数' }
    const needInvoice = ['费用报销', '差旅费报销'].includes(form.doc_type)
    if (needInvoice) {
      if (!row.invoice_no || !String(row.invoice_no).trim()) {
        return { ok: false, message: `报销类单据发票号必填（明细：${row.expense_type}）` }
      }
      if (!INVOICE_PATTERN.test(String(row.invoice_no).trim())) {
        return { ok: false, message: `发票号格式不正确（明细：${row.expense_type}）` }
      }
    }
  }
  const files = form.attachments || []
  const hasInvoice = files.some((file) => /发票|票据/i.test(file.file_name))
  const hasContract = files.some((file) => /合同/i.test(file.file_name))
  if (['费用报销', '差旅费报销'].includes(form.doc_type) && !hasInvoice) {
    return { ok: false, message: '报销类单据必须上传至少 1 个发票附件' }
  }
  if (['采购付款', '合同付款'].includes(form.doc_type) && !hasContract) {
    return { ok: false, message: '采购付款/合同付款必须上传合同附件' }
  }
  return { ok: true }
}

// ---------------- 日志 ----------------

function recordLog(docId, action, detail, operator = state.user.name, role = state.user.role) {
  state.operationLogs.push({
    id: uid('log'),
    doc_id: docId,
    action,
    operator,
    role,
    detail,
    created_at: nowStamp()
  })
}

function pushNotification(docId, title) {
  state.notifications.unshift({ id: uid('n'), doc_id: docId, title, time: '刚刚', read: false })
}

// ---------------- 提交链路（Spec 3.1：submitted → analyzing → pending_approval） ----------------

function createSnapshot(doc) {
  const snapshot = {
    id: uid('snap'),
    doc_id: doc.id,
    version: doc.version,
    created_at: nowStamp(),
    immutable: true,
    payload: {
      document: clone(doc),
      details: clone(getDetails(doc.id)),
      attachments: clone(getAttachments(doc.id))
    }
  }
  state.snapshots.push(snapshot)
  return snapshot
}

function createParseResult(doc) {
  const attachments = getAttachments(doc.id)
  if (!attachments.length) return
  const details = getDetails(doc.id)
  const firstDetail = details[0] || {}
  const file = attachments.find((row) => row.file_name.includes('发票')) || attachments[0]
  const total = details.reduce((acc, row) => acc + Number(row.amount || 0), 0)
  const tax = Math.round((total * 0.06) / 1.06) / 100
  state.parseResults.push({
    id: uid('pr'),
    doc_id: doc.id,
    attachment_id: file.id,
    file_name: file.file_name,
    page: 1,
    confidence: 96,
    fields: [
      { label: '发票号码', value: firstDetail.invoice_no || '未识别', confidence: 96 },
      { label: '开票日期', value: firstDetail.expense_date || doc.create_time.slice(0, 10), confidence: 94 },
      { label: '销售方', value: doc.project ? `${doc.project}服务商` : '未识别销售方', confidence: 91 },
      {
        label: '金额合计',
        value: `¥${total.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
        confidence: 98
      },
      { label: '税额', value: `¥${tax.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, confidence: 89 }
    ]
  })
}

function createInstanceAndTask(doc) {
  const chain = getFlowChain(doc)
  const firstNode = chain[1]
  const instance = {
    id: uid('ai'),
    doc_id: doc.id,
    status: 'running',
    current_node: firstNode
  }
  state.approvalInstances.push(instance)
  state.approvalTasks.push({
    id: uid('task'),
    instance_id: instance.id,
    doc_id: doc.id,
    node: firstNode,
    assignee: NODE_ASSIGNEE[firstNode] || '李明',
    status: 'pending',
    finished_at: null
  })
}

function buildRiskAnalysis(doc, triggerType = 'auto') {
  const details = getDetails(doc.id)
  const attachments = getAttachments(doc.id)
  // 清理旧版本分析结果（保留历史可按 doc_version 扩展）
  state.riskEvidences = state.riskEvidences.filter((row) => row.doc_id !== doc.id)
  state.riskAnalyses = state.riskAnalyses.filter((row) => row.doc_id !== doc.id)
  state.riskItems = state.riskItems.filter((row) => row.doc_id !== doc.id)
  const missingInvoice = details.some((row) => !row.invoice_no || row.invoice_no === '—')
  const level = missingInvoice ? 'mid' : 'low'
  const analysis = {
    id: uid('ra'),
    doc_id: doc.id,
    doc_version: doc.version,
    status: 'completed',
    overall_level: level,
    high_count: 0,
    mid_count: missingInvoice ? 1 : 0,
    low_count: missingInvoice ? 0 : 1,
    recommendation: missingInvoice ? 'supplement' : 'pass',
    recommendation_label: missingInvoice ? '补充材料' : '建议通过',
    summary: missingInvoice
      ? '存在明细缺少发票号，建议补充完整票据后提交审批'
      : '明细合计与单据金额一致，附件完整，未发现明显风险',
    trigger_type: triggerType,
    analyzed_at: nowStamp()
  }
  state.riskAnalyses.push(analysis)

  state.riskItems.push(
    missingInvoice
      ? {
          id: uid('ri'),
          doc_id: doc.id,
          rule_code: 'R-09',
          level: 'mid',
          title: '发票信息不完整',
          basis: '部分费用明细未填写发票号',
          evidence: '系统规则校验 · 发票号必填项缺失',
          suggestion: '补充发票号或上传对应票据',
          page: 1,
          confidence: 90,
          status: 'open'
        }
      : {
          id: uid('ri'),
          doc_id: doc.id,
          rule_code: 'R-02',
          level: 'low',
          title: '自动校验通过',
          basis: '明细合计与单据金额一致，附件类型完整',
          evidence: `系统规则校验 · 附件 ${attachments.length} 个`,
          suggestion: '无需处理，可继续审批',
          page: 1,
          confidence: 99,
          status: 'open'
        }
  )

  doc.risk_level = level
  doc.risk_count = 1
  recordLog(doc.id, '风险分析完成', `识别 1 项风险，整体等级：${level === 'mid' ? '中风险' : '低风险'}`, '系统', '系统')
  pushNotification(doc.id, `${doc.doc_no} 风险分析完成`)
  return analysis
}

// 异步链路：submitted → analyzing → pending_approval（Spec 8.4 异步模拟）
function runSubmitChain(docId, docVersion) {
  const doc = getDocument(docId)
  if (!doc) return
  doc.status = 'submitted'
  doc.current_node = '—'
  doc.queue_time = ''
  persist()
  setTimeout(() => {
    if (doc.status !== 'submitted') return
    doc.status = 'analyzing'
    recordLog(docId, '开始风险分析', '附件解析任务与风险分析任务已创建', '系统', '系统')
    persist()
    setTimeout(() => {
      if (doc.status !== 'analyzing') return
      doc.status = 'pending_approval'
      doc.current_node = getFlowChain(doc)[1]
      doc.queue_time = doc.submit_time.slice(11, 16)
      buildRiskAnalysis(doc, 'auto')
      persist()
    }, 1800)
  }, 700)
}

// ---------------- 认证 ----------------

export function login(username, password, remember) {
  if (!username.trim() || !password) {
    throw new Error('请输入用户名和密码')
  }
  const account = state.users.find((row) => row.name === username.trim())
  if (!account) {
    throw new Error('账号不存在，请从演示账号中选择')
  }
  state.user = { ...account }
  state.auth = true
  if (remember) {
    state.rememberedUser = account.name
  }
  persist()
}

export function logout() {
  state.auth = false
  persist()
}

export function markAllNotificationsRead() {
  state.notifications.forEach((item) => {
    item.read = true
  })
  persist()
}

export function resetDemo() {
  localStorage.removeItem(STORAGE_KEY)
  window.location.reload()
}

// ---------------- 单据操作（Spec 5.3 状态机） ----------------

export function createDocument(form, submit = false) {
  const now = nowStamp()
  const details = form.details.map((row) => ({
    id: uid('dd'),
    doc_id: '',
    expense_type: row.expense_type,
    expense_date: row.expense_date,
    amount: Number(row.amount) || 0,
    invoice_no: row.invoice_no || '',
    remark: row.remark || ''
  }))
  const totalAmount = details.reduce((acc, row) => acc + row.amount, 0)
  const doc = {
    id: uid('doc'),
    doc_no: nextDocNo(),
    doc_type: form.doc_type,
    title: String(form.title).trim(),
    applicant_id: state.user.id,
    applicant_name: state.user.name,
    dept_id: state.user.dept_id || 'dept-market',
    dept_name: form.dept || state.user.dept,
    project: String(form.project).trim(),
    total_amount: totalAmount,
    status: submit ? 'submitted' : 'draft',
    version: 1,
    current_node: submit ? '—' : null,
    submit_time: submit ? now : null,
    create_time: now,
    risk_level: 'none',
    risk_count: 0,
    queue_time: ''
  }
  state.documents.unshift(doc)
  details.forEach((row) => {
    row.doc_id = doc.id
    state.details.push(row)
  })
  form.attachments.forEach((file) => {
    state.attachments.push({
      id: uid('at'),
      doc_id: doc.id,
      file_name: file.file_name,
      size_label: file.size_label,
      mime: file.mime || '',
      file_type: file.file_type || 'pdf',
      path: `/files/${doc.doc_no}/v${doc.version}/${file.file_name}`,
      uploaded_at: now,
      parse_status: 'parsed'
    })
  })
  createParseResult(doc)
  recordLog(doc.id, '创建单据', submit ? `创建并提交单据，合计 ¥${totalAmount.toFixed(2)}` : '保存单据草稿')

  if (submit) {
    createSnapshot(doc)
    createInstanceAndTask(doc)
    recordLog(doc.id, '提交审批', `生成快照 v${doc.version}，提交至${getFlowChain(doc)[1]}`)
    persist()
    runSubmitChain(doc.id)
  } else {
    persist()
  }
  return doc
}

export function submitDraft(docId) {
  const doc = getDocument(docId)
  if (!doc || doc.status !== 'draft') return null
  const check = validateSubmitForm({
    doc_type: doc.doc_type,
    title: doc.title,
    project: doc.project,
    details: getDetails(docId).map((row) => ({ ...row })),
    attachments: getAttachments(docId)
  })
  if (!check.ok) {
    throw new Error(check.message)
  }
  doc.submit_time = nowStamp()
  createSnapshot(doc)
  createInstanceAndTask(doc)
  recordLog(docId, '提交审批', `生成快照 v${doc.version}，提交至${getFlowChain(doc)[1]}`)
  persist()
  runSubmitChain(docId)
  return doc
}

// 退回重提（仅 returned，version + 1，Spec 3.4）
export function resubmitDocument(docId) {
  const doc = getDocument(docId)
  if (!doc || doc.status !== 'returned') return null
  doc.version += 1
  doc.submit_time = nowStamp()
  createSnapshot(doc)
  const instance = {
    id: uid('ai'),
    doc_id: docId,
    status: 'running',
    current_node: getFlowChain(doc)[1]
  }
  state.approvalInstances.push(instance)
  state.approvalTasks.push({
    id: uid('task'),
    instance_id: instance.id,
    doc_id: docId,
    node: instance.current_node,
    assignee: NODE_ASSIGNEE[instance.current_node] || '李明',
    status: 'pending',
    finished_at: null
  })
  state.approvalOpinions.push({
    id: uid('op'),
    doc_id: docId,
    task_id: null,
    node: '申请人提交',
    user: doc.applicant_name,
    action: 'resubmit',
    opinion: `退回后重新提交，版本 v${doc.version}`,
    created_at: nowStamp()
  })
  recordLog(docId, '重新提交', `版本升级至 v${doc.version}，生成新快照`)
  persist()
  runSubmitChain(docId)
  return doc
}

export function withdrawDocument(docId) {
  const doc = getDocument(docId)
  if (!doc || doc.status !== 'pending_approval') return null
  doc.status = 'returned'
  doc.current_node = null
  doc.queue_time = ''
  const instance = state.approvalInstances.find((row) => row.doc_id === docId)
  if (instance) {
    instance.status = 'returned'
    instance.current_node = null
  }
  state.approvalTasks
    .filter((task) => task.doc_id === docId && task.status === 'pending')
    .forEach((task) => {
      task.status = 'cancelled'
      task.finished_at = nowStamp()
    })
  state.approvalOpinions.push({
    id: uid('op'),
    doc_id: docId,
    task_id: null,
    node: '申请人提交',
    user: state.user.name,
    action: 'withdraw',
    opinion: '申请人撤回单据',
    created_at: nowStamp()
  })
  recordLog(docId, '撤回单据', '申请人撤回，单据状态变更为已退回')
  persist()
  return doc
}

// 审批操作（Spec 3.3 决策点；最后节点通过 → approved，由财务确认完成后 completed）
export function approveDocument(docId, action, opinion) {
  const doc = getDocument(docId)
  if (!doc) return null
  const task = state.approvalTasks.find((row) => row.doc_id === docId && row.status === 'pending')
  const node = doc.current_node
  const opinionText = opinion.trim()
  const actionLabel = action === 'approve' ? '通过' : action === 'return' ? '退回' : '驳回'
  const defaultOpinion = {
    approve: '同意，审批通过。',
    return: '材料需补充，退回申请人修改后重新提交。',
    reject: '不符合报销规范，予以驳回。'
  }

  if (task) {
    task.status = 'done'
    task.action = action === 'approve' ? 'approved' : action
    task.finished_at = nowStamp()
  }
  state.approvalOpinions.push({
    id: uid('op'),
    doc_id: docId,
    task_id: task ? task.id : null,
    node,
    user: state.user.name,
    action,
    opinion: opinionText || defaultOpinion[action],
    created_at: nowStamp()
  })

  const instance = state.approvalInstances.find((row) => row.doc_id === docId)

  if (action === 'approve') {
    const chain = getFlowChain(doc)
    const index = chain.indexOf(node)
    const next = chain[index + 1]
    if (next && next !== '审批完成') {
      doc.current_node = next
      doc.status = 'pending_approval'
      if (instance) instance.current_node = next
      state.approvalTasks.push({
        id: uid('task'),
        instance_id: instance ? instance.id : null,
        doc_id: docId,
        node: next,
        assignee: NODE_ASSIGNEE[next] || '王芳',
        status: 'pending',
        finished_at: null
      })
      recordLog(docId, '审批通过', `${node}通过，流转至${next}`)
    } else {
      doc.current_node = '审批完成'
      doc.status = 'approved'
      doc.queue_time = ''
      if (instance) {
        instance.status = 'completed'
        instance.current_node = '审批完成'
      }
      ensureReport(docId)
      recordLog(docId, '审批通过', `${node}通过，单据已通过审批，待财务确认完成`)
      pushNotification(docId, `${doc.doc_no} 审批通过`)
    }
    persist()
    return doc
  }

  doc.status = action === 'return' ? 'returned' : 'rejected'
  doc.current_node = null
  doc.queue_time = ''
  if (task) task.status = 'done'
  if (instance) {
    instance.status = action === 'return' ? 'returned' : 'rejected'
    instance.current_node = null
  }
  state.approvalTasks
    .filter((row) => row.doc_id === docId && row.status === 'pending')
    .forEach((row) => {
      row.status = 'cancelled'
      row.finished_at = nowStamp()
    })
  recordLog(docId, action === 'return' ? '退回单据' : '驳回单据', opinionText || defaultOpinion[action])
  persist()
  return doc
}

// 财务确认完成（approved → completed，Spec 5.3）
export function confirmComplete(docId) {
  const doc = getDocument(docId)
  if (!doc || doc.status !== 'approved') return null
  doc.status = 'completed'
  doc.queue_time = ''
  recordLog(docId, '审批完成', `${state.user.name}确认完成，单据归档`)
  pushNotification(docId, `${doc.doc_no} 已完成归档`)
  persist()
  return doc
}

// 管理员恢复驳回单据（rejected → draft，Spec 5.3）
export function restoreDocument(docId, reason) {
  const doc = getDocument(docId)
  if (!doc || doc.status !== 'rejected') return null
  doc.status = 'draft'
  doc.current_node = null
  doc.queue_time = ''
  recordLog(docId, '恢复单据', `管理员恢复驳回单据为草稿。原因：${reason}`)
  persist()
  return doc
}

// 风险处理（Spec 4.5 Tab4：handled / dismissed + 意见）
export function handleRiskItem(itemId, status, opinion) {
  const item = state.riskItems.find((row) => row.id === itemId)
  if (!item) return null
  item.status = status
  item.handled_by = state.user.name
  item.handled_at = nowStamp()
  item.handle_opinion = opinion || ''
  const doc = getDocument(item.doc_id)
  recordLog(item.doc_id, '风险处理', `${status === 'handled' ? '标记已处理' : '排除'}风险项「${item.title}」${opinion ? `：${opinion}` : ''}`)
  if (doc) pushNotification(doc.id, `${doc.doc_no} 风险项已处理`)
  persist()
  return item
}

// 手动重新分析（Spec 3.2 人工触发）
export function rerunAnalysis(docId, reason = '人工触发') {
  const doc = getDocument(docId)
  if (!doc) return null
  const analysis = buildRiskAnalysis(doc, 'manual')
  recordLog(docId, '重新分析', `${state.user.name}触发重新分析。原因：${reason}`)
  persist()
  return analysis
}

export function addAttachments(docId, files) {
  const doc = getDocument(docId)
  if (!doc) return
  files.forEach((file) => {
    state.attachments.push({
      id: uid('at'),
      doc_id: docId,
      file_name: file.file_name,
      size_label: file.size_label,
      mime: file.mime || '',
      file_type: file.file_type || 'pdf',
      path: `/files/${doc.doc_no}/v${doc.version}/${file.file_name}`,
      uploaded_at: nowStamp(),
      parse_status: 'parsed'
    })
  })
  recordLog(docId, '上传附件', `新增 ${files.length} 个附件`)
  persist()
}

// ---------------- 报告（Spec 4.8） ----------------

export function ensureReport(docId) {
  const existing = getReportByDoc(docId)
  if (existing) return existing
  const doc = getDocument(docId)
  if (!doc) return null
  const analysis = getRiskAnalysis(docId) || {
    overall_level: 'none',
    high_count: 0,
    mid_count: 0,
    low_count: 0,
    recommendation_label: '建议通过',
    summary: '未发现明显风险'
  }
  const details = getDetails(docId)
  const amountChecks = details.map((row) => ({
    name: row.expense_type,
    doc_amount: row.amount,
    parsed_amount: row.amount,
    diff: 0,
    conclusion: '一致'
  }))
  const total = details.reduce((acc, row) => acc + Number(row.amount), 0)
  if (amountChecks.length) {
    amountChecks.push({
      name: '合计',
      doc_amount: total,
      parsed_amount: total,
      diff: 0,
      conclusion: '一致',
      is_total: true
    })
  }
  const reviews = getOpinions(docId)
    .filter((row) => ['approve', 'return', 'reject'].includes(row.action))
    .map((row) => ({
      name: row.user,
      role: row.user === '王芳' ? '财务' : '审批人',
      avatar: row.user.slice(0, 1),
      content: row.opinion,
      created_at: row.created_at
    }))
  const report = {
    id: uid('rpt'),
    doc_id: docId,
    report_no: nextReportNo(),
    generated_at: nowStamp(),
    overall_level: analysis.overall_level,
    overall_text: `整体风险：${({ high: '高风险', mid: '中风险', low: '低风险', none: '无风险' })[analysis.overall_level] || '无风险'}（${analysis.high_count + analysis.mid_count + analysis.low_count} 项：高 ${analysis.high_count} · 中 ${analysis.mid_count} · 低 ${analysis.low_count}）`,
    recommendation_label: analysis.recommendation_label,
    summary: analysis.summary,
    amount_checks: amountChecks,
    vendor: null,
    reviews
  }
  state.reports.push(report)
  recordLog(docId, '生成报告', `生成风险审核报告 ${report.report_no}`, '系统', '系统')
  persist()
  return report
}

// 风险规则配置（管理员，Spec 4.10）
export function updateRiskRule(ruleCode, patch) {
  const rule = state.riskRules.find((row) => row.code === ruleCode)
  if (!rule) return null
  Object.assign(rule, patch)
  recordLog(null, '规则配置', `更新风险规则 ${rule.code} ${rule.name}`)
  persist()
  return rule
}
