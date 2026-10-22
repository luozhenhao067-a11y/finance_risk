# 财务单据智能风险审核系统 规格说明书（Spec）

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.0 |
| 编写日期 | 2026-10-22 |
| 文档状态 | 评审后进入开发 |
| 适用读者 | 前端开发、后端开发、测试、实施 |

---

## 1. 系统概述

### 1.1 背景与目标

财务单据审核长期依赖人工：单据数量大、票据真伪与重复报销难查、费用标准与合同条款核对靠经验，效率低且风险高。本系统对费用报销、差旅费报销、采购付款、合同付款、借款单五类单据，在"申请人提交—审批流转—财务复核"的全链路上引入智能风险分析，形成"机器识别风险 + 人工决策闭环"。

**核心目标：**

1. 单据全生命周期线上化：创建、明细维护、附件上传、提交、审批、退回、驳回、完成、报告归档。
2. 智能风险分析：提交时自动解析附件（OCR + 结构化抽取），基于规则引擎生成风险项、风险等级、判断依据、证据与处理建议。
3. 人工审核闭环：审批人依据风险分析结果做通过 / 退回 / 驳回决策，决策与风险处理结果全程留痕。
4. 可审计：快照、审批意见、风险处理记录、操作日志全部不可变留痕，可回查可追溯。

### 1.2 核心价值

| 维度 | 价值 |
| --- | --- |
| 效率 | 审批人直接看风险结论与证据定位，不再逐张核票据；附件字段自动解析回填 |
| 风控 | 重复票据、金额不一致、费用超标准、合同付款偏差等由规则系统化拦截 |
| 合规 | 每次提交生成不可变快照，审批链、风险处理、报告全部留痕，满足审计要求 |
| 数据沉淀 | 风险数据、供应商数据、费用数据持续积累，支持后续统计分析 |

### 1.3 用户角色

| 角色 | 编码 | 主要职责 | 数据权限范围 |
| --- | --- | --- | --- |
| 申请人 | APPLICANT | 创建/编辑/提交单据，处理退回，查看自己单据全生命周期 | 仅本人创建的单据 |
| 部门负责人 | DEPT_MANAGER | 审批本部门单据的第一审批节点，通过/退回/驳回 | 本部门全部单据 |
| 财务审核人 | FINANCE | 审批最终节点，查看全量单据、风险分析、生成与导出报告 | 全部单据 |
| 系统管理员 | ADMIN | 用户/角色/部门管理，审批流配置，风险规则与费用标准配置，审计日志查询 | 全部数据 + 配置权限 |

> 一名用户可身兼多角色（如部门负责人同时是申请人），角色校验按"操作上下文"取对应角色。示例数据中的既有角色（张伟/李明/王芳）按上表映射。

### 1.4 技术栈总览

- 前端：Vue 3 + Vite + Element Plus + Pinia + Vue Router + Axios + ECharts。
- 后端：Java 17 + Spring Boot 3.x + Spring Security（JWT + RBAC）+ MyBatis-Plus + MySQL 8 + Redis + RocketMQ（异步任务）+ MinIO（文件存储）。
- 智能分析：附件解析服务（OCR + 字段结构化抽取）+ 风险规则引擎（规则可配置，LLM 辅助判断为可选扩展）。

---

## 2. 功能模块划分

一级模块共 6 个：

| 模块 | 核心职责 |
| --- | --- |
| 单据管理 | 五类单据的创建、草稿编辑、明细维护、附件上传、提交、退回重提、撤回；单据编号生成；快照生成 |
| 智能风险分析 | 附件解析（OCR/字段抽取）、风险规则执行、风险项/证据/等级/处理建议生成、风险处理记录 |
| 审批流转 | 审批实例与任务生成、节点流转（部门负责人 → 财务审核，可配置加签）、通过/退回/驳回/撤回操作 |
| 报告中心 | 风险审核报告生成、报告列表、报告详情查看、PDF/Excel 导出与下载回查 |
| 审计日志 | 全系统操作日志记录、按单据/操作人/时间/动作查询，日志只读不可篡改 |
| 系统管理 | 用户、角色、部门、审批流模板、风险规则、费用标准、供应商档案、字典配置 |

---

## 3. 核心业务流程

### 3.1 单据完整生命周期流程

```
[申请人] 新建单据(草稿 draft)
    │
    ├─ 填写基本信息（类型/标题/归属部门/项目）
    ├─ 维护费用明细（逐行：费用类型/日期/金额/发票号/备注）
    │     └─ 合计金额 total_amount 实时联动 = Σ明细金额（前端实时计算，后端提交时强校验）
    ├─ 上传附件（发票/合同/行程单等 PDF、PNG、JPG）
    ├─ 保存草稿（可多次，随时可编辑）
    │
    ▼
[提交校验] 提交（draft → submitted）
    ├─ 必填校验：基本信息、≥1 条明细、必需附件齐全
    ├─ 金额校验：total_amount = Σ明细金额，2 位小数
    └─ 不通过 → 返回前端错误提示，仍为 draft
    │
    ▼
[系统] submitted → analyzing（异步自动流转，秒级完成）
    ├─ 1. 生成不可变快照 document_snapshot（version = 当前版本，含单据+明细+附件元数据全量 JSON）
    ├─ 2. 生成审批实例 approval_instance 与首个审批任务 approval_task（当前节点 = 审批链首节点）
    ├─ 3. 创建附件解析任务：OCR + 字段结构化抽取 → attachment_parse_result（解析文本/字段/页码/置信度）
    ├─ 4. 解析完成后触发风险分析任务：规则引擎逐条执行 → risk_analysis + risk_item + risk_evidence
    │     （分析失败自动重试 3 次；仍失败则标注 analysis_failed 并进入待审批，审批人可手工触发重新分析）
    │
    ▼
[系统] analyzing → pending_approval（分析完成后自动流转）
    │
    ▼
[审批人] 当前节点审批（pending_approval）
    ├─ 查看：基本信息/明细/附件解析结果/风险项+证据+处理建议/审批流转历史
    ├─ 决策一：通过 approve
    │     ├─ 非最后节点 → 任务完成，流转下一节点（pending_approval，current_node 更新）
    │     └─ 最后节点   → 单据状态 approved，审批实例 completed
    ├─ 决策二：退回 return → 单据状态 returned，终止当前审批链
    │     └─ [申请人] 修改后重新提交（version + 1，重新走 submitted → analyzing → pending_approval，新快照+新分析）
    ├─ 决策三：驳回 reject → 单据状态 rejected（终态，流程终止）
    └─ [申请人] 撤回 withdraw → 单据状态 returned（当前节点任务取消，实例挂起）
    │
    ▼
[财务/管理员] approved → completed（财务确认完成，如付款/记账确认；单据归档，可生成报告）
```

### 3.2 智能风险分析触发时机与结果处理

**触发时机（3 种）：**

1. 提交/重提时自动触发（主路径）：解析任务完成后自动发起。
2. 退回重提后自动触发：新版本全量重新分析，旧版本分析结果保留为历史（按 version 隔离）。
3. 人工触发：analysis_failed 时、或财务/管理员在单据详情"风险分析"页点击"重新分析"（记录触发人与原因）。

**结果处理原则：**

- 风险分析结果是**建议**，不做自动决策：无论风险等级高低，单据一律进入 pending_approval 由人工决策。
- 整体风险等级 = 单项最高等级（high > mid > low > none），并结合风险数量展示（如"高风险（4 项：高 2 · 中 1 · 低 1）"）。
- 处理建议四档：`pass`（建议通过）/ `supplement`（补充材料）/ `manual_review`（人工复核）/ `reject_suggest`（建议驳回）。
- 每个风险项有状态：`open`（待处理）→ `handled`（已处理）/ `dismissed`（已排除），处理人、处理意见、处理时间落库。
- 审批通过时校验：存在 `open` 状态 high 级风险项时，前端强提示（需确认后仍可通过），确认行为记入审批意见与日志。

### 3.3 人工审核决策点

| 决策点 | 操作人 | 可执行操作 | 操作后状态 |
| --- | --- | --- | --- |
| 提交前 | 申请人 | 保存草稿 / 提交 | draft / submitted |
| 审批节点 1（部门负责人审批） | 部门负责人 | 通过 / 退回 / 驳回 | 流转财务审核 / returned / rejected |
| 审批节点 2（财务审核） | 财务审核人 | 通过 / 退回 / 驳回 | approved / returned / rejected |
| 大额加签节点（单笔 ≥ ¥300,000，可配置） | 分管副总（规则指定） | 通过 / 退回 / 驳回 | 流转财务审核 / returned / rejected |
| 审批中 | 申请人 | 撤回 | returned |
| 退回后 | 申请人 | 修改后重新提交 / 放弃（单据保留在 returned） | submitted / returned |
| 审批通过后 | 财务/管理员 | 确认完成 | completed |

### 3.4 退回重提与版本

- 退回（returned）与驳回（rejected）的区别：退回可修改后重提，驳回为终态（仅管理员经线下确认后可恢复为 draft，恢复操作强制留痕）。
- 每次重提 version + 1，生成新快照；审批意见、历史快照、历史风险分析按版本保留，单据详情可按版本回溯对比。

### 3.5 撤回

- 仅申请人在 pending_approval 状态可撤回；当前节点任务置 cancelled，审批实例置 returned；撤回后单据状态为 returned，可修改重提。

---

## 4. 详细功能规格（按页面）

### 4.1 登录页 `/login`

**页面目标**：身份认证入口。

- 主要功能点：账号密码登录、"记住用户名"、登录失败提示。
- 关键交互：登录成功跳转工作台；已登录访问登录页自动跳转工作台；带 `redirect` 参数时登录后回跳原地址。
- 字段与校验：用户名/密码非空；连续 5 次失败锁定账号 15 分钟（后端实现）。
- 权限控制：公开页面；其余所有页面未登录统一跳转登录页（路由守卫）。

### 4.2 工作台 `/dashboard`

**页面目标**：用户进入系统后的总览首页。

- 主要功能点：
  - 统计卡片：待我审批数、高风险单据数、审批中单据数、本月已完成数。
  - 风险分布图（高/中/低数量，环形图）。
  - 我的待办（按风险等级着色，点击跳转单据详情）。
  - 站内通知列表（风险分析完成、进入审批等），支持一键全部已读。
- 权限控制：统计口径按角色数据权限过滤；待办仅展示分配给当前用户的任务。

### 4.3 单据管理列表 `/documents`

**页面目标**：单据全量检索与入口。

- 主要功能点：
  - 列表字段：单据编号、类型、标题、申请人、部门、金额、状态、风险等级、当前节点、提交时间、版本。
  - 筛选：单据类型、状态、风险等级、关键字（编号/标题/申请人）、日期范围。
  - 分页 + 排序（金额、提交时间）。
  - 行操作：查看详情、编辑（仅 draft/returned 且为本人）、撤回（仅 pending_approval 且为本人）、重新提交（仅 returned 且为本人）。
- 权限控制：申请人仅见本人单据；部门负责人见本部门；财务/管理员见全部。删除仅限 draft 且本人。

### 4.4 新建/编辑单据 `/documents/new`、`/documents/:id/edit`

**页面目标**：录入单据信息、明细与附件，保存草稿或直接提交。

- 主要功能点：
  - 基本信息：单据类型（下拉，五类）、标题、归属部门、费用归属项目。
  - 费用明细表格：行内新增/编辑/删除，合计实时联动展示。
  - 附件上传：多选上传，支持 PDF/PNG/JPG，展示文件名/大小/类型图标，可删除。
  - 操作：保存草稿 / 提交审批 / 取消。
- 字段与校验规则：

| 字段 | 规则 |
| --- | --- |
| title | 必填，≤100 字符 |
| doc_type | 必填，枚举：费用报销 / 差旅费报销 / 采购付款 / 合同付款 / 借款单 |
| dept_id | 必填，默认取当前用户部门 |
| project | 必填，≤100 字符 |
| expense_type | 必填；按单据类型限定可选集合（交通费/住宿费/餐饮费/场地费/设备采购/合同款/借款 等，字典配置） |
| expense_date | 必填，合法日期，不得晚于当前日期；差旅类须在行程日期范围内 |
| amount | 必填，> 0，最多 2 位小数 |
| invoice_no | 报销类必填；格式校验（数字 8/10 位或 `INV-`/`HT-` 前缀 + 数字）；借款单可为"—" |
| remark | 选填，≤200 字符 |
| total_amount | 只读展示 = Σ明细 amount；前端实时联动，后端提交时强校验一致性 |
| 附件 | 单个 ≤20MB，类型白名单 pdf/png/jpg；报销类 ≥1 个发票附件，采购付款/合同付款必须含合同附件 |

- 关键交互：明细合计与 total_amount 实时联动；未保存离开页面弹确认；提交前前端预校验，后端提交接口返回逐字段错误。
- 权限控制：编辑仅限本人且状态为 draft/returned；单据类型一经提交不可变更。

### 4.5 单据详情 `/documents/:id`

**页面目标**：单据全信息查看与操作中心，6 个 Tab。

**Tab 1 基本信息**：单据编号、类型、标题、申请人、部门、项目、合计金额、状态、版本、当前节点、提交时间；高风险单据顶部醒目提示条。

**Tab 2 费用明细**：明细表格（类型/日期/金额/发票号/备注）+ 合计行；只读展示（编辑入口仅在可编辑状态显示）。

**Tab 3 附件与解析**：
- 附件列表（文件名/大小/上传时间/解析状态：parsing/parsed/failed）。
- 点击附件预览（PDF 在线预览，图片放大查看）；下载需带鉴权签名。
- 解析结果面板：每份附件展示解析字段表（字段名/解析值/置信度）与解析文本、页码、识别位置。

**Tab 4 风险分析**：
- 整体风险等级徽标 + 高/中/低数量 + 处理建议 + 分析摘要 + 分析时间。
- 风险项列表（按等级排序，可切换升/降序）：每项含等级、标题、判断依据、证据（引用附件页码+高亮片段+置信度）、处理建议、状态、处理人/处理意见。
- 风险处理操作（财务/审批人）：标记已处理（填写处理意见）/ 排除（填写理由）。
- "重新分析"按钮（财务/管理员，analysis_failed 或需要重算时）。

**Tab 5 审批流转**：
- 流程进度条：申请人提交 → 部门负责人审批 → （大额加签）→ 财务审核 → 审批完成；节点状态：done/current/pending/cancelled。
- 审批意见时间线：每节点操作人、动作（提交/通过/退回/驳回/撤回/重提）、意见、时间。
- 审批操作区（当前节点审批人可见）：通过 / 退回 / 驳回 + 意见输入框（退回/驳回意见必填，≤500 字符）。
- 撤回按钮（申请人，pending_approval 状态）。

**Tab 6 审计日志**：单据维度操作日志（时间倒序）：动作、操作人、角色、详情。

- 权限控制：
  - 审批操作区仅当前节点任务的被分配人可见。
  - 附件下载：申请人本人、本单据审批链参与人、财务、管理员。
  - 退回/驳回、撤回按钮按 3.3 决策点矩阵控制。
  - 版本回溯（返回键切换历史版本快照对比）财务/管理员可用。

### 4.6 风险分析中心 `/risks`

**页面目标**：风险全局视图与风险工作台。

- 主要功能点：
  - 筛选：风险等级、单据类型、风险项状态（open/handled/dismissed）、日期范围。
  - 列表/卡片：单据编号、类型、整体风险、风险数、分析时间、处理建议，点击进入单据详情"风险分析"Tab。
  - 汇总统计：各级风险单据数、open 风险项 TOP 规则。
- 权限控制：申请人仅见本人单据风险；部门负责人见本部门；财务/管理员全量。

### 4.7 审批中心 `/approvals`

**页面目标**：审批人任务工作台。

- 主要功能点：
  - 左侧：待办队列（待我审批的单据，按提交时间/风险等级排序），筛选单据类型。
  - 右侧：选中单据概览（基本信息、明细、附件、风险项、整体风险、审批进度），内嵌通过/退回/驳回操作与意见输入。
  - 已办列表：我处理过的任务与我的决策记录。
- 关键交互：退回/驳回必须填意见；通过时如存在 open 的高风险项弹二次确认，确认内容写入审批意见。
- 权限控制：待办任务严格按 assignee = 当前用户过滤；审批操作服务端校验任务状态为 pending 且单据状态为 pending_approval，防止重复操作（并发用乐观锁 version 字段）。

### 4.8 报告中心 `/reports` 与报告详情 `/reports/:docId`

**页面目标**：风险审核报告的生成、查看与导出。

- 主要功能点（报告中心）：报告列表（报告编号、单据编号、生成时间、整体风险、处理建议）、生成报告入口、导出下载。
- 报告详情内容（严格包含 PRD 要求的 8 部分）：
  1. 单据摘要（编号/类型/标题/申请人/金额/状态/提交时间）。
  2. 整体风险（等级 + 风险数量分布）。
  3. 金额核对表（逐费用类型：单据金额 / 解析金额 / 差额 / 结论，含合计行）。
  4. 风险项列表（等级/标题/依据/证据/建议）。
  5. 证据列表（附件引用、页码、片段、置信度）。
  6. 供应商风险（供应商名称、评分、等级、说明；无供应商单据显示"不适用"）。
  7. 处理建议（四档 + 摘要）。
  8. 人工复核意见（审批人意见时间线）。
- 关键交互：生成报告（单据 approved/completed 后自动生成一次，也可手动生成覆盖）；导出 PDF/Excel，导出文件落库可下载、可回查。
- 权限控制：财务/管理员可生成与导出；申请人可查看本人单据报告（不含导出，MVP 可放宽为可下载）。

### 4.9 审计日志 `/logs`

**页面目标**：全系统操作审计查询。

- 主要功能点：按单据编号、操作人、动作类型、时间范围筛选；分页列表（时间、操作人、角色、动作、对象、详情）。
- 权限控制：仅财务与管理员可见；日志只读，无任何修改/删除入口。

### 4.10 系统管理 `/admin/*`（管理员）

| 子页面 | 功能 |
| --- | --- |
| 用户管理 | 用户增删改查、启用/停用、角色分配 |
| 角色管理 | 角色定义与权限点分配 |
| 部门管理 | 部门树维护、部门负责人指定（审批任务按此路由） |
| 审批流配置 | 审批链模板维护：基础链 部门负责人审批 → 财务审核；条件加签规则（如单笔 ≥ ¥300,000 增加分管副总节点） |
| 风险规则配置 | 10 类规则启用/停用、参数（金额容差、费用标准阈值、置信度阈值等） |
| 费用标准配置 | 差旅住宿/交通/餐饮标准（按城市/职级/晚数） |
| 供应商档案 | 供应商基础信息、评分、黑名单维护 |
| 字典配置 | 费用类型、单据类型等枚举维护 |

---

## 5. 数据模型与状态机详细设计

### 5.1 实体关系总览

```
user ─┬─ applicant ─┐
dept ─┴─────────────┤
                    ▼
              document (1)───(N) document_detail
                  │
                  ├──(N) document_snapshot (按 version)
                  ├──(N) attachment ──(N) attachment_parse_result
                  ├──(1) approval_instance ──(N) approval_task
                  │                                └──(N) approval_opinion
                  ├──(N) risk_analysis ──(N) risk_item ──(N) risk_evidence
                  ├──(N) operation_log
                  └──(N) report
```

### 5.2 表结构设计

**主表 `document`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_no | VARCHAR(32) UNIQUE | 单据编号，格式 `FY20261021-001`（FY + yyyyMMdd + "-" + 3 位当日流水，服务端生成防并发重复） |
| doc_type | VARCHAR(32) | 费用报销 / 差旅费报销 / 采购付款 / 合同付款 / 借款单 |
| title | VARCHAR(100) | 标题 |
| applicant_id | BIGINT | 申请人 |
| dept_id | BIGINT | 归属部门 |
| project | VARCHAR(100) | 费用归属项目 |
| total_amount | DECIMAL(14,2) | 合计金额，与明细合计强一致 |
| status | VARCHAR(32) | 状态机，见 5.3 |
| version | INT | 版本号，初值 1，重提 +1 |
| current_node | VARCHAR(32) | 当前审批节点名 |
| submit_time | DATETIME | 最近一次提交时间 |
| create_time / update_time | DATETIME | 创建/更新时间 |
| risk_level | VARCHAR(16) | 冗余字段：整体风险等级（none/low/mid/high） |
| risk_count | INT | 冗余字段：风险项数量 |
| remark | VARCHAR(500) | 备注 |
| delete_flag | TINYINT | 逻辑删除标记 |

**明细表 `document_detail`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id | BIGINT | 单据 ID |
| expense_type | VARCHAR(32) | 费用类型（字典） |
| expense_date | DATE | 费用发生日期 |
| amount | DECIMAL(14,2) | 金额，>0 |
| invoice_no | VARCHAR(64) | 发票号/合同号 |
| remark | VARCHAR(200) | 备注 |

**快照表 `document_snapshot`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id | BIGINT | 单据 ID |
| version | INT | 快照对应版本 |
| payload | JSON | 不可变全量 JSON：{document, details[], attachments[]（元数据）} |
| created_at | DATETIME | 生成时间 |

快照机制说明：提交/重提时事务内生成；`payload` 写入后**任何接口不得修改**（后端仅提供只读查询，无 update 语句）；附件文件实体本身在存储层做只读化（提交后上传通道关闭，新版本附件写入新目录/新对象）；快照用于审批人查看"提交时点"的数据、退回重提前后版本对比、审计取证。

**附件表 `attachment`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id | BIGINT | 单据 ID |
| file_name | VARCHAR(255) | 原始文件名 |
| mime | VARCHAR(64) | MIME 类型 |
| file_type | VARCHAR(16) | pdf / image |
| size | BIGINT | 字节数 |
| storage_path | VARCHAR(512) | 存储路径（MinIO 对象键，按 `{doc_no}/{version}/{file_name}` 组织） |
| parse_status | VARCHAR(16) | parsing / parsed / failed |
| uploaded_by / uploaded_at | BIGINT / DATETIME | 上传人与时间 |

**附件解析结果 `attachment_parse_result`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id / attachment_id | BIGINT | 单据/附件 |
| page | INT | 页码 |
| raw_text | TEXT | 解析文本 |
| fields | JSON | 字段数组：[{label, value, confidence, position}]（发票号码/开票日期/销售方/金额合计/税额/合同编号/本期应付/付款比例 等，按单据类型模板） |
| confidence | DECIMAL(5,2) | 整体识别置信度 |

**审批实例 `approval_instance`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id | BIGINT | 单据 ID |
| flow_def_id | BIGINT | 审批流模板 ID |
| status | VARCHAR(16) | running / completed / returned / rejected / cancelled |
| current_node | VARCHAR(32) | 当前节点名 |
| start_time / end_time | DATETIME | 起止时间 |

**审批任务 `approval_task`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| instance_id | BIGINT | 实例 ID |
| doc_id | BIGINT | 单据 ID（冗余便于查询） |
| node | VARCHAR(32) | 节点名 |
| assignee_id / assignee_name | BIGINT / VARCHAR | 被分配人 |
| status | VARCHAR(16) | pending / done / cancelled |
| action | VARCHAR(16) | approved / returned / rejected（完成后） |
| created_at / finished_at | DATETIME | 创建/完成时间 |

**审批意见 `approval_opinion`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id / task_id | BIGINT | 单据/任务 |
| node | VARCHAR(32) | 节点名（"申请人提交"用于提交类记录） |
| user_id / user_name | BIGINT / VARCHAR | 操作人 |
| action | VARCHAR(16) | submit / resubmit / approve / return / reject / withdraw |
| opinion | VARCHAR(500) | 意见内容 |
| created_at | DATETIME | 时间 |

**风险分析 `risk_analysis`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id | BIGINT | 单据 ID |
| doc_version | INT | 对应单据版本 |
| status | VARCHAR(16) | running / completed / failed |
| overall_level | VARCHAR(16) | none / low / mid / high |
| high_count / mid_count / low_count | INT | 各级数量 |
| recommendation | VARCHAR(16) | pass / supplement / manual_review / reject_suggest |
| recommendation_label | VARCHAR(32) | 建议通过 / 补充材料 / 人工复核 / 建议驳回 |
| summary | VARCHAR(500) | 分析摘要 |
| trigger_type | VARCHAR(16) | auto / resubmit / manual |
| triggered_by | VARCHAR(64) | 触发人（manual 时） |
| analyzed_at | DATETIME | 完成时间 |

**风险项 `risk_item`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| analysis_id / doc_id | BIGINT | 分析/单据 |
| rule_code | VARCHAR(32) | 规则编码（R-01 ~ R-10） |
| level | VARCHAR(8) | high / mid / low |
| title | VARCHAR(100) | 风险标题 |
| basis | VARCHAR(500) | 判断依据 |
| suggestion | VARCHAR(200) | 处理建议 |
| page | INT | 证据页码 |
| confidence | DECIMAL(5,2) | 置信度 |
| status | VARCHAR(16) | open / handled / dismissed |
| handled_by / handled_at / handle_opinion | — | 风险处理记录（人/时间/意见） |

**风险证据 `risk_evidence`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| risk_item_id / doc_id | BIGINT | 风险项/单据 |
| attachment_id | BIGINT | 附件 |
| page | INT | 页码 |
| snippet | VARCHAR(500) | 原文片段（高亮依据） |
| confidence | DECIMAL(5,2) | 置信度 |

**操作日志 `operation_log`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id | BIGINT | 单据（可空，系统级操作） |
| action | VARCHAR(32) | 动作：创建单据/上传附件/提交审批/风险分析完成/审批通过/退回单据/驳回单据/撤回单据/重新提交/生成报告/查看风险报告/重新分析 等 |
| operator_id / operator_name / role | — | 操作人 |
| detail | VARCHAR(500) | 详情 |
| ip / user_agent | VARCHAR | 审计附加信息 |
| created_at | DATETIME | 时间 |

**报告 `report`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 主键 |
| doc_id | BIGINT | 单据 ID |
| report_no | VARCHAR(32) UNIQUE | 报告编号 `RPT-20261021-0087` |
| overall_level / overall_text | — | 整体风险 |
| recommendation_label / summary | — | 建议与摘要 |
| content | JSON | 报告 8 部分结构化内容（见 4.8） |
| export_file_path | VARCHAR(512) | 导出文件存储路径（PDF/Excel） |
| generated_by / generated_at | — | 生成人/时间 |

### 5.3 单据状态机详细设计

**状态枚举：** `draft / submitted / analyzing / pending_approval / returned / rejected / approved / completed`

```
                    ┌─────────────┐
       保存草稿      │    draft    │◄────────── 管理员恢复(仅 rejected, 留痕)
   ┌───────────────►│ (申请人编辑) │
   │                └──────┬──────┘
   │        提交校验通过     │ 提交
   │                       ▼
   │                ┌──────────────┐
   │                │  submitted   │
   │                └──────┬───────┘
   │           系统异步流转  │
   │                       ▼
   │                ┌──────────────┐   分析失败重试3次仍失败(标注 analysis_failed)
   │                │  analyzing   │──────────────────────┐
   │                └──────┬───────┘                      │
   │          分析完成自动流转│                              │
   │                       ▼                              ▼
   │                ┌──────────────────────┐
   │                │   pending_approval   │◄──── 节点流转(通过, 非最后节点)
   │                └──┬─────┬─────┬───────┘
   │       申请人撤回   │     │     │
   │                   │     │     │
   │                   ▼     ▼     ▼
   │               ┌──────┐ ┌──────────┐ ┌──────────┐
   │               │returned│ │ rejected │ │ approved │
   │               └──┬───┘ └──────────┘ └────┬─────┘
   │     修改后重提     │      (终态)            │ 财务确认完成
   │    (version + 1)  └───────────────────────►└──────────► completed (终态)
   └────────────────── (重走 submitted→analyzing→pending_approval)
```

**流转规则矩阵（谁可以操作什么）：**

| 当前状态 | 操作 | 操作人 | 目标状态 | 附加规则 |
| --- | --- | --- | --- | --- |
| draft | 编辑/删除 | 申请人本人 | draft / 删除 | 删除仅限 draft，物理删除或逻辑删除按审计要求 |
| draft | 提交 | 申请人本人 | submitted | 校验：必填、明细≥1、金额一致、必需附件 |
| submitted | 系统流转 | 系统 | analyzing | 事务内：快照 + 审批实例 + 解析/分析任务创建 |
| analyzing | 系统流转 | 系统 | pending_approval | 分析完成；失败重试 3 次后带 analysis_failed 标记进入 |
| pending_approval | 通过（非最后节点） | 当前节点 assignee | pending_approval | current_node 更新为下一节点，生成新任务 |
| pending_approval | 通过（最后节点） | 当前节点 assignee | approved | 实例 completed |
| pending_approval | 退回 | 当前节点 assignee | returned | 意见必填；实例 returned，未完成任务 cancelled |
| pending_approval | 驳回 | 当前节点 assignee | rejected | 意见必填；终态 |
| pending_approval | 撤回 | 申请人本人 | returned | 当前任务 cancelled，实例 returned |
| returned | 修改重提 | 申请人本人 | submitted | version + 1，新快照、复用或重建实例（推荐重建实例），全量重分析 |
| rejected | 恢复 | 管理员 | draft | 强制填写恢复原因，写入 operation_log |
| approved | 确认完成 | 财务/管理员 | completed | 终态 |

**并发控制：** 审批操作与撤回/重提使用单据 `version`（审批链版本）做乐观锁；同一任务重复操作返回 409 状态冲突错误。

### 5.4 审批实例/任务状态机

- 实例：`running → completed / returned / rejected / cancelled`（撤回时任务 cancelled、实例 returned）。
- 任务：`pending → done (approved/returned/rejected) / cancelled`。
- 节点链默认：`申请人提交 → 部门负责人审批 → 财务审核 → 审批完成`。
- 条件加签：审批流模板配置规则，如 `total_amount ≥ 300000` 时在部门负责人之后插入"分管副总审批"节点。

### 5.5 风险规则清单（10 类，规则引擎配置化）

| 规则编码 | 名称 | 适用单据类型 | 默认等级 | 判断逻辑要点 |
| --- | --- | --- | --- | --- |
| R-01 | 金额一致性 | 全部 | high | 单据金额 vs 明细合计 vs 发票解析合计，差额 > 容差（默认 ¥0.01）即命中 |
| R-02 | 明细合计校验 | 全部 | 阻塞性 | total_amount ≠ Σ明细 时提交直接拦截（不走风险项，前端联动 + 后端强校验） |
| R-03 | 合同与付款一致性 | 采购付款/合同付款 | high | 付款金额 vs 合同应付金额/付款节点/付款比例 |
| R-04 | 批量付款校验 | 采购付款（批量） | high | 各收款方明细合计 vs 总额；收款账户重复 |
| R-05 | 费用标准 | 差旅费报销/费用报销 | mid | 住宿/交通/餐饮 vs 标准配置（城市/职级/晚数） |
| R-06 | 市场价格偏离 | 采购付款 | mid | 单价 vs 市场比价库近期均价，偏离阈值（默认 10%） |
| R-07 | 消费异常 | 差旅费报销/费用报销 | mid | 节假日异常时段消费、连号发票、单日多票 |
| R-08 | 供应商风险 | 采购付款/合同付款 | mid/high | 成立年限 < 12 个月、黑名单、历史交易少 |
| R-09 | 附件完整性 | 全部 | low/mid | 必需附件缺失、发票要素不全、识别置信度 < 阈值（默认 85） |
| R-10 | 重复票据 | 全部 | high | 发票号与历史单据比对命中 |

**整体风险等级计算：** `overall_level = max(风险项等级)`；无风险项为 `none`。
**处理建议映射：** 存在 high → `manual_review`（金额/合同类可升级 `reject_suggest`）；仅 mid → `supplement`；仅 low → `pass` 或 `manual_review`；none → `pass`。规则引擎给出默认值，可配置覆盖。

---

## 6. 接口设计建议（RESTful）

### 6.1 通用约定

- 前缀：`/api/v1`；认证：`Authorization: Bearer <JWT>`；Content-Type：`application/json`，上传用 `multipart/form-data`。
- 统一响应体：

```json
{
  "code": 0,
  "message": "success",
  "data": { },
  "trace_id": "1a2b3c4d5e6f"
}
```

- 错误码：`0` 成功；`400xx` 参数错误；`401xx` 未认证/凭证失效；`403xx` 无权限/数据越权；`404xx` 资源不存在；`409xx` 状态冲突（非法流转/重复操作）；`500xx` 系统错误。
- 分页：`page`（从 1 起）、`page_size`（默认 20，最大 100），返回 `{ total, page, page_size, list }`。

### 6.2 核心接口清单

**认证与用户**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | /api/v1/auth/login | 登录，返回 JWT 与用户信息 |
| POST | /api/v1/auth/logout | 登出 |
| GET | /api/v1/auth/me | 当前用户信息与权限点 |

**单据与明细**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/documents | 单据分页列表（按角色数据权限过滤） |
| POST | /api/v1/documents | 创建单据（含明细，草稿或直接提交） |
| GET | /api/v1/documents/{id} | 单据详情聚合（含明细/附件/分析/审批/日志摘要） |
| PUT | /api/v1/documents/{id} | 编辑单据（仅 draft/returned 且本人） |
| DELETE | /api/v1/documents/{id} | 删除（仅 draft 且本人） |
| POST | /api/v1/documents/{id}/submit | 提交审批（draft → submitted → analyzing） |
| POST | /api/v1/documents/{id}/resubmit | 退回重提（version+1） |
| POST | /api/v1/documents/{id}/withdraw | 撤回 |
| GET | /api/v1/documents/{id}/snapshots | 版本快照列表 |
| GET | /api/v1/documents/{id}/snapshots/{version} | 指定版本快照详情 |
| POST | /api/v1/documents/{id}/details | 新增明细 |
| PUT | /api/v1/documents/{id}/details/{detailId} | 修改明细 |
| DELETE | /api/v1/documents/{id}/details/{detailId} | 删除明细 |

**附件**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/documents/{id}/attachments | 附件列表 |
| POST | /api/v1/documents/{id}/attachments | 上传附件（multipart，多文件） |
| GET | /api/v1/attachments/{id}/download | 下载（签名 URL 或流式返回） |
| GET | /api/v1/attachments/{id}/preview | 预览（PDF/图片） |
| DELETE | /api/v1/attachments/{id} | 删除（仅未提交单据） |
| GET | /api/v1/attachments/{id}/parse-result | 解析结果（文本/字段/页码/置信度） |

**审批**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/approvals/todo | 我的待办（pending 任务列表） |
| GET | /api/v1/approvals/done | 我的已办 |
| POST | /api/v1/approvals/tasks/{taskId}/approve | 通过 {opinion} |
| POST | /api/v1/approvals/tasks/{taskId}/return | 退回 {opinion 必填} |
| POST | /api/v1/approvals/tasks/{taskId}/reject | 驳回 {opinion 必填} |
| GET | /api/v1/documents/{id}/approval-flow | 审批流转详情（进度+意见时间线） |

**风险分析**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/documents/{id}/risk-analysis | 最新分析结果（含风险项+证据） |
| POST | /api/v1/documents/{id}/risk-analysis/rerun | 手动重新分析 |
| GET | /api/v1/risk-items | 风险项全局查询（筛选/分页） |
| PUT | /api/v1/risk-items/{id}/handle | 风险处理：{status: handled/dismissed, opinion} |

**报告与日志**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/reports | 报告列表 |
| POST | /api/v1/documents/{id}/report | 生成报告 |
| GET | /api/v1/reports/{id} | 报告详情 |
| GET | /api/v1/reports/{id}/export?format=pdf\|excel | 导出报告文件 |
| GET | /api/v1/logs | 操作日志查询 |
| GET | /api/v1/documents/{id}/logs | 单据维度日志 |

**系统管理（管理员）**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST/PUT/DELETE | /api/v1/admin/users | 用户管理 |
| GET/POST/PUT | /api/v1/admin/roles | 角色与权限点 |
| GET/POST/PUT/DELETE | /api/v1/admin/depts | 部门树 |
| GET/POST/PUT | /api/v1/admin/approval-flows | 审批流模板与加签规则 |
| GET/POST/PUT | /api/v1/admin/risk-rules | 风险规则参数配置 |
| GET/POST/PUT/DELETE | /api/v1/admin/standards | 费用标准配置 |
| GET/POST/PUT | /api/v1/admin/vendors | 供应商档案 |
| GET/POST/PUT | /api/v1/admin/dicts | 字典（费用类型等） |

### 6.3 关键请求/响应示例

**提交单据** `POST /api/v1/documents/{id}/submit`

```json
// 响应（data 部分）
{
  "doc": {
    "id": 101,
    "doc_no": "FY20261022-003",
    "status": "analyzing",
    "version": 1,
    "current_node": "部门负责人审批",
    "submit_time": "2026-10-22 14:30:05"
  },
  "snapshot_version": 1,
  "approval_instance_id": 2001,
  "parse_task_ids": ["pt-9001", "pt-9002"],
  "analysis_task_id": "rt-8001"
}
```

**风险分析结果** `GET /api/v1/documents/{id}/risk-analysis`

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 5001,
    "doc_id": 101,
    "doc_version": 1,
    "status": "completed",
    "overall_level": "high",
    "high_count": 1,
    "mid_count": 1,
    "low_count": 0,
    "recommendation": "manual_review",
    "recommendation_label": "人工复核",
    "summary": "存在金额不一致，请财务人工复核后决定通过或退回",
    "analyzed_at": "2026-10-22 14:31:02",
    "items": [
      {
        "id": 7001,
        "rule_code": "R-01",
        "level": "high",
        "title": "金额不一致",
        "basis": "报销单合计 ¥7,000.50 与发票解析合计 ¥6,980.50 不一致，差额 ¥20.00",
        "suggestion": "核对明细金额并更正，或补充差额说明",
        "status": "open",
        "evidences": [
          {
            "attachment_id": 3002,
            "file_name": "发票.png",
            "page": 1,
            "snippet": "价税合计 ¥4,860.00",
            "confidence": 98
          }
        ]
      }
    ]
  },
  "trace_id": "1a2b3c4d5e6f"
}
```

**审批通过** `POST /api/v1/approvals/tasks/{taskId}/approve`

```json
// 请求
{ "opinion": "同意报销，请财务复核发票明细。" }

// 响应（data）
{
  "doc_id": 101,
  "doc_status": "pending_approval",
  "current_node": "财务审核",
  "next_task": { "id": 8012, "node": "财务审核", "assignee_name": "王芳", "status": "pending" }
}
```

---

## 7. 非功能需求

### 7.1 性能

| 指标 | 要求 |
| --- | --- |
| 列表/查询接口 | P95 < 300ms（万级数据） |
| 单据详情聚合 | P95 < 500ms |
| 提交事务 | P95 < 2s（快照+实例+任务创建） |
| 附件解析 + 风险分析 | 异步，P95 < 60s（解析）/ P95 < 30s（规则分析），超时告警 |
| 报告生成 | P95 < 5s；导出异步化，完成后通知下载 |
| 并发 | 支持 200 并发审批操作无状态冲突（乐观锁 + 幂等） |

### 7.2 安全

- 认证：JWT（有效期 2h，refresh 机制可选）；密码 BCrypt 存储；登录失败锁定。
- 授权：RBAC 权限点 + 数据权限（本人/本部门/全量三层），服务端强制校验，前端控制仅做体验。
- 附件安全：下载/预览必须鉴权；使用短期签名 URL（5 分钟）；文件类型白名单 + 大小 ≤20MB；存储路径不暴露物理路径。
- 数据：敏感字段（手机号等）脱敏展示；传输 HTTPS；生产环境关闭 Swagger 或加认证。
- 防重放：审批操作幂等键（taskId + 单据审批版本），重复请求返回幂等结果。

### 7.3 审计

- `operation_log` 只追加（append-only），无修改/删除接口与 SQL 权限；保留 ≥ 5 年，按月归档。
- 快照 `payload` 不可变；风险处理记录不可删除（可追加更正）。
- 关键操作记录 IP、User-Agent、trace_id，支持按 trace_id 串起一次请求全链路。

### 7.4 可扩展性

- 风险规则引擎：规则注册式（每规则一个 executor），新增规则不改主流程；规则参数配置化。
- 审批流：模板 + 条件加签，支持后续多级/会签/或签。
- 附件解析：解析器接口化（OCR 厂商可替换），字段模板按单据类型配置。
- 预留多租户字段 `tenant_id`，业务表统一包含。

### 7.5 可用性

- 核心接口可用性 ≥ 99.9%；异步任务失败重试与死信队列；数据库每日备份；关键操作前端二次确认（驳回、删除）。

---

## 8. 技术实现建议

### 8.1 前端

- 选型：Vue 3.5（Composition API）+ Vite 6 + Element Plus + Pinia + Vue Router 4 + Axios + ECharts 5。
- 目录建议（在当前 `fronted` 项目上改造，保留现有页面骨架与视觉风格）：

```
fronted/src/
├── api/                  # Axios 封装 + 按模块接口定义（auth/documents/approvals/risks/reports/logs/admin）
├── assets/
├── components/           # 通用组件：RiskBadge/StatusBadge/AppLayout/AppSidebar/ToastHost 等
├── composables/          # useToast、useTableQuery 等
├── data/                 # mock 数据与 mock 拦截（过渡期）
├── router/               # 路由（现有 10 个视图 + 系统管理路由）
├── stores/               # Pinia：auth、document、approval、risk、report
├── styles/
├── utils/                # format（金额/日期/状态文案）、校验规则
└── views/                # 现有视图 + admin/
```

- 改造路径：现有 `src/store/appStore.js` 的 localStorage 单文件状态管理替换为 Pinia + API 层；页面结构、Tab 划分、流程节点顺序保持与现有实现一致；先抽 API 层（函数签名与后端接口一一对应），mock 切换时视图层零改动。

### 8.2 后端

- 选型：Java 17 + Spring Boot 3.x + Spring Security + MyBatis-Plus + MySQL 8 + Redis + RocketMQ + MinIO。
- 分层：controller → service（事务边界在此）→ mapper；领域事件（提交、分析完成、审批流转）走 MQ 解耦。
- 异步链：提交事务提交后发 MQ 事件 → 解析任务消费（OCR/字段抽取）→ 完成后发事件 → 风险分析任务消费（规则引擎）→ 完成后更新单据状态为 pending_approval（状态流转统一走状态机服务，校验合法迁移）。
- 轻量备选：团队若以 Node 为主，可用 NestJS + TypeORM + PostgreSQL + BullMQ 实现同等架构，接口契约不变。
- 交付物：后端工程 + DDL 初始化脚本 + 示例数据脚本（覆盖 PRD 验收 8 步链路）。

### 8.3 文件存储与附件解析

- 存储：MinIO（或 S3 兼容），对象键 `{tenant}/{doc_no}/v{version}/{uuid}_{file_name}`；提交后版本目录只读。
- 解析：PDF 转图 + OCR（百度 OCR / PaddleOCR 可选）；结构化抽取用模板匹配 + LLM（可选）兜底；解析结果含页码、位置、置信度，落 `attachment_parse_result`。

### 8.4 Mock 策略（前端先行开发）

1. 契约先行：以本 Spec 第 6 章接口为准，输出 OpenAPI 3.0 描述文件，前后端共同维护。
2. 前端 mock：使用 **MSW（Mock Service Worker）** 拦截 Axios 请求返回契约数据（现有 seed.js 数据迁移为 mock 数据源）；或使用 vite-plugin-mock。接口响应结构、错误码、分页格式与真实后端完全一致。
3. 异步模拟：提交后 mock 延迟 1~2 秒将状态 submitted → analyzing → pending_approval，模拟真实异步链路。
4. 切换：后端就绪后仅改 Axios baseURL 与关闭 MSW，前端代码零改动。
5. 演示模式：保留现有 localStorage 独立演示能力，作为无后端环境下的演示降级。

---

## 9. 优先级与迭代建议

### 9.1 MVP（P0，必须包含）

- 登录/登出 + RBAC 四角色 + 数据权限三层过滤。
- 单据 CRUD：五类单据、明细联动合计、附件上传（PDF/PNG/JPG）、草稿、提交、撤回、退回重提（version+1）、快照。
- 审批流：部门负责人 → 财务审核两节点 + 通过/退回/驳回 + 意见 + 流程进度可视化。
- 风险分析（规则引擎化）：**6 类核心规则**——R-01 金额一致性、R-02 明细合计、R-05 费用标准、R-09 附件完整性、R-10 重复票据、R-03 合同与付款一致性；风险项/证据/等级/处理建议 + 风险处理记录。
- 附件解析：OCR 字段抽取 + 解析结果展示（文本/字段/页码/置信度）。
- 报告：8 部分结构 + PDF/Excel 导出 + 下载回查。
- 审计日志全链路记录 + 查询。
- 示例数据：完整跑通 PRD 第 5 章验收 8 步链路。

### 9.2 第二阶段（P1）

- 大额加签节点（金额阈值配置化）与审批流模板管理页面。
- R-04 批量付款校验、R-06 市场价格、R-07 消费异常、R-08 供应商风险（供应商档案 + 比价库）。
- 站内消息中心 + 邮件通知（待办提醒、分析完成通知）。
- 风险分析 LLM 辅助判断（语义级风险、异常描述识别）。
- 工作台数据看板增强（部门/类型/趋势多维统计）。
- 版本快照对比视图（退回前后差异高亮）。

### 9.3 第三阶段（P2）

- 移动端适配 / 企业微信、钉钉集成审批。
- 与 ERP/财务系统对接（凭证回写、付款状态同步）。
- 电子签章、发票查验 API 对接（税务验真）。
- 多租户隔离、数据归档策略、报表自助配置。

---

## 附录 A：枚举字典汇总

| 枚举 | 取值 |
| --- | --- |
| doc_type | 费用报销 / 差旅费报销 / 采购付款 / 合同付款 / 借款单 |
| document.status | draft / submitted / analyzing / pending_approval / returned / rejected / approved / completed |
| approval_instance.status | running / completed / returned / rejected / cancelled |
| approval_task.status | pending / done / cancelled |
| approval_task.action | approved / returned / rejected |
| approval_opinion.action | submit / resubmit / approve / return / reject / withdraw |
| risk level | none / low / mid / high |
| risk_item.status | open / handled / dismissed |
| risk_analysis.recommendation | pass / supplement / manual_review / reject_suggest |
| parse_status | parsing / parsed / failed |

## 附录 B：现有前端与 Spec 映射表

| 现有前端（fronted/src） | Spec 对应 | 改造说明 |
| --- | --- | --- |
| views/LoginView.vue | 4.1 登录页 | 对接后端 /auth/login |
| views/DashboardView.vue | 4.2 工作台 | 统计改为接口数据 |
| views/DocumentsView.vue | 4.3 单据管理列表 | 分页/筛选走后端 |
| views/DocumentNewView.vue | 4.4 新建/编辑单据 | 校验规则按 4.4 表补齐 |
| views/DocumentDetailView.vue（6 Tab） | 4.5 单据详情 | 结构保留，数据改 API |
| views/RisksView.vue | 4.6 风险分析中心 | 增加风险处理操作 |
| views/ApprovalsView.vue | 4.7 审批中心 | 对接 todo 任务接口 + 乐观锁 |
| views/ReportCenterView.vue / ReportView.vue | 4.8 报告中心/详情 | 对接导出接口 |
| views/AuditLogsView.vue | 4.9 审计日志 | 对接 /logs 接口 |
| store/appStore.js（localStorage） | 后端 API 层 | 替换为 Pinia + api/；保留为 mock 降级 |
| data/seed.js | 数据库示例数据脚本 | 字段映射到 5.2 表结构 |
