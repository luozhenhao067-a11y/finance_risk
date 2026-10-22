-- ============================================================
-- 财务单据智能风险审核系统 真库迁移脚本 v2
-- 目标: 现有 19 表模型对齐规划(Spec/design/契约),保留全部测试数据
-- 执行: mysql -uroot -p financial_risk_audit < migrate_v2.sql
-- 2026-10-22
-- ============================================================

USE `financial_risk_audit`;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------- 1. user: 密码统一 Root@123456 (BCrypt) ----------
UPDATE `user` SET `password` = '$2b$10$gGmjqQFVhyhYydi8sQiP1OitYJ.ME9ZElL5KhRzaUtUGNO4UdyZV6';

-- ---------- 2. document: 状态机/乐观锁/冗余字段 ----------
ALTER TABLE `document`
  MODIFY `status` VARCHAR(20) NOT NULL DEFAULT 'draft'
    COMMENT 'draft/submitted/analyzing/pending_approval/returned/rejected/approved/completed',
  ADD COLUMN `version` INT NOT NULL DEFAULT 1 COMMENT '单据版本,初值1,退回重提+1,审批乐观锁依据' AFTER `status`,
  ADD COLUMN `current_node` VARCHAR(50) DEFAULT NULL COMMENT '当前审批节点名,draft/returned/rejected为NULL' AFTER `version`,
  ADD COLUMN `risk_level` VARCHAR(10) NOT NULL DEFAULT 'none' COMMENT '冗余:整体风险等级 none/low/mid/high' AFTER `current_node`,
  ADD COLUMN `risk_count` INT NOT NULL DEFAULT 0 COMMENT '冗余:风险项数量' AFTER `risk_level`,
  ADD COLUMN `delete_flag` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除 0正常 1删除' AFTER `risk_count`;

-- doc_type 英文码 -> 中文 5 类
UPDATE `document` SET `doc_type` = CASE `doc_type`
  WHEN 'travel' THEN '差旅费报销'
  WHEN 'expense' THEN '费用报销'
  WHEN 'entertainment' THEN '费用报销'
  WHEN 'purchase' THEN '采购付款'
  WHEN 'contract' THEN '合同付款'
  WHEN 'training' THEN '费用报销'
  WHEN 'meeting' THEN '费用报销'
  ELSE `doc_type` END;

UPDATE `document` SET `doc_type_name` = CASE `doc_type_name`
  WHEN '差旅报销' THEN '差旅费报销'
  WHEN '日常费用报销' THEN '费用报销'
  WHEN '业务招待' THEN '费用报销'
  WHEN '会议费报销' THEN '费用报销'
  WHEN '培训费报销' THEN '费用报销'
  ELSE `doc_type_name` END;

-- ---------- 3. document_item: 发票号/合同号 ----------
ALTER TABLE `document_item`
  ADD COLUMN `invoice_no` VARCHAR(32) DEFAULT NULL COMMENT '发票号/合同号,报销类必填,借款单为—' AFTER `amount`;

UPDATE `document_item` di JOIN `document` d ON d.`id` = di.`document_id`
  SET di.`invoice_no` = CONCAT('INV-', LPAD(di.`id`, 8, '0'))
  WHERE d.`doc_type` IN ('差旅费报销', '费用报销');

UPDATE `document_item` di JOIN `document` d ON d.`id` = di.`document_id`
  SET di.`invoice_no` = CONCAT('HT-2026-', LPAD(di.`id`, 4, '0'))
  WHERE d.`doc_type` IN ('采购付款', '合同付款');

-- ---------- 4. attachment / attachment_parse_result: 解析状态 ----------
ALTER TABLE `attachment`
  ADD COLUMN `parse_status` VARCHAR(20) NOT NULL DEFAULT 'parsing'
    COMMENT 'parsing/parsed/failed' AFTER `file_url`;

UPDATE `attachment` a LEFT JOIN `attachment_parse_result` p ON p.`attachment_id` = a.`id`
  SET a.`parse_status` = CASE p.`parse_status` WHEN 'success' THEN 'parsed' WHEN 'failed' THEN 'failed' ELSE 'parsing' END;

UPDATE `attachment_parse_result` SET `parse_status` = 'parsed' WHERE `parse_status` = 'success';

-- ---------- 5. risk_rule: 替换为 R-01~R-10 + R-EXT ----------
ALTER TABLE `risk_rule`
  ADD COLUMN `params` VARCHAR(200) DEFAULT NULL COMMENT '规则参数(JSON或文本),如 容差 ¥0.01' AFTER `threshold`;

-- 先重映射 risk_item.rule_id, 再换规则行
UPDATE `risk_item` SET `rule_id` = CASE `rule_id`
  WHEN 1 THEN 10      -- 重复发票 -> R-10 重复票据
  WHEN 2 THEN 11      -- 发票日期异常 -> R-EXT
  WHEN 3 THEN 5       -- 金额超标准 -> R-05 费用标准
  WHEN 4 THEN 11      -- 拆单 -> R-EXT
  WHEN 5 THEN 8       -- 供应商黑名单 -> R-08 供应商风险
  WHEN 6 THEN 6       -- 价格异常 -> R-06 市场价格偏离
  WHEN 7 THEN 9       -- 附件缺失 -> R-09 附件完整性
  WHEN 8 THEN 11      -- 发票真伪 -> R-EXT
  WHEN 9 THEN 7       -- 行程重叠 -> R-07 消费异常
  WHEN 10 THEN 11     -- 敏感关键词 -> R-EXT
  ELSE 11 END;

DELETE FROM `risk_rule`;
ALTER TABLE `risk_rule` AUTO_INCREMENT = 1;

INSERT INTO `risk_rule` (`id`, `rule_code`, `rule_name`, `rule_type`, `risk_level`, `description`, `threshold`, `params`, `enabled`, `created_at`) VALUES
(1,  'R-01',  '金额一致性',     'amount',     'high',     '单据金额 vs 明细合计 vs 发票解析合计,差额超容差命中', 0.01,  '容差 ¥0.01', 1, '2026-05-01 09:00:00'),
(2,  'R-02',  '明细合计校验',   'amount',     'blocking', '提交强校验:合计与明细不一致直接拦截,不走风险项',    NULL, '提交强校验', 1, '2026-05-01 09:00:00'),
(3,  'R-03',  '合同与付款一致性', 'amount',    'high',     '付款金额 vs 合同应付金额/付款节点',                  0.10,  '付款比例偏差阈值 10%', 1, '2026-05-01 09:00:00'),
(4,  'R-04',  '批量付款校验',   'purchase',   'high',     '批量付款收款方重复检测',                            NULL, '收款方重复检测', 0, '2026-05-01 09:00:00'),
(5,  'R-05',  '费用标准',       'travel',     'mid',      '住宿/交通/餐饮 vs 城市/职级/晚数标准',               NULL, '按城市/职级/晚数', 1, '2026-05-01 09:00:00'),
(6,  'R-06',  '市场价格偏离',   'price',      'mid',      '采购价格偏离市场均价',                              0.10,  '偏离阈值 10%', 1, '2026-05-01 09:00:00'),
(7,  'R-07',  '消费异常',       'travel',     'mid',      '节假日/连号发票/单日多票等异常消费',                NULL, '节假日/连号发票/单日多票', 0, '2026-05-01 09:00:00'),
(8,  'R-08',  '供应商风险',     'supplier',   'mid',      '供应商成立年限/黑名单/经营异常',                    NULL, '成立年限 < 12 个月', 1, '2026-05-01 09:00:00'),
(9,  'R-09',  '附件完整性',     'attachment', 'low',      '必需附件/要素齐全/解析置信度',                      85.00, '置信度阈值 85%', 1, '2026-05-01 09:00:00'),
(10, 'R-10',  '重复票据',       'invoice',    'high',     '发票号与历史单据比对命中',                          NULL, '历史单据比对', 1, '2026-05-01 09:00:00'),
(11, 'R-EXT', '扩展规则',       'keyword',    'medium',   '发票日期异常/拆单/发票真伪/敏感关键词/重复报销/超预算/范围外/采购未审批等扩展规则', NULL, '扩展规则,按需启用', 1, '2026-05-01 09:00:00');

-- ---------- 6. risk_item: 等级与处理字段 ----------
ALTER TABLE `risk_item`
  MODIFY `risk_level` VARCHAR(10) NOT NULL COMMENT '风险等级: low/mid/high',
  MODIFY `status` VARCHAR(20) NOT NULL DEFAULT 'open' COMMENT 'open/handled/dismissed',
  ADD COLUMN `handled_by` VARCHAR(50) DEFAULT NULL COMMENT '处理人姓名' AFTER `status`,
  ADD COLUMN `handled_at` DATETIME DEFAULT NULL COMMENT '处理时间' AFTER `handled_by`,
  ADD COLUMN `handle_opinion` VARCHAR(500) DEFAULT NULL COMMENT '处理意见' AFTER `handled_at`;

UPDATE `risk_item` SET `risk_level` = 'mid' WHERE `risk_level` = 'medium';

UPDATE `risk_item`
  SET `status` = 'handled', `handled_by` = '王芳', `handled_at` = `created_at`, `handle_opinion` = '经人工复核确认风险成立'
  WHERE `status` = 'confirmed';

UPDATE `risk_item`
  SET `handled_by` = '王芳', `handled_at` = `created_at`, `handle_opinion` = '经人工复核予以排除'
  WHERE `status` = 'dismissed';

-- ---------- 7. risk_analysis: 版本隔离 + 等级/建议 ----------
ALTER TABLE `risk_analysis`
  DROP INDEX `uk_analysis_doc`,
  MODIFY `risk_level` VARCHAR(10) NOT NULL DEFAULT 'low' COMMENT '风险等级: low/mid/high',
  ADD COLUMN `doc_version` INT NOT NULL DEFAULT 1 COMMENT '对应单据版本,历史按版本保留' AFTER `document_id`,
  ADD COLUMN `overall_level` VARCHAR(10) DEFAULT NULL COMMENT '整体等级 none/low/mid/high' AFTER `risk_level`,
  ADD COLUMN `high_count` INT NOT NULL DEFAULT 0 COMMENT '高风险项数' AFTER `overall_level`,
  ADD COLUMN `mid_count` INT NOT NULL DEFAULT 0 COMMENT '中风险项数' AFTER `high_count`,
  ADD COLUMN `low_count` INT NOT NULL DEFAULT 0 COMMENT '低风险项数' AFTER `mid_count`,
  ADD COLUMN `recommendation` VARCHAR(20) DEFAULT NULL COMMENT 'pass/supplement/manual_review/reject_suggest' AFTER `low_count`,
  ADD COLUMN `recommendation_label` VARCHAR(20) DEFAULT NULL COMMENT '建议通过/补充材料/人工复核/建议驳回' AFTER `recommendation`,
  ADD COLUMN `trigger_type` VARCHAR(20) NOT NULL DEFAULT 'auto' COMMENT 'auto/resubmit/manual' AFTER `recommendation_label`,
  ADD COLUMN `triggered_by` VARCHAR(50) DEFAULT NULL COMMENT 'manual 时记录触发人' AFTER `trigger_type`,
  ADD COLUMN `analyzed_at` DATETIME DEFAULT NULL COMMENT '分析完成时间' AFTER `triggered_by`,
  ADD UNIQUE KEY `uk_analysis_doc_version` (`document_id`, `doc_version`);

UPDATE `risk_analysis`
  SET `risk_level` = CASE `risk_level` WHEN 'high' THEN 'high' WHEN 'medium' THEN 'mid' ELSE 'low' END,
      `overall_level` = CASE `risk_level` WHEN 'high' THEN 'high' WHEN 'medium' THEN 'mid' ELSE 'low' END,
      `analyzed_at` = `end_time`,
      `trigger_type` = 'auto';

UPDATE `risk_analysis` a
  SET a.`high_count` = (SELECT COUNT(*) FROM `risk_item` i WHERE i.`analysis_id` = a.`id` AND i.`risk_level` = 'high'),
      a.`mid_count`  = (SELECT COUNT(*) FROM `risk_item` i WHERE i.`analysis_id` = a.`id` AND i.`risk_level` = 'mid'),
      a.`low_count`  = (SELECT COUNT(*) FROM `risk_item` i WHERE i.`analysis_id` = a.`id` AND i.`risk_level` = 'low');

UPDATE `risk_analysis`
  SET `recommendation` = CASE
        WHEN `overall_level` = 'high' THEN 'manual_review'
        WHEN `overall_level` = 'mid' THEN 'supplement'
        ELSE 'pass' END,
      `recommendation_label` = CASE
        WHEN `overall_level` = 'high' THEN '人工复核'
        WHEN `overall_level` = 'mid' THEN '补充材料'
        ELSE '建议通过' END;

-- ---------- 8. document: 冗余回写 + current_node ----------
UPDATE `document` d JOIN `risk_analysis` a ON a.`document_id` = d.`id`
  SET d.`risk_level` = a.`overall_level`, d.`risk_count` = a.`risk_count`;

UPDATE `document` d
  SET d.`current_node` = (
    SELECT t.`node_name` FROM `approval_task` t
    WHERE t.`document_id` = d.`id` AND t.`task_status` = 'pending'
    ORDER BY t.`node_no` LIMIT 1)
  WHERE d.`status` = 'pending_approval';

UPDATE `document` SET `current_node` = '审批完成' WHERE `status` = 'completed';

-- ---------- 9. approval_flow: 状态枚举对齐 ----------
UPDATE `approval_flow` SET `status` = 'completed' WHERE `status` = 'passed';
ALTER TABLE `approval_flow`
  MODIFY `status` VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT 'running/completed/returned/rejected/cancelled';

-- ---------- 10. approval_task: 状态+动作 ----------
ALTER TABLE `approval_task`
  MODIFY `task_status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/done/cancelled',
  ADD COLUMN `action` VARCHAR(20) DEFAULT NULL COMMENT 'approved/returned/rejected' AFTER `task_status`;

UPDATE `approval_task` SET `task_status` = 'done', `action` = 'approved' WHERE `task_status` = 'approved';
UPDATE `approval_task` SET `task_status` = 'done', `action` = 'rejected' WHERE `task_status` = 'rejected';
UPDATE `approval_task` SET `task_status` = 'done', `action` = 'returned' WHERE `task_status` = 'returned';

-- 流程已结束单据的残留 pending 任务置 cancelled
UPDATE `approval_task` t JOIN `document` d ON d.`id` = t.`document_id`
  SET t.`task_status` = 'cancelled'
  WHERE t.`task_status` = 'pending' AND d.`status` IN ('returned', 'rejected', 'completed');

-- ---------- 11. approval_opinion: 时间线模型 ----------
ALTER TABLE `approval_opinion`
  DROP INDEX `uk_opinion_task`,
  CHANGE `opinion_type` `action` VARCHAR(20) NOT NULL COMMENT 'approve/return/reject;提交类 submit/resubmit/withdraw 由服务追加',
  ADD COLUMN `node` VARCHAR(50) DEFAULT NULL COMMENT '审批节点名' AFTER `action`;

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
