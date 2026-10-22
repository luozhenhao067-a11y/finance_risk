-- ============================================================
-- 财务单据智能风险审核系统 清空表脚本（可重复导入, v2）
-- ============================================================

USE `financial_risk_audit`;

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE `dict`;
TRUNCATE TABLE `vendor`;
TRUNCATE TABLE `expense_standard`;
TRUNCATE TABLE `report`;
TRUNCATE TABLE `notification`;
TRUNCATE TABLE `audit_log`;
TRUNCATE TABLE `approval_opinion`;
TRUNCATE TABLE `approval_task`;
TRUNCATE TABLE `approval_flow`;
TRUNCATE TABLE `risk_evidence`;
TRUNCATE TABLE `risk_item`;
TRUNCATE TABLE `risk_analysis`;
TRUNCATE TABLE `risk_rule`;
TRUNCATE TABLE `document_snapshot`;
TRUNCATE TABLE `attachment_parse_result`;
TRUNCATE TABLE `attachment`;
TRUNCATE TABLE `document_item`;
TRUNCATE TABLE `document`;
TRUNCATE TABLE `role_permission`;
TRUNCATE TABLE `user_role`;
TRUNCATE TABLE `permission`;
TRUNCATE TABLE `role`;
TRUNCATE TABLE `user`;
SET FOREIGN_KEY_CHECKS = 1;
