-- 迁移补丁 v2b: 承接 migrate_v2.sql 失败点(section 11)之后的部分
USE `financial_risk_audit`;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------- 11. approval_opinion: 时间线模型 ----------
ALTER TABLE `approval_opinion` DROP FOREIGN KEY `fk_opinion_task`;
ALTER TABLE `approval_opinion` DROP INDEX `uk_opinion_task`;
ALTER TABLE `approval_opinion`
  CHANGE `opinion_type` `action` VARCHAR(20) NOT NULL COMMENT 'approve/return/reject;提交类 submit/resubmit/withdraw 由服务追加',
  ADD COLUMN `node` VARCHAR(50) DEFAULT NULL COMMENT '审批节点名' AFTER `action`,
  ADD KEY `idx_opinion_task` (`task_id`);
ALTER TABLE `approval_opinion`
  ADD CONSTRAINT `fk_opinion_task` FOREIGN KEY (`task_id`) REFERENCES `approval_task` (`id`) ON DELETE CASCADE;

UPDATE `approval_opinion` SET `action` = 'approve' WHERE `action` = 'agree';
UPDATE `approval_opinion` o JOIN `approval_task` t ON t.`id` = o.`task_id` SET o.`node` = t.`node_name`;

-- ---------- 12. audit_log: 动作中文化 + 追踪字段 ----------
ALTER TABLE `audit_log`
  ADD COLUMN `role` VARCHAR(50) DEFAULT NULL COMMENT '操作人角色' AFTER `action`,
  ADD COLUMN `trace_id` VARCHAR(40) DEFAULT NULL COMMENT '全链路追踪ID' AFTER `role`,
  ADD COLUMN `user_agent` VARCHAR(300) DEFAULT NULL COMMENT '客户端UA' AFTER `trace_id`;

UPDATE `audit_log` SET `action` = CASE `action`
  WHEN 'CREATE_DOC' THEN '创建单据'
  WHEN 'SUBMIT' THEN '提交审批'
  WHEN 'RISK_ANALYSIS_DONE' THEN '风险分析完成'
  WHEN 'APPROVE' THEN '审批通过'
  WHEN 'RETURN' THEN '退回单据'
  WHEN 'REJECT' THEN '驳回单据'
  WHEN 'COMPLETE' THEN '审批完成'
  WHEN 'REPORT_GENERATED' THEN '生成报告'
  WHEN 'UPLOAD_ATTACHMENT' THEN '上传附件'
  ELSE `action` END;

UPDATE `audit_log` l LEFT JOIN `user` u ON u.`id` = l.`user_id`
  SET l.`role` = COALESCE(u.`position`, '系统');

-- ---------- 13. report: 8 部分 content + 导出路径 ----------
ALTER TABLE `report`
  ADD COLUMN `content` JSON DEFAULT NULL COMMENT '报告8部分内容JSON' AFTER `suggestion`,
  ADD COLUMN `export_file_path` VARCHAR(500) DEFAULT NULL COMMENT '导出文件路径' AFTER `content`;

UPDATE `report`
  SET `report_no` = CONCAT('RPT', SUBSTRING(`report_no`, 3, 9), '-', LPAD(SUBSTRING_INDEX(`report_no`, '-', -1), 4, '0'));

-- ---------- 14. 新表: 快照 / 费用标准 / 供应商 / 字典 ----------
CREATE TABLE `document_snapshot` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '快照ID',
  `document_id` BIGINT UNSIGNED NOT NULL COMMENT '单据ID',
  `version` INT NOT NULL DEFAULT 1 COMMENT '单据版本',
  `payload` JSON NOT NULL COMMENT '提交时点全量快照 {document,details[],attachments[]}',
  `immutable` TINYINT NOT NULL DEFAULT 1 COMMENT '恒为1,只读不可变,无UPDATE接口',
  `created_at` DATETIME NOT NULL COMMENT '快照时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_snapshot_doc_version` (`document_id`, `version`),
  KEY `idx_snapshot_doc` (`document_id`),
  CONSTRAINT `fk_snapshot_doc` FOREIGN KEY (`document_id`) REFERENCES `document` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单据不可变快照表';

CREATE TABLE `expense_standard` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '标准ID',
  `category` VARCHAR(20) NOT NULL COMMENT '费用类别:住宿/交通/餐饮',
  `city` VARCHAR(30) NOT NULL COMMENT '城市,通用=不限城市',
  `position_level` VARCHAR(20) NOT NULL COMMENT '职级:员工/经理',
  `amount` DECIMAL(14,2) NOT NULL COMMENT '标准金额',
  `unit` VARCHAR(10) NOT NULL DEFAULT '晚' COMMENT '计量:晚/天/人',
  `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_std` (`category`, `city`, `position_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='费用报销标准表';

CREATE TABLE `vendor` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '供应商ID',
  `name` VARCHAR(100) NOT NULL COMMENT '供应商名称',
  `score` INT DEFAULT NULL COMMENT '评分0-100',
  `risk_level` VARCHAR(10) NOT NULL DEFAULT 'low' COMMENT '风险等级 low/mid/high',
  `blacklist` TINYINT NOT NULL DEFAULT 0 COMMENT '黑名单 0否 1是',
  `established_date` DATE DEFAULT NULL COMMENT '成立日期',
  `note` VARCHAR(500) DEFAULT NULL COMMENT '备注(经营异常等)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '建档时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_vendor_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='供应商档案表';

CREATE TABLE `dict` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '字典ID',
  `dict_type` VARCHAR(30) NOT NULL COMMENT '字典类型: doc_type/expense_type',
  `dict_label` VARCHAR(50) NOT NULL COMMENT '显示名',
  `dict_value` VARCHAR(50) NOT NULL COMMENT '存储值',
  `sort` INT NOT NULL DEFAULT 0 COMMENT '排序',
  `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dict` (`dict_type`, `dict_value`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字典表';

SET FOREIGN_KEY_CHECKS = 1;
