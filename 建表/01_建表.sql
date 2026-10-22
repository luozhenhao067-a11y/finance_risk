-- ============================================================
-- 财务单据智能风险审核系统 建表脚本 (v2, 对齐 Spec/design/契约)
-- 数据库: MySQL 8.x   字符集: utf8mb4
-- 23 张表: RBAC(5) + 单据(5) + 快照(1) + 风险(5) + 审批(3) + 日志/通知/报告(3) + 配置(3)
-- 2026-10-22 由真库 SHOW CREATE TABLE 生成
-- ============================================================

CREATE DATABASE IF NOT EXISTS `financial_risk_audit`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `financial_risk_audit`;

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE `user` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录名',
  `password` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码(BCrypt)',
  `real_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '真实姓名',
  `email` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '邮箱',
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '手机号',
  `department` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '部门',
  `position` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '职位',
  `status` tinyint NOT NULL DEFAULT '1' COMMENT '1启用 0禁用',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

CREATE TABLE `role` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '角色ID',
  `role_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '角色编码',
  `role_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '角色名称',
  `description` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '角色描述',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_role_code` (`role_code`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

CREATE TABLE `permission` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '权限ID',
  `perm_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '权限编码',
  `perm_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '权限名称',
  `perm_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'menu' COMMENT 'menu/button/api',
  `parent_id` bigint unsigned DEFAULT NULL COMMENT '父权限ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_perm_code` (`perm_code`),
  KEY `idx_parent` (`parent_id`),
  CONSTRAINT `fk_permission_parent` FOREIGN KEY (`parent_id`) REFERENCES `permission` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限表';

CREATE TABLE `user_role` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` bigint unsigned NOT NULL COMMENT '用户ID',
  `role_id` bigint unsigned NOT NULL COMMENT '角色ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '绑定时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_role` (`user_id`,`role_id`),
  KEY `fk_ur_role` (`role_id`),
  CONSTRAINT `fk_ur_role` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ur_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

CREATE TABLE `role_permission` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键',
  `role_id` bigint unsigned NOT NULL COMMENT '角色ID',
  `permission_id` bigint unsigned NOT NULL COMMENT '权限ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_role_perm` (`role_id`,`permission_id`),
  KEY `fk_rp_perm` (`permission_id`),
  CONSTRAINT `fk_rp_perm` FOREIGN KEY (`permission_id`) REFERENCES `permission` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rp_role` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=43 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色权限关联表';

CREATE TABLE `document` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '单据ID',
  `doc_no` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '单据编号，如FY20261021-001',
  `doc_type` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '单据类型:travel/expense/entertainment/purchase/contract/training/meeting',
  `doc_type_name` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '单据类型名称',
  `title` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '单据标题',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'draft' COMMENT 'draft/submitted/analyzing/pending_approval/returned/rejected/approved/completed',
  `version` int NOT NULL DEFAULT '1' COMMENT '单据版本,初值1,退回重提+1,审批乐观锁依据',
  `current_node` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前审批节点名,draft/returned/rejected为NULL',
  `risk_level` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'none' COMMENT '冗余:整体风险等级 none/low/mid/high',
  `risk_count` int NOT NULL DEFAULT '0' COMMENT '冗余:风险项数量',
  `delete_flag` tinyint NOT NULL DEFAULT '0' COMMENT '逻辑删除 0正常 1删除',
  `total_amount` decimal(14,2) NOT NULL DEFAULT '0.00' COMMENT '单据总金额',
  `currency` char(3) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'CNY' COMMENT '币种',
  `applicant_id` bigint unsigned NOT NULL COMMENT '申请人ID',
  `department` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '申请部门',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '单据说明',
  `submit_time` datetime DEFAULT NULL COMMENT '提交时间',
  `finish_time` datetime DEFAULT NULL COMMENT '办结时间',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_doc_no` (`doc_no`),
  KEY `idx_applicant` (`applicant_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_doc_applicant` FOREIGN KEY (`applicant_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=41 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单据主表';

CREATE TABLE `document_item` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '明细ID',
  `document_id` bigint unsigned NOT NULL COMMENT '单据ID',
  `item_no` int NOT NULL COMMENT '明细序号',
  `expense_type` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '费用类型',
  `expense_date` date NOT NULL COMMENT '费用发生日期',
  `amount` decimal(14,2) NOT NULL COMMENT '金额',
  `invoice_no` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '发票号/合同号,报销类必填,借款单为—',
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '费用说明',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_doc_item` (`document_id`),
  CONSTRAINT `fk_item_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=132 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单据费用明细表';

CREATE TABLE `attachment` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '附件ID',
  `document_id` bigint unsigned NOT NULL COMMENT '单据ID',
  `file_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件名',
  `file_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件类型',
  `file_size` int NOT NULL COMMENT '文件大小(KB)',
  `file_url` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件路径',
  `parse_status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'parsing' COMMENT 'parsing/parsed/failed',
  `upload_by` bigint unsigned NOT NULL COMMENT '上传人ID',
  `upload_time` datetime NOT NULL COMMENT '上传时间',
  PRIMARY KEY (`id`),
  KEY `idx_att_doc` (`document_id`),
  KEY `fk_att_uploader` (`upload_by`),
  CONSTRAINT `fk_att_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_att_uploader` FOREIGN KEY (`upload_by`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=113 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单据附件表';

CREATE TABLE `attachment_parse_result` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '解析结果ID',
  `attachment_id` bigint unsigned NOT NULL COMMENT '附件ID',
  `parse_status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'success/failed',
  `parse_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'ocr/structured',
  `result_json` json DEFAULT NULL COMMENT '解析结果JSON',
  `confidence` decimal(5,2) DEFAULT NULL COMMENT '置信度',
  `error_msg` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '失败原因',
  `parse_time` datetime NOT NULL COMMENT '解析时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_parse_attachment` (`attachment_id`),
  CONSTRAINT `fk_parse_att` FOREIGN KEY (`attachment_id`) REFERENCES `attachment` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=113 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='附件解析结果表';

CREATE TABLE `document_snapshot` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '快照ID',
  `document_id` bigint unsigned NOT NULL COMMENT '单据ID',
  `version` int NOT NULL DEFAULT '1' COMMENT '单据版本',
  `payload` json NOT NULL COMMENT '提交时点全量快照 {document,details[],attachments[]}',
  `immutable` tinyint NOT NULL DEFAULT '1' COMMENT '恒为1,只读不可变,无UPDATE接口',
  `created_at` datetime NOT NULL COMMENT '快照时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_snapshot_doc_version` (`document_id`,`version`),
  KEY `idx_snapshot_doc` (`document_id`),
  CONSTRAINT `fk_snapshot_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单据不可变快照表';

CREATE TABLE `risk_rule` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '规则ID',
  `rule_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '规则编码',
  `rule_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '规则名称',
  `rule_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '规则类型:invoice/amount/supplier/price/attachment/travel/keyword/history/budget/scope/purchase',
  `risk_level` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '风险等级:low/medium/high',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '规则描述',
  `threshold` decimal(14,2) DEFAULT NULL COMMENT '阈值',
  `params` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '规则参数(JSON或文本),如 容差 ¥0.01',
  `enabled` tinyint NOT NULL DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_rule_code` (`rule_code`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险规则表';

CREATE TABLE `risk_analysis` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '分析ID',
  `document_id` bigint unsigned NOT NULL COMMENT '单据ID',
  `doc_version` int NOT NULL DEFAULT '1' COMMENT '对应单据版本,历史按版本保留',
  `analysis_no` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '分析编号',
  `risk_score` int NOT NULL DEFAULT '0' COMMENT '风险评分0-100',
  `risk_level` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'low' COMMENT '风险等级: low/mid/high',
  `overall_level` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '整体等级 none/low/mid/high',
  `high_count` int NOT NULL DEFAULT '0' COMMENT '高风险项数',
  `mid_count` int NOT NULL DEFAULT '0' COMMENT '中风险项数',
  `low_count` int NOT NULL DEFAULT '0' COMMENT '低风险项数',
  `recommendation` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'pass/supplement/manual_review/reject_suggest',
  `recommendation_label` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '建议通过/补充材料/人工复核/建议驳回',
  `trigger_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'auto' COMMENT 'auto/resubmit/manual',
  `triggered_by` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'manual 时记录触发人',
  `analyzed_at` datetime DEFAULT NULL COMMENT '分析完成时间',
  `risk_count` int NOT NULL DEFAULT '0' COMMENT '风险项数量',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending/analyzing/completed/failed',
  `analyzer` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '分析引擎',
  `start_time` datetime NOT NULL COMMENT '开始时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  `summary` text COLLATE utf8mb4_unicode_ci COMMENT '分析摘要',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_analysis_doc_version` (`document_id`,`doc_version`),
  CONSTRAINT `fk_analysis_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险分析主表';

CREATE TABLE `risk_item` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '风险项ID',
  `analysis_id` bigint unsigned NOT NULL COMMENT '分析ID',
  `rule_id` bigint unsigned NOT NULL COMMENT '命中规则ID',
  `risk_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '风险类型',
  `risk_level` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '风险等级: low/mid/high',
  `risk_desc` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '风险描述',
  `score` int NOT NULL COMMENT '风险项分值',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'open' COMMENT 'open/handled/dismissed',
  `handled_by` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '处理人姓名',
  `handled_at` datetime DEFAULT NULL COMMENT '处理时间',
  `handle_opinion` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '处理意见',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_ritem_analysis` (`analysis_id`),
  KEY `idx_ritem_rule` (`rule_id`),
  CONSTRAINT `fk_ritem_analysis` FOREIGN KEY (`analysis_id`) REFERENCES `risk_analysis` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ritem_rule` FOREIGN KEY (`rule_id`) REFERENCES `risk_rule` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险项表';

CREATE TABLE `risk_evidence` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '证据ID',
  `risk_item_id` bigint unsigned NOT NULL COMMENT '风险项ID',
  `evidence_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'evidence类型:attachment/parse_result/text',
  `evidence_content` text COLLATE utf8mb4_unicode_ci COMMENT '证据内容',
  `source` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '证据来源',
  `attachment_id` bigint unsigned DEFAULT NULL COMMENT '关联附件ID',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_evidence_item` (`risk_item_id`),
  KEY `fk_evidence_att` (`attachment_id`),
  CONSTRAINT `fk_evidence_att` FOREIGN KEY (`attachment_id`) REFERENCES `attachment` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_evidence_item` FOREIGN KEY (`risk_item_id`) REFERENCES `risk_item` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险证据表';

CREATE TABLE `approval_flow` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '审批流ID',
  `document_id` bigint unsigned NOT NULL COMMENT '单据ID',
  `flow_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '审批流名称',
  `current_node` int NOT NULL DEFAULT '1' COMMENT '当前节点',
  `total_nodes` int NOT NULL DEFAULT '3' COMMENT '总节点数',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'running' COMMENT 'running/completed/returned/rejected/cancelled',
  `start_time` datetime NOT NULL COMMENT '启动时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_flow_doc` (`document_id`),
  CONSTRAINT `fk_flow_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批流表';

CREATE TABLE `approval_task` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '任务ID',
  `flow_id` bigint unsigned NOT NULL COMMENT '审批流ID',
  `document_id` bigint unsigned NOT NULL COMMENT '单据ID',
  `node_no` int NOT NULL COMMENT '节点序号',
  `node_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '节点名称',
  `approver_id` bigint unsigned NOT NULL COMMENT '审批人ID',
  `task_status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending/done/cancelled',
  `action` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'approved/returned/rejected',
  `assign_time` datetime NOT NULL COMMENT '任务到达时间',
  `handle_time` datetime DEFAULT NULL COMMENT '处理时间',
  PRIMARY KEY (`id`),
  KEY `idx_task_flow` (`flow_id`),
  KEY `idx_task_doc` (`document_id`),
  KEY `idx_task_approver` (`approver_id`),
  CONSTRAINT `fk_task_approver` FOREIGN KEY (`approver_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_task_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_task_flow` FOREIGN KEY (`flow_id`) REFERENCES `approval_flow` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=103 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批任务表';

CREATE TABLE `approval_opinion` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '意见ID',
  `task_id` bigint unsigned NOT NULL COMMENT '审批任务ID',
  `opinion` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '审批意见',
  `action` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'approve/return/reject;提交类 submit/resubmit/withdraw 由服务追加',
  `node` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '审批节点名',
  `create_by` bigint unsigned NOT NULL COMMENT '审批人ID',
  `create_time` datetime NOT NULL COMMENT '审批时间',
  PRIMARY KEY (`id`),
  KEY `fk_opinion_user` (`create_by`),
  KEY `idx_opinion_task` (`task_id`),
  CONSTRAINT `fk_opinion_task` FOREIGN KEY (`task_id`) REFERENCES `approval_task` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_opinion_user` FOREIGN KEY (`create_by`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=83 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批意见表';

CREATE TABLE `audit_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '日志ID',
  `document_id` bigint unsigned DEFAULT NULL COMMENT '单据ID',
  `user_id` bigint unsigned DEFAULT NULL COMMENT '操作人ID',
  `action` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作类型',
  `role` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作人角色',
  `trace_id` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '全链路追踪ID',
  `user_agent` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '客户端UA',
  `detail` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作详情',
  `ip` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作IP',
  `create_time` datetime NOT NULL COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `idx_log_doc` (`document_id`),
  KEY `idx_log_user` (`user_id`),
  CONSTRAINT `fk_log_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_log_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=229 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审计日志表';

CREATE TABLE `notification` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '通知ID',
  `user_id` bigint unsigned NOT NULL COMMENT '接收人ID',
  `document_id` bigint unsigned DEFAULT NULL COMMENT '单据ID',
  `title` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '通知标题',
  `content` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '通知内容',
  `type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'approval' COMMENT 'approval/risk/system',
  `is_read` tinyint NOT NULL DEFAULT '0' COMMENT '是否已读',
  `create_time` datetime NOT NULL COMMENT '通知时间',
  PRIMARY KEY (`id`),
  KEY `idx_notif_user` (`user_id`),
  KEY `idx_notif_doc` (`document_id`),
  CONSTRAINT `fk_notif_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_notif_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=36 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通知表';

CREATE TABLE `report` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '报告ID',
  `document_id` bigint unsigned NOT NULL COMMENT '单据ID',
  `report_no` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '报告编号',
  `risk_score` int NOT NULL DEFAULT '0' COMMENT '风险评分',
  `risk_level` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'low' COMMENT '风险等级:low/medium/high',
  `conclusion` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '审核结论',
  `summary` text COLLATE utf8mb4_unicode_ci COMMENT '报告摘要',
  `suggestion` text COLLATE utf8mb4_unicode_ci COMMENT '管理建议',
  `content` json DEFAULT NULL COMMENT '报告8部分内容JSON',
  `export_file_path` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '导出文件路径',
  `report_status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'generated' COMMENT 'generated/published',
  `create_by` bigint unsigned NOT NULL COMMENT '报告生成人ID',
  `create_time` datetime NOT NULL COMMENT '生成时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_doc` (`document_id`),
  KEY `fk_report_user` (`create_by`),
  CONSTRAINT `fk_report_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_report_user` FOREIGN KEY (`create_by`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险审核报告表';

CREATE TABLE `expense_standard` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '标准ID',
  `category` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '费用类别:住宿/交通/餐饮',
  `city` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '城市,通用=不限城市',
  `position_level` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '职级:员工/经理',
  `amount` decimal(14,2) NOT NULL COMMENT '标准金额',
  `unit` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '晚' COMMENT '计量:晚/天/人',
  `enabled` tinyint NOT NULL DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_std` (`category`,`city`,`position_level`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='费用报销标准表';

CREATE TABLE `vendor` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '供应商ID',
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '供应商名称',
  `score` int DEFAULT NULL COMMENT '评分0-100',
  `risk_level` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'low' COMMENT '风险等级 low/mid/high',
  `blacklist` tinyint NOT NULL DEFAULT '0' COMMENT '黑名单 0否 1是',
  `established_date` date DEFAULT NULL COMMENT '成立日期',
  `note` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备注(经营异常等)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '建档时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_vendor_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='供应商档案表';

CREATE TABLE `dict` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '字典ID',
  `dict_type` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '字典类型: doc_type/expense_type',
  `dict_label` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '显示名',
  `dict_value` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '存储值',
  `scope` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '适用单据类型,空=全部',
  `sort` int NOT NULL DEFAULT '0' COMMENT '排序',
  `enabled` tinyint NOT NULL DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dict` (`dict_type`,`scope`,`dict_value`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字典表';

SET FOREIGN_KEY_CHECKS = 1;
