# 财务单据智能风险审核系统 · 开发指导文档（design.md）

> 用途：Vibe Coding 系统级 System Prompt。只含技术约束与架构要点，业务背景见 Spec。
> 权威来源：`项目信息/财务单据智能风险审核系统Spec.md`、`财务单据智能风险审核系统-接口契约.md`。冲突时以本文件约束为准。

---

## 1. 技术栈与分层规范

### 1.1 技术栈

| 端 | 选型 |
| --- | --- |
| 前端 | Vue 3.5（Composition API）+ Vite 6 + Element Plus + Pinia + Vue Router 4 + Axios + ECharts 5 |
| 后端 | Java 17 + Spring Boot 3.x + Spring Security（JWT + RBAC）+ MyBatis-Plus + MySQL 8 |
| 中间件 | Redis（会话/缓存）、RocketMQ（异步任务）、MinIO（文件存储） |
| 智能分析 | 附件解析（OCR + 字段结构化抽取）+ 风险规则引擎（10 类规则可配置，LLM 辅助可选） |

### 1.2 分层职责（强制）

三层核心：**Controller → Service → Mapper**，另加横切层：

| 层 | 职责 | 禁止 |
| --- | --- | --- |
| Controller | 参数绑定与校验、调用 Service、包装 `Result` | **禁止写业务逻辑**：不得出现状态判断、金额计算、数据组装、直接调 Mapper |
| Service | 业务逻辑唯一归属，事务边界在此（`@Transactional`），调用状态机服务、发 MQ 事件 | 禁止直接操作 HTTP/JSON 细节 |
| Mapper | 单表 CRUD（MyBatis-Plus），复杂查询写 XML | 禁止跨表业务拼装（放 Service） |
| 状态机服务 | 唯一允许修改 `document.status` 的地方，校验合法迁移 | 任何层绕过它直接改 status |
| 异步任务层 | RocketMQ 消费者：附件解析、风险分析 | 业务代码不得同步调用解析/分析 |
| 安全层 | Spring Security 过滤器：JWT、RBAC、数据权限（本人/本部门/全部三层） | 权限只在前端控制 |

**铁律：**
- Controller 一个方法 = 取参 → 调一个 Service 方法 → 返回。多一步就是业务逻辑越界。
- 事务边界只在 Service；MQ 发送在事务提交后（本地事务表或 afterCommit），不在事务内发。
- 领域事件（提交、分析完成、审批流转）走 MQ 解耦，禁止 Service 间同步直连。
- 服务端强制校验一切权限与状态，前端校验仅体验。

---

## 2. 核心状态机流转

### 2.1 document 状态枚举（全量 8 个）

`draft / submitted / analyzing / pending_approval / returned / rejected / approved / completed`

### 2.2 状态跃迁矩阵（唯一合法迁移）

| 当前状态 | 操作 | 操作人 | 目标状态 | 关键规则 |
| --- | --- | --- | --- | --- |
| draft | 提交 | 申请人本人 | submitted | 强校验：必填、明细 ≥1、`total_amount = Σ明细`（2 位小数）、必需附件齐全 |
| submitted | 系统流转 | 系统 | analyzing | 事务内：生成快照 + 审批实例 + 首任务 + 发 MQ |
| analyzing | 系统流转 | 系统 | pending_approval | 分析完成；**重试 3 次仍失败 → 标注 `analysis_failed` 仍进 pending_approval**，审批人可手工重分析 |
| pending_approval | 通过（非最后节点） | 当前节点 assignee | pending_approval | `current_node` 更新，生成下一节点任务 |
| pending_approval | 通过（最后节点） | 当前节点 assignee | approved | 审批实例 completed |
| pending_approval | 退回 | 当前节点 assignee | returned | 意见必填；实例 returned，未完成任务 cancelled |
| pending_approval | 驳回 | 当前节点 assignee | rejected | 意见必填；**终态** |
| pending_approval | 撤回 | 申请人本人 | returned | 仅申请人；当前任务 cancelled，实例 returned |
| returned | 修改重提 | 申请人本人 | submitted | **version + 1**，新快照、重建审批实例、全量重分析 |
| rejected | 恢复 | 管理员 | draft | 仅管理员；强制填恢复原因，写入 operation_log |
| approved | 确认完成 | 财务/管理员 | completed | 终态，归档，可生成报告 |

- 审批链默认：`申请人提交 → 部门负责人审批 → 财务审核`；条件加签（如 `total_amount ≥ 300000` 插入分管副总节点）由审批流模板配置。
- 所有迁移必须经状态机服务校验，非法迁移抛 `409xx`。

### 2.3 子状态机

- 审批实例 `approval_instance.status`：`running → completed / returned / rejected / cancelled`
- 审批任务 `approval_task.status`：`pending → done / cancelled`；`action`：`approved / returned / rejected`
- 审批意见 `approval_opinion.action`：`submit / resubmit / approve / return / reject / withdraw`
- 风险项 `risk_item.status`：`open → handled / dismissed`（处理人、意见、时间落库）

---

## 3. 数据一致性约束

### 3.1 快照 `document_snapshot`：只读不可变

- 提交/重提时事务内生成；`payload` = 全量 JSON：`{document, details[], attachments[]（元数据）}`。
- **写入后任何接口不得修改**：无 UPDATE 语句、无修改 API，仅只读查询。
- 附件存储层同不可变：对象键 `{doc_no}/v{version}/{uuid}_{file_name}`，提交后上传通道关闭；新版本附件写新目录，不覆盖旧文件。
- 用途：审批人看"提交时点"数据、退回前后版本对比、审计取证。按 `version` 隔离，历史分析结果全保留。

### 3.2 审批并发：乐观锁（version 字段）

- `document.version` 作审批链版本：**审批操作与撤回/重提必须携带 version 做乐观锁比对**。
- 版本不一致返回 `40903`，响应携带服务端最新 version，前端提示刷新。
- 审批操作幂等键 = `taskId + 单据审批版本`，重复请求返回幂等结果，不重复执行。
- 服务端审批前校验三条件：当前用户 = 任务 assignee；`task.status = pending`；`document.status = pending_approval`。

### 3.3 其他强一致约束

- `total_amount = Σ明细 amount`：前端实时联动，**后端提交时强校验**，不等直接拦（R-02 阻塞性规则）。
- `doc_no` 服务端生成（`FYyyyyMMdd-001` 当日 3 位流水），唯一索引 + 防并发重复，前端不传。
- `operation_log` 只追加（append-only）：无修改/删除接口与 SQL 权限；风险处理记录不可删除，只可追加更正。
- 提交事务一次完成：快照 + 审批实例 + 首任务，任一步失败整体回滚。

---

## 4. 异步链路要求（MQ）

### 4.1 流转链

```
提交事务提交 → MQ 事件 → 解析任务消费（OCR + 字段抽取）→ attachment_parse_result
    → 发"解析完成"事件 → 风险分析任务消费（规则引擎）→ risk_analysis + risk_item + risk_evidence
    → 状态机流转 analyzing → pending_approval
```

- 全程异步，前端提交后只拿到任务 ID；状态由 `submitted → analyzing → pending_approval` 自动流转，前端轮询或通知。
- 解析/分析结果**只作建议**：无论风险等级高低一律进 pending_approval 由人工决策，机器不自动决策。

### 4.2 失败重试与兜底

| 环节 | 策略 |
| --- | --- |
| 解析/分析任务失败 | 自动重试 **3 次** |
| 重试仍失败 | 单据标注 `analysis_failed`（`risk_analysis.status = failed`），**仍进入 pending_approval**，不阻塞审批 |
| 兜底 1 | 审批人/财务/管理员在详情页手工触发"重新分析"（记录触发人与原因，`trigger_type = manual`） |
| 兜底 2 | RocketMQ 死信队列（DLQ），超时告警（解析 P95 < 60s，分析 P95 < 30s） |
| 消费者幂等 | 按消息唯一键去重，重复消费不产生脏数据 |
| 状态回写 | 任务完成回写只经状态机服务，校验合法迁移 |

### 4.3 触发时机（3 种）

1. `auto`：提交/重提自动触发（主路径）。
2. `resubmit`：退回重提，新版本全量重分析，旧版结果按 version 保留。
3. `manual`：analysis_failed 或人工点击"重新分析"。

---

## 5. 统一规范

### 5.1 接口前缀与认证

- 全部接口前缀 **`/api/v1`**；认证 `Authorization: Bearer <JWT>`（有效期 2h）；Content-Type `application/json`，上传 `multipart/form-data`。
- 分页：`page` 从 1 起，`page_size` 默认 20 最大 100；返回 `{total, page, page_size, list}`。

### 5.2 统一响应体 `Result<T>`

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "trace_id": "1a2b3c4d5e6f"
}
```

### 5.3 错误码

| 段 | 含义 |
| --- | --- |
| `0` | 成功 |
| `400xx` | 参数错误 |
| `401xx` | 未认证/凭证失效（40103 账号锁定 15 分钟） |
| `403xx` | 无权限/数据越权 |
| `404xx` | 资源不存在 |
| `409xx` | 状态冲突：40901 非法流转 / 40902 任务已处理 / **40903 乐观锁版本冲突** |
| `500xx` | 系统错误 |

### 5.4 异常处理

- 业务异常统一抛 **`BizException(code, message)`**；全局 `GlobalExceptionHandler` 捕获后转 `Result`，HTTP 状态与 code 段对应。
- 禁止在 Controller 内 try-catch 吞业务异常、禁止返回裸 String/Map 作响应。
- 每个请求生成 `trace_id` 贯穿响应与 operation_log，可按 trace_id 串起一次请求全链路。
- 校验失败返回逐字段错误信息，前端逐个标红。

---

## 6. 关键数据模型速查

> 真库物理表名（23 张，MySQL 8 `financial_risk_audit`）：`user / role / permission / user_role / role_permission / document / document_item / attachment / attachment_parse_result / document_snapshot / risk_rule / risk_analysis / risk_item / risk_evidence / approval_flow / approval_task / approval_opinion / audit_log / notification / report / expense_standard / vendor / dict`。下方速查表为规划名，物理对应：document_detail→document_item、approval_instance→approval_flow、operation_log→audit_log、sys_*→RBAC 5 表、approval_flow_def/flow_node→固定三节点(建表内无模板表)、risk_rule_config→risk_rule(params JSON)。

| 表 | 关键点 |
| --- | --- |
| `document` | `doc_no` UNIQUE；`status/version/current_node` 状态机核心；`total_amount DECIMAL(14,2)`；冗余 `risk_level/risk_count`；`delete_flag` 逻辑删除 |
| `document_detail` | 逐行费用明细；`amount > 0`，2 位小数 |
| `document_snapshot` | `payload JSON` 不可变全量快照，见 §3.1 |
| `attachment` | `parse_status: parsing/parsed/failed`；`storage_path` 按 `{doc_no}/v{version}/` 组织 |
| `attachment_parse_result` | `fields JSON: [{label, value, confidence, position}]`；按单据类型字段模板抽取 |
| `approval_instance` | `running/completed/returned/rejected/cancelled`；关联 `flow_def_id` 模板 |
| `approval_task` | `assignee_id` 路由审批人；`pending/done/cancelled` + `action` |
| `approval_opinion` | 全程时间线，含 submit/resubmit 记录 |
| `risk_analysis` | `doc_version` 隔离历史；`overall_level` + 三级计数；`recommendation` 四档；`trigger_type: auto/resubmit/manual` |
| `risk_item` | `rule_code R-01~R-10`；`level: high/mid/low`；`status: open/handled/dismissed` |
| `risk_evidence` | 引用附件、页码、原文片段 `snippet`、置信度 |
| `operation_log` | append-only；记 IP/User-Agent/trace_id；保留 ≥5 年按月归档 |
| `report` | `content JSON` 严格 8 部分；`report_no: RPT-yyyyMMdd-xxxx`；导出文件落库可回查 |
| 全部业务表 | 预留 `tenant_id`（多租户） |

### 6.1 风险规则 10 类（规则引擎配置化）

| 编码 | 规则 | 默认等级 |
| --- | --- | --- |
| R-01 | 金额一致性（单据 vs 明细 vs 发票解析，容差默认 ¥0.01） | high |
| R-02 | 明细合计校验（阻塞性：提交直接拦截，不走风险项） | — |
| R-03 | 合同与付款一致性 | high |
| R-04 | 批量付款校验 | high |
| R-05 | 费用标准（城市/职级/晚数） | mid |
| R-06 | 市场价格偏离（默认 10%） | mid |
| R-07 | 消费异常（连号发票/单日多票等） | mid |
| R-08 | 供应商风险（年限/黑名单） | mid/high |
| R-09 | 附件完整性（置信度阈值默认 85） | low/mid |
| R-10 | 重复票据（发票号历史比对） | high |

- 整体等级 = max(风险项等级)，无风险项为 `none`。
- 建议映射：有 high → `manual_review`（金额/合同类可升级 `reject_suggest`）；仅 mid → `supplement`；仅 low → `pass` 或 `manual_review`；none → `pass`。可配置覆盖。
- 审批通过时存在 open 的 high 风险项：前端强提示二次确认，确认行为写入审批意见与日志。

### 6.2 角色与数据权限

| 角色 | 编码 | 数据范围 |
| --- | --- | --- |
| 申请人 | APPLICANT | 本人单据 |
| 部门负责人 | DEPT_MANAGER | 本部门 |
| 财务审核人 | FINANCE | 全部 |
| 系统管理员 | ADMIN | 全部 + 配置 |

一名用户可多角色，按操作上下文取角色；服务端强制数据权限过滤，前端仅体验。

真库物理角色 6 个（role 表）：`admin`（系统管理员）/ `finance_manager`（财务经理）/ `finance_staff`（财务专员）/ `dept_manager`（部门经理）/ `employee`（员工）/ `auditor`（审计员）。逻辑→物理映射：APPLICANT=employee，DEPT_MANAGER=dept_manager，FINANCE=finance_manager+finance_staff+auditor，ADMIN=admin。

---

## 7. 开发铁律清单（AI 编码自检）

1. Controller 零业务逻辑；状态修改只走状态机服务。
2. 所有状态迁移按 §2.2 矩阵，未列出的迁移一律拒绝。
3. 审批/撤回/重提必带 version 乐观锁，冲突返回 40903。
4. 快照与 operation_log 只有 INSERT + SELECT，永远无 UPDATE/DELETE。
5. 解析/分析只走 MQ 异步链，Service 禁止同步调用。
6. 异常只抛 BizException，响应只走 Result，接口前缀 /api/v1。
7. 权限三层（本人/本部门/全部）服务端校验。
8. 金额统一 DECIMAL(14,2)，前端浮点计算禁止直接用于提交值。
9. 历史数据按 version 保留，禁止清理旧版本分析/快照。
10. 新增规则 = 新增一个 executor 注册进引擎，不改主流程。
