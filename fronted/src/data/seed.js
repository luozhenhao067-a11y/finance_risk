export const DOC_TYPES = ['费用报销', '差旅费报销', '采购付款', '合同付款', '借款单']

// 角色定义（Spec 1.3）
export const ROLES = [
  { code: 'APPLICANT', label: '申请人' },
  { code: 'DEPT_MANAGER', label: '部门负责人' },
  { code: 'FINANCE', label: '财务审核人' },
  { code: 'ADMIN', label: '系统管理员' }
]

// 审批流配置（Spec 5.4：基础链 + 金额条件加签）
export const FLOW_CONFIG = {
  baseNodes: ['申请人提交', '部门负责人审批', '财务审核', '审批完成'],
  extraNode: { threshold: 300000, node: '分管副总审批', assignee: '赵刚', insertAfter: '部门负责人审批' }
}

// 风险规则清单（Spec 5.5，R-01 ~ R-10）
export const RISK_RULES = [
  { code: 'R-01', name: '金额一致性', level: 'high', docTypes: '全部', enabled: true, params: '容差 ¥0.01' },
  { code: 'R-02', name: '明细合计校验', level: 'blocking', docTypes: '全部', enabled: true, params: '提交强校验' },
  { code: 'R-03', name: '合同与付款一致性', level: 'high', docTypes: '采购付款/合同付款', enabled: true, params: '付款比例偏差阈值 10%' },
  { code: 'R-04', name: '批量付款校验', level: 'high', docTypes: '采购付款（批量）', enabled: false, params: '收款方重复检测' },
  { code: 'R-05', name: '费用标准', level: 'mid', docTypes: '差旅费报销/费用报销', enabled: true, params: '按城市/职级/晚数' },
  { code: 'R-06', name: '市场价格偏离', level: 'mid', docTypes: '采购付款', enabled: true, params: '偏离阈值 10%' },
  { code: 'R-07', name: '消费异常', level: 'mid', docTypes: '差旅费报销/费用报销', enabled: false, params: '节假日/连号发票/单日多票' },
  { code: 'R-08', name: '供应商风险', level: 'mid', docTypes: '采购付款/合同付款', enabled: true, params: '成立年限 < 12 个月' },
  { code: 'R-09', name: '附件完整性', level: 'low', docTypes: '全部', enabled: true, params: '置信度阈值 85%' },
  { code: 'R-10', name: '重复票据', level: 'high', docTypes: '全部', enabled: true, params: '历史单据比对' }
]

// 费用类型字典（按单据类型可选集合，Spec 4.4）
export const EXPENSE_TYPES = {
  费用报销: ['办公费', '场地费', '设备采购', '其他'],
  差旅费报销: ['交通费', '住宿费', '餐饮费', '其他'],
  采购付款: ['设备采购', '合同款', '服务费', '其他'],
  合同付款: ['合同款', '服务费', '其他'],
  借款单: ['借款']
}

export const seedState = {
  schemaVersion: 2,
  auth: false,
  user: {
    id: 'u-wangfang',
    name: '王芳',
    role: '财务审核人',
    role_code: 'FINANCE',
    dept: '财务部',
    dept_id: 'dept-finance',
    avatar: '王'
  },
  users: [
    { id: 'u-zhangwei', name: '张伟', role: '申请人', role_code: 'APPLICANT', dept: '市场部', dept_id: 'dept-market', avatar: '张' },
    { id: 'u-lina', name: '李娜', role: '申请人', role_code: 'APPLICANT', dept: '采购部', dept_id: 'dept-purchase', avatar: '李' },
    { id: 'u-wangqiang', name: '王强', role: '申请人', role_code: 'APPLICANT', dept: '采购部', dept_id: 'dept-purchase', avatar: '王' },
    { id: 'u-chenchen', name: '陈晨', role: '申请人', role_code: 'APPLICANT', dept: '品牌部', dept_id: 'dept-brand', avatar: '陈' },
    { id: 'u-liuyang', name: '刘洋', role: '申请人', role_code: 'APPLICANT', dept: '销售部', dept_id: 'dept-sales', avatar: '刘' },
    { id: 'u-liming', name: '李明', role: '部门负责人', role_code: 'DEPT_MANAGER', dept: '采购部', dept_id: 'dept-purchase', avatar: '李' },
    { id: 'u-zhaogang', name: '赵刚', role: '部门负责人', role_code: 'DEPT_MANAGER', dept: '总经办', dept_id: 'dept-gm', avatar: '赵' },
    { id: 'u-wangfang', name: '王芳', role: '财务审核人', role_code: 'FINANCE', dept: '财务部', dept_id: 'dept-finance', avatar: '王' },
    { id: 'u-admin', name: '系统管理员', role: '系统管理员', role_code: 'ADMIN', dept: '信息部', dept_id: 'dept-it', avatar: '管' }
  ],
  depts: [
    { id: 'dept-market', name: '市场部' },
    { id: 'dept-purchase', name: '采购部' },
    { id: 'dept-brand', name: '品牌部' },
    { id: 'dept-sales', name: '销售部' },
    { id: 'dept-finance', name: '财务部' },
    { id: 'dept-gm', name: '总经办' },
    { id: 'dept-it', name: '信息部' }
  ],
  stats: {
    pendingApproval: 12,
    highRisk: 5,
    inApproval: 36,
    completedMonth: 128
  },
  riskDistribution: { high: 23, mid: 41, low: 67 },
  documents: [
    {
      id: 'd001',
      doc_no: 'FY20261021-001',
      doc_type: '差旅费报销',
      title: '10月上海出差差旅报销',
      applicant_id: 'u-zhangwei',
      applicant_name: '张伟',
      dept_id: 'dept-market',
      dept_name: '市场部',
      project: '华东区渠道大会',
      total_amount: 7000.5,
      status: 'pending_approval',
      version: 2,
      current_node: '财务审核',
      submit_time: '2026-10-21 10:32',
      create_time: '2026-10-21 10:20',
      risk_level: 'high',
      risk_count: 4,
      queue_time: '10:32'
    },
    {
      id: 'd014',
      doc_no: 'FY20261020-014',
      doc_type: '采购付款',
      title: '服务器采购付款',
      applicant_id: 'u-lina',
      applicant_name: '李娜',
      dept_id: 'dept-purchase',
      dept_name: '采购部',
      project: '信息化基础建设',
      total_amount: 86500,
      status: 'pending_approval',
      version: 1,
      current_node: '财务审核',
      submit_time: '2026-10-20 09:15',
      create_time: '2026-10-20 09:02',
      risk_level: 'mid',
      risk_count: 2,
      queue_time: '09:15'
    },
    {
      id: 'd009',
      doc_no: 'FY20261020-009',
      doc_type: '合同付款',
      title: '合同二期付款',
      applicant_id: 'u-wangqiang',
      applicant_name: '王强',
      dept_id: 'dept-purchase',
      dept_name: '采购部',
      project: '供应链系统升级',
      total_amount: 320000,
      status: 'pending_approval',
      version: 1,
      current_node: '部门负责人审批',
      submit_time: '2026-10-20 16:40',
      create_time: '2026-10-20 16:21',
      risk_level: 'high',
      risk_count: 3,
      queue_time: '昨天'
    },
    {
      id: 'd032',
      doc_no: 'FY20261019-032',
      doc_type: '费用报销',
      title: '9月市场活动费用报销',
      applicant_id: 'u-chenchen',
      applicant_name: '陈晨',
      dept_id: 'dept-brand',
      dept_name: '品牌部',
      project: '品牌发布会',
      total_amount: 3260.5,
      status: 'completed',
      version: 1,
      current_node: '审批完成',
      submit_time: '2026-10-19 11:08',
      create_time: '2026-10-19 10:45',
      risk_level: 'low',
      risk_count: 1,
      queue_time: '昨天'
    },
    {
      id: 'd025',
      doc_no: 'FY20261019-025',
      doc_type: '借款单',
      title: '出差借款申请',
      applicant_id: 'u-liuyang',
      applicant_name: '刘洋',
      dept_id: 'dept-sales',
      dept_name: '销售部',
      project: '华南客户拜访',
      total_amount: 20000,
      status: 'pending_approval',
      version: 1,
      current_node: '部门负责人审批',
      submit_time: '2026-10-19 14:20',
      create_time: '2026-10-19 14:02',
      risk_level: 'none',
      risk_count: 0,
      queue_time: '昨天'
    }
  ],
  details: [
    { id: 'dd001', doc_id: 'd001', expense_type: '交通费', expense_date: '2026-10-15', amount: 1280, invoice_no: 'INV-88910234', remark: '上海至北京高铁' },
    { id: 'dd002', doc_id: 'd001', expense_type: '住宿费', expense_date: '2026-10-16', amount: 4860, invoice_no: 'INV-88910451', remark: '北京酒店3晚' },
    { id: 'dd003', doc_id: 'd001', expense_type: '餐饮费', expense_date: '2026-10-17', amount: 860.5, invoice_no: 'INV-88910987', remark: '客户接待' },
    { id: 'dd004', doc_id: 'd014', expense_type: '设备采购', expense_date: '2026-10-18', amount: 86500, invoice_no: 'INV-PC-77120', remark: '双路服务器 2 台' },
    { id: 'dd005', doc_id: 'd009', expense_type: '合同款', expense_date: '2026-10-15', amount: 320000, invoice_no: 'HT-2026-0721', remark: '供应链系统二期合同款' },
    { id: 'dd006', doc_id: 'd025', expense_type: '借款', expense_date: '2026-10-19', amount: 20000, invoice_no: '—', remark: '出差备用金' },
    { id: 'dd007', doc_id: 'd032', expense_type: '场地费', expense_date: '2026-09-28', amount: 3260.5, invoice_no: 'INV-770123', remark: '品牌发布会场地' }
  ],
  attachments: [
    { id: 'at001', doc_id: 'd001', file_name: '高铁票.pdf', size_label: '1.2MB', mime: 'application/pdf', file_type: 'pdf', path: '/files/FY20261021-001/高铁票.pdf', uploaded_at: '2026-10-21 10:24', parse_status: 'parsed' },
    { id: 'at002', doc_id: 'd001', file_name: '发票.png', size_label: '860KB', mime: 'image/png', file_type: 'image', path: '/files/FY20261021-001/发票.png', uploaded_at: '2026-10-21 10:25', parse_status: 'parsed' },
    { id: 'at003', doc_id: 'd001', file_name: '行程单.jpg', size_label: '1.5MB', mime: 'image/jpeg', file_type: 'image', path: '/files/FY20261021-001/行程单.jpg', uploaded_at: '2026-10-21 10:26', parse_status: 'parsed' },
    { id: 'at004', doc_id: 'd014', file_name: '采购合同.pdf', size_label: '2.4MB', mime: 'application/pdf', file_type: 'pdf', path: '/files/FY20261020-014/采购合同.pdf', uploaded_at: '2026-10-20 09:06', parse_status: 'parsed' },
    { id: 'at005', doc_id: 'd014', file_name: '报价单.png', size_label: '680KB', mime: 'image/png', file_type: 'image', path: '/files/FY20261020-014/报价单.png', uploaded_at: '2026-10-20 09:07', parse_status: 'parsed' },
    { id: 'at006', doc_id: 'd009', file_name: '合同扫描件.pdf', size_label: '3.1MB', mime: 'application/pdf', file_type: 'pdf', path: '/files/FY20261020-009/合同扫描件.pdf', uploaded_at: '2026-10-20 16:28', parse_status: 'parsed' },
    { id: 'at007', doc_id: 'd025', file_name: '借款申请单.pdf', size_label: '380KB', mime: 'application/pdf', file_type: 'pdf', path: '/files/FY20261019-025/借款申请单.pdf', uploaded_at: '2026-10-19 14:08', parse_status: 'parsed' },
    { id: 'at008', doc_id: 'd032', file_name: '场地发票.pdf', size_label: '510KB', mime: 'application/pdf', file_type: 'pdf', path: '/files/FY20261019-032/场地发票.pdf', uploaded_at: '2026-10-19 10:52', parse_status: 'parsed' }
  ],
  snapshots: [
    { id: 'snap001', doc_id: 'd001', version: 2, created_at: '2026-10-21 10:32', immutable: true }
  ],
  approvalInstances: [
    { id: 'ai001', doc_id: 'd001', status: 'running', current_node: '财务审核' },
    { id: 'ai002', doc_id: 'd014', status: 'running', current_node: '财务审核' },
    { id: 'ai003', doc_id: 'd009', status: 'running', current_node: '部门负责人审批' },
    { id: 'ai004', doc_id: 'd025', status: 'running', current_node: '部门负责人审批' },
    { id: 'ai005', doc_id: 'd032', status: 'completed', current_node: '审批完成' }
  ],
  approvalTasks: [
    { id: 'task001', instance_id: 'ai001', doc_id: 'd001', node: '部门负责人审批', assignee: '李明', status: 'done', action: 'approved', finished_at: '2026-10-21 10:50' },
    { id: 'task002', instance_id: 'ai001', doc_id: 'd001', node: '财务审核', assignee: '王芳', status: 'pending', finished_at: null },
    { id: 'task003', instance_id: 'ai002', doc_id: 'd014', node: '财务审核', assignee: '王芳', status: 'pending', finished_at: null },
    { id: 'task004', instance_id: 'ai003', doc_id: 'd009', node: '部门负责人审批', assignee: '李明', status: 'pending', finished_at: null },
    { id: 'task005', instance_id: 'ai004', doc_id: 'd025', node: '部门负责人审批', assignee: '李明', status: 'pending', finished_at: null },
    { id: 'task006', instance_id: 'ai005', doc_id: 'd032', node: '财务审核', assignee: '王芳', status: 'done', action: 'approved', finished_at: '2026-10-19 15:30' }
  ],
  approvalOpinions: [
    { id: 'op001', doc_id: 'd001', task_id: 'task001', node: '申请人提交', user: '张伟', action: 'submit', opinion: '提交审批', created_at: '2026-10-21 10:32' },
    { id: 'op002', doc_id: 'd001', task_id: 'task001', node: '部门负责人审批', user: '李明', action: 'approve', opinion: '同意报销，请财务复核发票明细。', created_at: '2026-10-21 10:50' },
    { id: 'op003', doc_id: 'd014', task_id: 'task003', node: '申请人提交', user: '李娜', action: 'submit', opinion: '提交审批', created_at: '2026-10-20 09:15' },
    { id: 'op004', doc_id: 'd009', task_id: 'task004', node: '申请人提交', user: '王强', action: 'submit', opinion: '提交审批', created_at: '2026-10-20 16:40' },
    { id: 'op005', doc_id: 'd025', task_id: 'task005', node: '申请人提交', user: '刘洋', action: 'submit', opinion: '提交审批', created_at: '2026-10-19 14:20' },
    { id: 'op006', doc_id: 'd032', task_id: 'task006', node: '财务审核', user: '王芳', action: 'approve', opinion: '票据齐全，同意报销。', created_at: '2026-10-19 15:30' }
  ],
  riskAnalyses: [
    {
      id: 'ra001', doc_id: 'd001', doc_version: 2, status: 'completed', overall_level: 'high',
      high_count: 2, mid_count: 1, low_count: 1,
      recommendation: 'manual_review',
      recommendation_label: '人工复核',
      summary: '存在金额不一致与重复票据，请财务人工复核后决定通过或退回',
      trigger_type: 'auto', analyzed_at: '2026-10-21 10:33'
    },
    {
      id: 'ra002', doc_id: 'd014', doc_version: 1, status: 'completed', overall_level: 'mid',
      high_count: 0, mid_count: 2, low_count: 0,
      recommendation: 'supplement',
      recommendation_label: '补充材料',
      summary: '采购价格高于近期市场均价，建议补充供应商比价材料',
      trigger_type: 'auto', analyzed_at: '2026-10-20 09:16'
    },
    {
      id: 'ra003', doc_id: 'd009', doc_version: 1, status: 'completed', overall_level: 'high',
      high_count: 3, mid_count: 0, low_count: 0,
      recommendation: 'reject_suggest',
      recommendation_label: '建议驳回',
      summary: '付款金额、合同条款与审批权限均存在高风险，建议驳回并核验合同',
      trigger_type: 'auto', analyzed_at: '2026-10-20 16:41'
    },
    {
      id: 'ra004', doc_id: 'd025', doc_version: 1, status: 'completed', overall_level: 'none',
      high_count: 0, mid_count: 0, low_count: 0,
      recommendation: 'pass',
      recommendation_label: '建议通过',
      summary: '未发现明显风险，附件与金额校验通过',
      trigger_type: 'auto', analyzed_at: '2026-10-19 14:21'
    },
    {
      id: 'ra005', doc_id: 'd032', doc_version: 1, status: 'completed', overall_level: 'low',
      high_count: 0, mid_count: 0, low_count: 1,
      recommendation: 'manual_review',
      recommendation_label: '人工复核',
      summary: '发票信息存在轻微缺失，已由财务人工复核',
      trigger_type: 'auto', analyzed_at: '2026-10-19 11:09'
    }
  ],
  riskItems: [
    {
      id: 'ri001', doc_id: 'd001', rule_code: 'R-01', level: 'high', title: '金额不一致',
      basis: '报销单合计 ¥7,000.50 与发票解析合计 ¥6,980.50 不一致，差额 ¥20.00',
      evidence: '发票 INV-88910451 第 1 页 · 解析值 ¥4,860.00',
      suggestion: '核对明细金额并更正，或补充差额说明',
      page: 1, confidence: 98, status: 'open'
    },
    {
      id: 'ri002', doc_id: 'd001', rule_code: 'R-10', level: 'high', title: '重复票据',
      basis: '发票 INV-88910234 与 2026-05 已报销单据 FY20260512-008 重复',
      evidence: '重复检测命中率 96% · 历史单据附件对比',
      suggestion: '人工复核，如确认重复则退回申请人',
      page: 2, confidence: 96, status: 'open'
    },
    {
      id: 'ri003', doc_id: 'd001', rule_code: 'R-05', level: 'mid', title: '费用超标准',
      basis: '住宿费 ¥4,860.00 超出差旅标准（北京 上限 ¥800/晚 × 3 晚）',
      evidence: '住宿发票 3 晚 · 标准配置表 差旅-住宿',
      suggestion: '补充超标说明并加签，或调整金额',
      page: 1, confidence: 94, status: 'open'
    },
    {
      id: 'ri004', doc_id: 'd001', rule_code: 'R-09', level: 'low', title: '发票信息不完整',
      basis: '餐饮发票未识别出销售方税号',
      evidence: '附件第 3 页 · 解析置信度 78%',
      suggestion: '人工补充税号或重新上传清晰发票',
      page: 3, confidence: 78, status: 'open'
    },
    {
      id: 'ri005', doc_id: 'd014', rule_code: 'R-06', level: 'mid', title: '采购价格偏离市场',
      basis: '服务器单价 ¥43,250.00 高于近 3 个月市场均价约 12%',
      evidence: '报价单第 1 页 · 市场比价库',
      suggestion: '补充至少两家供应商比价材料',
      page: 1, confidence: 88, status: 'open'
    },
    {
      id: 'ri006', doc_id: 'd014', rule_code: 'R-08', level: 'mid', title: '供应商风险',
      basis: '供应商成立时间不足 12 个月，历史交易记录较少',
      evidence: '工商信息查询 · 供应商档案',
      suggestion: '核验供应商资质与履约能力',
      page: 1, confidence: 84, status: 'open'
    },
    {
      id: 'ri007', doc_id: 'd009', rule_code: 'R-03', level: 'high', title: '合同与付款不一致',
      basis: '付款金额 ¥320,000.00 与合同本期应付金额 ¥280,000.00 不一致',
      evidence: '合同扫描件第 4 页 · 付款条款',
      suggestion: '核对合同付款节点与金额',
      page: 4, confidence: 97, status: 'open'
    },
    {
      id: 'ri008', doc_id: 'd009', rule_code: 'R-03', level: 'high', title: '付款超合同进度',
      basis: '本期付款比例 40% 高于合同约定 30%',
      evidence: '合同扫描件第 5 页 · 验收与付款',
      suggestion: '补充验收单并重新确认付款比例',
      page: 5, confidence: 93, status: 'open'
    },
    {
      id: 'ri009', doc_id: 'd009', rule_code: 'R-EXT', level: 'high', title: '审批权限缺失',
      basis: '单笔付款超过 ¥300,000.00，缺少分管副总审批节点',
      evidence: '审批规则配置 · 大额付款权限',
      suggestion: '增加分管副总审批节点后重新提交',
      page: 1, confidence: 99, status: 'open'
    },
    {
      id: 'ri010', doc_id: 'd032', rule_code: 'R-09', level: 'low', title: '发票信息不完整',
      basis: '场地发票备注栏未填写活动名称',
      evidence: '场地发票第 1 页 · 解析置信度 80%',
      suggestion: '人工补充活动名称说明',
      page: 1, confidence: 80, status: 'handled', handled_by: '王芳', handled_at: '2026-10-19 15:30', handle_opinion: '已与申请人确认，活动名称为品牌发布会，风险排除。'
    }
  ],
  riskEvidences: [
    { id: 're001', risk_item_id: 'ri001', doc_id: 'd001', attachment_id: 'at002', page: 1, snippet: '价税合计 ¥4,860.00', confidence: 98 },
    { id: 're002', risk_item_id: 'ri002', doc_id: 'd001', attachment_id: 'at002', page: 2, snippet: 'INV-88910234', confidence: 96 },
    { id: 're003', risk_item_id: 'ri003', doc_id: 'd001', attachment_id: 'at003', page: 1, snippet: '住宿 3 晚', confidence: 94 },
    { id: 're004', risk_item_id: 'ri004', doc_id: 'd001', attachment_id: 'at003', page: 3, snippet: '销售方税号未识别', confidence: 78 }
  ],
  parseResults: [
    {
      id: 'pr001', doc_id: 'd001', attachment_id: 'at002', file_name: '发票.png', page: 1, confidence: 98,
      fields: [
        { label: '发票号码', value: 'INV-88910451', confidence: 98 },
        { label: '开票日期', value: '2026-10-15', confidence: 96 },
        { label: '销售方', value: '北京朝阳酒店管理有限公司', confidence: 94 },
        { label: '金额合计', value: '¥4,860.00', confidence: 99 },
        { label: '税额', value: '¥275.09', confidence: 86 }
      ]
    },
    {
      id: 'pr002', doc_id: 'd014', attachment_id: 'at004', file_name: '采购合同.pdf', page: 1, confidence: 97,
      fields: [
        { label: '合同编号', value: 'HT-2026-0912', confidence: 98 },
        { label: '供应商', value: '北京云启科技有限公司', confidence: 96 },
        { label: '合同金额', value: '¥86,500.00', confidence: 97 }
      ]
    },
    {
      id: 'pr003', doc_id: 'd009', attachment_id: 'at006', file_name: '合同扫描件.pdf', page: 4, confidence: 95,
      fields: [
        { label: '合同编号', value: 'HT-2026-0721', confidence: 98 },
        { label: '本期应付', value: '¥280,000.00', confidence: 95 },
        { label: '付款比例', value: '30%', confidence: 94 }
      ]
    },
    {
      id: 'pr004', doc_id: 'd025', attachment_id: 'at007', file_name: '借款申请单.pdf', page: 1, confidence: 96,
      fields: [
        { label: '借款金额', value: '¥20,000.00', confidence: 97 },
        { label: '借款用途', value: '出差备用金', confidence: 96 }
      ]
    }
  ],
  operationLogs: [
    { id: 'log001', doc_id: 'd001', action: '创建单据', operator: '张伟', role: '申请人', detail: '创建草稿单据，版本 v1', created_at: '2026-10-21 10:20' },
    { id: 'log002', doc_id: 'd001', action: '上传附件', operator: '张伟', role: '申请人', detail: '上传 高铁票.pdf / 发票.png / 行程单.jpg', created_at: '2026-10-21 10:26' },
    { id: 'log003', doc_id: 'd001', action: '提交审批', operator: '张伟', role: '申请人', detail: '生成快照 v2，提交至部门负责人审批', created_at: '2026-10-21 10:32' },
    { id: 'log004', doc_id: 'd001', action: '风险分析完成', operator: '系统', role: '系统', detail: '识别 4 项风险，整体等级：高风险', created_at: '2026-10-21 10:33' },
    { id: 'log005', doc_id: 'd001', action: '审批通过', operator: '李明', role: '审批人', detail: '部门负责人审批通过，流转至财务审核', created_at: '2026-10-21 10:50' },
    { id: 'log006', doc_id: 'd001', action: '查看风险报告', operator: '王芳', role: '财务', detail: '查看风险审核报告 RPT-20261021-0087', created_at: '2026-10-21 11:02' },
    { id: 'log007', doc_id: 'd014', action: '提交审批', operator: '李娜', role: '申请人', detail: '提交至财务审核', created_at: '2026-10-20 09:15' },
    { id: 'log008', doc_id: 'd014', action: '风险分析完成', operator: '系统', role: '系统', detail: '识别 2 项风险，整体等级：中风险', created_at: '2026-10-20 09:16' },
    { id: 'log009', doc_id: 'd009', action: '提交审批', operator: '王强', role: '申请人', detail: '提交至部门负责人审批', created_at: '2026-10-20 16:40' },
    { id: 'log010', doc_id: 'd009', action: '风险分析完成', operator: '系统', role: '系统', detail: '识别 3 项风险，整体等级：高风险', created_at: '2026-10-20 16:41' },
    { id: 'log011', doc_id: 'd025', action: '提交审批', operator: '刘洋', role: '申请人', detail: '提交至部门负责人审批', created_at: '2026-10-19 14:20' },
    { id: 'log012', doc_id: 'd032', action: '审批完成', operator: '王芳', role: '财务', detail: '财务审核通过，单据完成', created_at: '2026-10-19 15:30' }
  ],
  reports: [
    {
      id: 'rpt001',
      doc_id: 'd001',
      report_no: 'RPT-20261021-0087',
      generated_at: '2026-10-21 11:02',
      overall_level: 'high',
      overall_text: '整体风险：高风险（4 项：高 2 · 中 1 · 低 1）',
      recommendation_label: '人工复核',
      summary: '存在金额不一致与重复票据，请财务人工复核后决定通过或退回。',
      amount_checks: [
        { name: '交通费', doc_amount: 1280, parsed_amount: 1280, diff: 0, conclusion: '一致' },
        { name: '住宿费', doc_amount: 4860, parsed_amount: 4860, diff: 0, conclusion: '一致' },
        { name: '餐饮费', doc_amount: 860.5, parsed_amount: 840.5, diff: 20, conclusion: '不一致' },
        { name: '合计', doc_amount: 7000.5, parsed_amount: 6980.5, diff: 20, conclusion: '需复核', is_total: true }
      ],
      vendor: {
        name: '北京朝阳酒店管理有限公司',
        score: 62,
        level: 'mid',
        note: '近 12 个月价格波动 18%，高于行业均值，建议关注定价合理性'
      },
      reviews: [
        {
          name: '王芳',
          role: '财务',
          avatar: '王',
          content: '金额差额已与申请人电话确认，属录入错误，退回修改后重新提交。',
          created_at: '2026-10-21 11:02'
        }
      ]
    }
  ],
  todos: [
    { id: 'td001', doc_id: 'd001', level: 'high', text: 'FY20261021-001 差旅报销待审批' },
    { id: 'td002', doc_id: 'd014', level: 'mid', text: 'FY20261020-014 采购付款超预算预警' },
    { id: 'td003', doc_id: 'd025', level: 'none', text: 'FY20261019-025 借款单材料待补充' }
  ],
  notifications: [
    { id: 'n001', doc_id: 'd001', title: 'FY20261021-001 风险分析完成', time: '10 分钟前', read: false },
    { id: 'n002', doc_id: 'd014', title: 'FY20261020-014 已进入财务审核', time: '1 小时前', read: false },
    { id: 'n003', doc_id: 'd009', title: 'FY20261020-009 存在 3 项高风险', time: '昨天', read: true }
  ],
  riskRules: RISK_RULES
}
