# 财务单据智能风险审核系统（前端）

基于 Vue 3 + Vite 的可运行前端演示项目，按原型还原登录、工作台、新建单据、单据详情（风险分析）、审批处理、风险审核报告六个页面，并补齐单据管理、风险分析、报告中心、审计日志等入口页面。

## 运行

```bash
npm install
npm run dev
```

默认访问地址：http://localhost:5173

生产构建：

```bash
npm run build
npm run preview
```

演示账号：用户名、密码均非空即可登录（例如 `张伟` / `123456`）。

## 页面与路由

| 原型页面 | 路由 | 说明 |
| --- | --- | --- |
| 01 登录 | `/login` | 账号密码校验、记住我、登录后跳转 |
| 02 工作台 | `/dashboard` | KPI、最近单据、风险概览、待办、通知 |
| 03 新建单据 | `/documents/new` | 基本信息、费用明细、附件上传、提交前检查 |
| 04 单据详情 · 风险分析 | `/documents/:id` | 基本信息、费用明细、附件解析、风险分析、审批流转、审计日志 |
| 05 审批处理 | `/approvals` | 审批队列、单据摘要、风险提示、审批意见与操作 |
| 06 风险审核报告 | `/reports/:docId` | 报告预览、Excel 导出、PDF 打印 |
| 扩展：单据管理 | `/documents` | 全量单据检索、筛选 |
| 扩展：风险分析 | `/risks` | 全量风险项汇总 |
| 扩展：报告中心 | `/reports` | 报告归档、缺失报告生成、汇总导出 |
| 扩展：审计日志 | `/logs` | 全量操作留痕与导出 |

## 数据模型

前端使用单一响应式数据仓库模拟后端，数据定义在 `src/data/seed.js`，业务操作在 `src/store/appStore.js`。

- `documents`：单据主表，包含 `doc_no`、`doc_type`、`total_amount`、状态机字段 `status`、`version`、`current_node`、`submit_time` 等。
- `details`：费用明细，单据金额由明细实时汇总。
- `attachments`：附件元数据与模拟路径，支持 PDF / PNG / JPG，单文件不超过 10MB。
- `snapshots`：提交及重新提交时生成的不可变版本快照。
- `approvalInstances` / `approvalTasks` / `approvalOpinions`：审批实例、任务与意见。
- `riskAnalyses` / `riskItems` / `riskEvidences` / `parseResults`：风险结论、风险项、证据与附件解析结果。
- `operationLogs`：全流程审计日志。
- `reports`：风险审核报告，包含金额核对、供应商风险与人工复核记录。

单据状态：`draft → pending_approval → completed`，并支持 `returned`、`rejected` 分支；重新提交后 `version` 加一。

## 演示流程

1. 登录后进入工作台，从“新建单据”填写标题、费用项目与明细。
2. 上传 PDF / PNG / JPG 附件，保存草稿或提交审批。
3. 提交后自动生成快照、审批任务与风险分析，跳转单据详情查看风险报告。
4. 在审批中心选择单据，执行退回、驳回或通过；通过后流转至财务审核，最终完成并生成报告。
5. 在单据详情导出报告，或在报告中心查看历史报告、导出 Excel / PDF。
6. 侧边栏用户菜单可退出登录或重置演示数据。

数据持久化在浏览器 `localStorage`，键名 `finance-risk-audit-state-v1`。
