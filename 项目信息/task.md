# 财务单据智能风险审核系统 · 开发任务清单（task.md）

> 排期原则：纵向切片（单条业务线跑通）；每任务 1–2 小时；`[核心卡点]` = 影响核心流程的卡点任务。
> 前端基于现有 `fronted` 工程改造（Vue 3 + Vite + Element Plus），Phase 6 为页面对接而非从零初始化。

## Phase 1：基建与认证

- [ ] 1.1 后端工程初始化
  - 文件：`pom.xml`、`application.yml`、`FinanceRiskAuditApplication.java`、包结构 `controller/service/mapper/entity/config`
  - 内容：Spring Boot 3.x + Java 17；MyBatis-Plus / MySQL / Redis / RocketMQ / MinIO 依赖与连接配置
  - 依赖：无

- [ ] 1.2 统一响应体与错误码
  - 文件：`Result.java`、`ErrorCode.java`、`TraceIdFilter.java`
  - 内容：`Result<T>` 信封 `{code,message,data,trace_id}`；错误码分段 400xx~500xx；trace_id 贯穿请求
  - 依赖：1.1 完成

- [ ] 1.3 全局异常处理
  - 文件：`BizException.java`、`GlobalExceptionHandler.java`
  - 内容：业务异常统一抛 BizException；参数校验失败逐字段返回 message
  - 依赖：1.2 完成

- [ ] 1.4 MyBatis-Plus 基础配置
  - 文件：`MybatisPlusConfig.java`、`MetaObjectHandler.java`
  - 内容：分页插件、逻辑删除（delete_flag）、create_time/update_time 自动填充
  - 依赖：1.1 完成

- [x] 1.5 数据库 DDL 建表脚本
  - 文件：`建表/01_建表.sql`、`建表/02_清空表.sql`、`建表/03_插入数据.sql`（已从真库生成并回归验证，说明见 `建表/04_测试数据说明.md`）
  - 内容：全量表 23 张（user / role / permission / user_role / role_permission / document / document_item / attachment / attachment_parse_result / document_snapshot / risk_rule / risk_analysis / risk_item / risk_evidence / approval_flow / approval_task / approval_opinion / audit_log / notification / report / expense_standard / vendor / dict）；doc_no 唯一索引；seed：用户 11 个（admin/系统管理员、张伟/财务经理、李娜+王芳/财务专员、刘洋+陈静+高翔/部门经理、赵磊/工程师、孙丽/市场专员、周强/销售经理、吴敏/审计员，密码统一 Root@123456 BCrypt）、角色 6 个、权限、审批流固定三节点（部门经理审批→财务专员审核→财务经理复核）、R-01~R-10 + R-EXT 规则行、字典 21 条、费用标准 9 条、供应商 5 条
  - 依赖：1.1 完成

- [ ] 1.6 实体与 Mapper
  - 文件：`entity/` 全部实体类、`mapper/` 全部 Mapper 接口
  - 依赖：1.5 完成

- [ ] 1.7 JWT 工具与 Spring Security
  - 文件：`JwtUtil.java`、`SecurityConfig.java`、`JwtAuthenticationFilter.java`、`LoginAttemptService.java`
  - 内容：JWT 签发/校验（有效期 2h）；过滤链放行 `/auth/login`；密码 BCrypt；Redis 记失败次数，连续 5 次锁定 15 分钟（40103）
  - 依赖：1.2、1.6 完成

- [ ] 1.8 认证接口
  - 文件：`AuthController.java`、`AuthService.java`、`LoginRequest/LoginResponse.java`
  - 内容：POST `/api/v1/auth/login`（返回 token+user）、POST `/auth/logout`、GET `/auth/me`（用户信息+权限点）
  - 依赖：1.7 完成

- [ ] 1.9 权限上下文与数据权限
  - 文件：`SecurityUtil.java`、`DataScopeUtil.java`、`@RequireRole` 注解
  - 内容：SecurityContext 取当前用户；数据权限三层（本人/本部门/全部）生成查询过滤条件；RBAC 服务端校验
  - 依赖：1.8 完成

- [ ] 1.10 中间件本地环境
  - 文件：`docker-compose.yml`
  - 内容：MySQL 8 / Redis / RocketMQ（namesrv+broker）/ MinIO
  - 依赖：无

## Phase 2：单据 CRUD 跑通

- [ ] 2.1 单据编号生成 [核心卡点]
  - 文件：`DocNoService.java`
  - 内容：`FYyyyyMMdd-001` 当日 3 位流水；Redis 计数 + 唯一索引防并发重复；前端不传 doc_no
  - 依赖：1.6 完成

- [ ] 2.2 创建单据 POST `/documents`
  - 文件：`DocumentController.createDocument`、`DocumentService.createDocument`、`DocumentCreateRequest.java`
  - 内容：含明细批量插入；total_amount 服务端计算；`submit=false` 保存草稿分支
  - 依赖：2.1 完成

- [ ] 2.3 单据列表 GET `/documents`
  - 文件：`DocumentController.listDocuments`、`DocumentService.pageQuery`
  - 内容：分页/筛选/排序（sort_by 白名单）；数据权限三层过滤
  - 依赖：2.2、1.9 完成

- [ ] 2.4 单据详情聚合 GET `/documents/{id}`
  - 文件：`DocumentController.getDocument`、`DocumentService.getDetail`、`DocumentDetailVO.java`
  - 内容：主表+明细+附件+审批+风险+日志聚合（风险/审批字段暂空，随 Phase 4/5 填充）；返回 `permissions` 按钮权限（按权限矩阵+单据状态计算）
  - 依赖：2.3 完成

- [ ] 2.5 编辑单据 PUT `/documents/{id}`
  - 文件：`DocumentController.updateDocument`、`DocumentService.updateDocument`
  - 内容：仅 draft/returned 且本人；doc_type 一经提交不可变；明细全量替换
  - 依赖：2.4 完成

- [ ] 2.6 删除单据 DELETE `/documents/{id}`
  - 文件：`DocumentController.deleteDocument`、`DocumentService.deleteDocument`
  - 内容：仅 draft 且本人；逻辑删除
  - 依赖：2.4 完成

- [ ] 2.7 明细增量接口（可选）
  - 文件：`DocumentController.addDetail/updateDetail/deleteDetail`
  - 内容：POST/PUT/DELETE `/documents/{id}/details`；删除后剩余明细不得为空（40001）
  - 依赖：2.5 完成

- [ ] 2.8 附件上传 POST `/documents/{id}/attachments`
  - 文件：`AttachmentController.upload`、`AttachmentService.java`、`MinioUtil.java`
  - 内容：multipart 多文件；类型白名单 pdf/png/jpg、单文件 ≤20MB；对象键 `{doc_no}/v{version}/{uuid}_{file_name}`；落库 parse_status=parsing（解析任务触发依赖 3.7，先留钩子）
  - 依赖：2.2、1.10 完成

- [ ] 2.9 附件列表/下载/预览/删除
  - 文件：`AttachmentController.list/download/preview/delete`
  - 内容：下载/预览鉴权 + 5 分钟签名 URL；删除仅 draft/returned 且本人
  - 依赖：2.8 完成

## Phase 3：核心状态机与异步链路

- [ ] 3.1 状态机服务 [核心卡点]
  - 文件：`DocumentStateMachine.java`
  - 内容：8 状态迁移矩阵（design §2.2）；唯一允许修改 document.status 的入口；非法迁移抛 40901
  - 依赖：1.6 完成

- [ ] 3.2 提交强校验 [核心卡点]
  - 文件：`SubmitValidator.java`
  - 内容：必填 / 明细 ≥1 / 金额一致（容差 ¥0.01，R-02 阻塞性）/ 发票号格式 / 必需附件（报销类发票、采购合同付款类合同）；失败逐字段 message 返回 40001，单据保持 draft
  - 依赖：2.5、2.8 完成

- [ ] 3.3 快照服务 [核心卡点]
  - 文件：`SnapshotService.java`、`DocumentSnapshotMapper`
  - 内容：事务内生成 payload 全量 JSON（document+details+attachments 元数据）；只读不可变，无 UPDATE 接口；按 version 隔离保留历史
  - 依赖：2.6 完成

- [ ] 3.4 审批流构建与首任务 [核心卡点]
  - 文件：`ApprovalFlowBuilder.java`
  - 内容：按模板生成审批链（部门负责人审批→财务审核；total_amount ≥300000 条件加签分管副总）；创建 approval_instance + 首 approval_task（assignee 按部门负责人路由）
  - 依赖：1.6 完成

- [ ] 3.5 提交接口 POST `/documents/{id}/submit` [核心卡点]
  - 文件：`DocumentController.submit`、`DocumentService.submit`
  - 内容：校验 → 状态机 draft→submitted → 事务内（快照+审批实例+首任务）→ 事务提交后发 MQ；任一步失败整体回滚
  - 依赖：3.1、3.2、3.3、3.4、3.6 完成

- [ ] 3.6 MQ 生产者与事件发送 [核心卡点]
  - 文件：`MqProducer.java`、`DocumentSubmittedEvent.java`、topic 常量
  - 内容：事务提交后发事件（TransactionSynchronization afterCommit 或本地事务表）；RocketMQ 配置
  - 依赖：3.1、1.10 完成

- [ ] 3.7 解析任务消费者（Mock 解析） [核心卡点]
  - 文件：`ParseTaskConsumer.java`
  - 内容：消费 DocumentSubmittedEvent → Mock 解析 → 写 attachment_parse_result → 发解析完成事件；失败重试 3 次；按消息唯一键幂等去重
  - 依赖：3.6 完成

- [ ] 3.8 分析任务消费者与兜底流转 [核心卡点]
  - 文件：`AnalysisTaskConsumer.java`
  - 内容：消费解析完成事件 → 执行分析（Phase 5 前为 Mock 空结果）→ 状态机 analyzing→pending_approval；重试 3 次仍失败标注 analysis_failed 仍进 pending_approval；死信队列告警
  - 依赖：3.7 完成

- [ ] 3.9 纵向验收：提交全链路
  - 文件：`db/sample-data.sql`、Postman 集合或 `DocumentSubmitFlowTest.java`
  - 内容：端到端验证 draft→submitted→analyzing→pending_approval，含快照/实例/首任务落库断言
  - 依赖：3.8 完成

## Phase 4：审批模块与并发控制

- [ ] 4.1 待办/已办接口
  - 文件：`ApprovalController.todo/done`、`ApprovalService.todoList/doneList`
  - 内容：GET `/approvals/todo`（assignee=当前用户、task=pending、doc=pending_approval）；GET `/approvals/done`（已处理任务分页）
  - 依赖：3.8 完成

- [ ] 4.2 乐观锁防并发 [核心卡点]
  - 文件：`DocumentMapper` 版本比对 UPDATE、`OptimisticLockHelper.java`
  - 内容：审批/撤回/重提携带 document.version 做 `WHERE version=?` 条件更新；冲突返回 40903 并携带最新 version；幂等键 = taskId+单据审批版本
  - 依赖：4.1 完成

- [ ] 4.3 审批操作接口 POST `/documents/{id}/approve` [核心卡点]
  - 文件：`ApprovalController.approve`、`ApprovalService.approve/returnDoc/rejectDoc`
  - 内容：action=approve/return/reject；服务端三条件校验（当前用户=assignee、task=pending、doc=pending_approval）；非最后节点→当前任务 done+生成下一节点任务；最后节点→approved+实例 completed（自动生成报告钩子，依赖 5.15 接入）；return/reject 意见必填+未完成任务 cancelled+实例 returned/rejected；重复操作 40902
  - 依赖：4.1、4.2 完成

- [ ] 4.4 审批流转详情 GET `/documents/{id}/approval-flow`
  - 文件：`ApprovalController.flow`、`ApprovalFlowService.java`
  - 内容：chain 节点状态（done/current/pending）+ 意见时间线（按 created_at 升序）
  - 依赖：4.3 完成

- [ ] 4.5 撤回接口 POST `/documents/{id}/withdraw`
  - 文件：`DocumentController.withdraw`、`DocumentService.withdraw`
  - 内容：仅申请人、pending_approval；当前任务 cancelled、实例 returned；意见追加 action=withdraw；携带 version 乐观锁
  - 依赖：4.2、3.8 完成

- [ ] 4.6 退回重提 POST `/documents/{id}/resubmit` [核心卡点]
  - 文件：`DocumentController.resubmit`、`DocumentService.resubmit`
  - 内容：returned→submitted；version+1；新快照；重建审批实例；全量重分析（trigger_type=resubmit）；意见追加 action=resubmit
  - 依赖：4.5、3.3、3.5 完成

- [ ] 4.7 确认完成与恢复接口
  - 文件：`DocumentController.complete/restore`
  - 内容：POST `/complete`（approved→completed，财务/管理员）；POST `/restore`（rejected→draft，仅管理员，原因必填写 operation_log）
  - 依赖：4.3 完成

- [ ] 4.8 工作台聚合与通知接口
  - 文件：`DashboardController.stats`、`NotificationController.java`
  - 内容：GET `/dashboard/stats`（KPI 四卡/风险分布/待办/通知，按数据权限过滤）；GET `/notifications`、PUT `/notifications/read-all`；分析完成写通知（依赖 5.6 后接入）
  - 依赖：4.1 完成

## Phase 5：解析与风控引擎

- [ ] 5.1 解析器接口与 Mock 实现
  - 文件：`ParseEngine.java`（接口）、`MockParseEngine.java`、字段模板配置
  - 内容：按 doc_type 字段模板抽取（发票号码/开票日期/销售方/金额合计/税额/合同编号等）；替换 3.7 消费者中的 Mock 逻辑
  - 依赖：3.7 完成

- [ ] 5.2 解析结果查询 GET `/attachments/{id}/parse-result`
  - 文件：`AttachmentController.parseResult`
  - 内容：返回 fields/raw_text/page/confidence
  - 依赖：5.1 完成

- [ ] 5.3 规则引擎框架 [核心卡点]
  - 文件：`RiskRuleEngine.java`、`RuleExecutor.java`（接口）、`RuleRegistry.java`
  - 内容：规则注册式执行（新增规则不改主流程）；整体等级=max(风险项等级)；处理建议映射（high→manual_review 等，可配置覆盖）；risk_analysis/risk_item/risk_evidence 落库
  - 依赖：5.1 完成

- [ ] 5.4 规则批次 1：R-01 金额一致性、R-09 附件完整性、R-10 重复票据
  - 文件：`AmountConsistencyRule.java`、`AttachmentCompletenessRule.java`、`DuplicateInvoiceRule.java`
  - 内容：R-01 单据 vs 明细 vs 发票解析（容差 ¥0.01）；R-09 必需附件/要素齐全/置信度阈值 85；R-10 发票号历史比对
  - 依赖：5.3 完成

- [ ] 5.5 规则批次 2：R-05 费用标准、R-03 合同与付款一致性
  - 文件：`ExpenseStandardRule.java`、`ContractPaymentRule.java`
  - 内容：R-05 住宿/交通/餐饮 vs 标准配置（城市/职级/晚数）；R-03 付款金额 vs 合同应付金额/付款节点
  - 依赖：5.4 完成

- [ ] 5.6 分析消费者接入规则引擎
  - 文件：`AnalysisTaskConsumer.java`（改造）、`RiskAnalysisService.java`
  - 内容：真实规则执行替换 Mock；写 risk_analysis（doc_version 隔离）+risk_item+risk_evidence；回写 document 冗余 risk_level/risk_count；失败重试 3 次+analysis_failed 兜底（仍进 pending_approval）；完成写通知
  - 依赖：5.3、3.8 完成

- [ ] 5.7 风险分析查询 GET `/documents/{id}/risk-analysis`
  - 文件：`RiskAnalysisController.getAnalysis`、`RiskAnalysisService.getLatest`
  - 内容：按 doc_version 取最新；返回 analysis+items（含 evidences）+parse_results；null=尚未分析完成
  - 依赖：5.6 完成

- [ ] 5.8 手动重新分析 POST `/documents/{id}/risk-analysis/rerun`
  - 文件：`RiskAnalysisController.rerun`
  - 内容：财务/管理员；trigger_type=manual、triggered_by 落库；分析进行中拒绝（40901）
  - 依赖：5.7 完成

- [ ] 5.9 风险项全局查询与汇总
  - 文件：`RiskItemController.list/summary`
  - 内容：GET `/risk-items`（筛选/分页/数据权限）；GET `/risk-items/summary`（各级统计+open 规则 TOP）
  - 依赖：5.7 完成

- [ ] 5.10 风险处理 PUT `/risk-items/{itemId}/handle`
  - 文件：`RiskItemController.handle`、`RiskItemService.handle`
  - 内容：handled/dismissed；意见必填；handled_by/handled_at 落库；非 open 不可处理（40901）；处理记录不可删除
  - 依赖：5.7 完成

- [ ] 5.11 高风险审批二次确认
  - 文件：`DocumentDetailVO.permissions`（增 has_open_high 标记）、`ApprovalService`（确认内容写入 opinion+日志）
  - 内容：审批通过时存在 open 的 high 风险项：前端强提示，确认行为留痕
  - 依赖：4.3、5.7 完成

- [ ] 5.12 规则批次 3（P1 可选）：R-04/R-06/R-07/R-08
  - 文件：`BatchPaymentRule.java`、`MarketPriceRule.java`、`ConsumptionAnomalyRule.java`、`VendorRiskRule.java`
  - 依赖：5.5 完成

- [ ] 5.13 操作日志切面
  - 文件：`OperationLogAspect.java`、`@OperationLog` 注解
  - 内容：AOP 记录 action/操作人/角色/IP/UA/trace_id；append-only 无修改删除接口；覆盖动作清单（创建单据/上传附件/提交审批/审批通过/退回/驳回/撤回/重新提交/恢复/风险处理/生成报告等）
  - 依赖：1.3、1.6 完成

- [ ] 5.14 审计日志查询接口
  - 文件：`OperationLogController.list/export`、`DocumentController.logs`
  - 内容：GET `/logs`（财务/管理员，筛选分页）、GET `/logs/export`、GET `/documents/{id}/logs`
  - 依赖：5.13 完成

- [ ] 5.15 报告生成服务
  - 文件：`ReportService.java`、`ReportController.generate`
  - 内容：POST `/documents/{id}/report`；8 部分内容组装（单据摘要/整体风险/金额核对表/风险项/证据/供应商风险/处理建议/人工复核意见）；幂等（已存在直接返回）；approved/completed 后自动生成一次；报告编号 RPT-yyyyMMdd-xxxx
  - 依赖：5.7、4.3 完成

- [ ] 5.16 报告查询与导出
  - 文件：`ReportController.list/byDoc/export/exportSummary`
  - 内容：GET `/reports`、`/reports/by-doc/{docId}`、`/reports/{id}/export?format=pdf|excel`（导出文件落库 export_file_path）、`/reports/export-summary`
  - 依赖：5.15 完成

- [ ] 5.17 系统管理：用户/角色/部门
  - 文件：`AdminController.userCrud/roleCrud/deptCrud`、`AdminUserService.java`
  - 内容：GET/POST/PUT/DELETE `/admin/users`、`/admin/roles`、`/admin/depts`（部门树、负责人指定）；仅 ADMIN
  - 依赖：1.9 完成

- [ ] 5.18 系统管理：审批流/风险规则/费用标准/供应商/字典
  - 文件：`AdminController.flowCrud/riskRuleCrud/standardCrud/vendorCrud/dictCrud`
  - 内容：`/admin/approval-flows`（模板+加签规则）、`/admin/risk-rules`（启用/停用/参数 patch）、`/admin/standards`、`/admin/vendors`、`/admin/dicts`；变更写审计日志
  - 依赖：5.17 完成

## Phase 6：前端联调与页面渲染

- [ ] 6.1 Axios 封装
  - 文件：`fronted/src/api/client.js`
  - 内容：baseURL `VITE_API_BASE || '/api/v1'`；Bearer 注入（localStorage['finance-risk-audit-token']）；信封解包（code===0 返 data）；401 统一跳登录；40903 统一提示刷新
  - 依赖：1.8 完成

- [ ] 6.2 API 层定义
  - 文件：`fronted/src/api/index.js`（按模块拆分 auth/documents/attachments/approvals/risks/reports/logs/admin）
  - 内容：函数签名与契约第 3 章接口一一对应；视图层零改动可切换 mock
  - 依赖：6.1 完成

- [ ] 6.3 Pinia auth store 与路由守卫
  - 文件：`fronted/src/stores/auth.js`、`fronted/src/router/index.js`
  - 内容：登录/登出/me；token 持久化；未登录跳 /login、带 redirect 回跳；替换 appStore 的 localStorage 单文件状态
  - 依赖：6.2 完成

- [ ] 6.4 LoginView 对接
  - 文件：`fronted/src/views/LoginView.vue`
  - 内容：登录表单/错误提示（40102/40103）/记住用户名；登录成功跳工作台
  - 依赖：6.3 完成

- [ ] 6.5 DashboardView 对接
  - 文件：`fronted/src/views/DashboardView.vue`
  - 内容：KPI 四卡/风险分布环形图/我的待办/通知列表+一键已读；数据来自 `/dashboard/stats`
  - 依赖：6.2、4.8 完成

- [ ] 6.6 DocumentsView 对接
  - 文件：`fronted/src/views/DocumentsView.vue`
  - 内容：筛选/分页/排序走后端；行操作按钮按权限显示（查看/编辑/撤回/重新提交）
  - 依赖：6.2、2.3 完成

- [ ] 6.7 DocumentNewView 对接
  - 文件：`fronted/src/views/DocumentNewView.vue`
  - 内容：新建/编辑表单；明细合计实时联动（仅展示，后端强校验）；附件上传；保存草稿/直接提交；逐字段错误标红
  - 依赖：2.2、2.5、2.8 完成

- [ ] 6.8 DocumentDetailView 6 Tab 对接
  - 文件：`fronted/src/views/DocumentDetailView.vue`
  - 内容：基本信息/明细/附件与解析/风险分析/审批流转/审计日志 6 Tab；操作按钮消费 permissions；高风险提示条；提交后轮询状态流转（2~3s）
  - 依赖：2.4、4.4、5.7、5.14 完成

- [ ] 6.9 ApprovalsView 对接
  - 文件：`fronted/src/views/ApprovalsView.vue`
  - 内容：待办队列+已办；通过/退回/驳回+意见必填；40903 提示刷新重试；open 高风险项通过前二次确认
  - 依赖：4.3、5.11 完成

- [ ] 6.10 RisksView 对接
  - 文件：`fronted/src/views/RisksView.vue`
  - 内容：风险列表/筛选/汇总统计；风险处理（handled/dismissed+意见）
  - 依赖：5.9、5.10 完成

- [ ] 6.11 ReportCenterView + ReportView 对接
  - 文件：`fronted/src/views/ReportCenterView.vue`、`fronted/src/views/ReportView.vue`
  - 内容：报告列表/生成/详情 8 部分/PDF/Excel 导出下载
  - 依赖：5.15、5.16 完成

- [ ] 6.12 AuditLogsView 对接
  - 文件：`fronted/src/views/AuditLogsView.vue`
  - 内容：日志筛选分页列表；只读无操作入口
  - 依赖：5.14 完成

- [ ] 6.13 AdminView 对接
  - 文件：`fronted/src/views/AdminView.vue`
  - 内容：用户/部门管理、风险规则开关与参数、审批流配置等 Tab
  - 依赖：5.17、5.18 完成

- [ ] 6.14 关闭 mock 联调与端到端验收
  - 文件：`fronted/.env`（VITE_API_BASE）、验收用例
  - 内容：切换真实后端；关闭 MSW/mock；跑通示例数据 8 步验收链路（创建→提交→分析→审批→通过→报告→完成→日志可查）
  - 依赖：6.3~6.13 全部完成
