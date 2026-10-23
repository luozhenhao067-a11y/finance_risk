-- 001 单据表补充字段 + 审批意见 task_id 可空
-- 说明：应用启动时由 app/migrate.py 幂等执行，本文件仅作变更留档。
-- 数据库：financial_risk_audit（MySQL 8，utf8mb4）

ALTER TABLE document
    ADD COLUMN project varchar(100) NULL COMMENT '费用项目' AFTER title,
    ADD COLUMN dept_id bigint unsigned NULL COMMENT '部门ID（无部门表，仅冗余）' AFTER project;

-- 契约要求提交/撤回意见的 task_id 为 NULL，需先删除外键
ALTER TABLE approval_opinion DROP FOREIGN KEY fk_opinion_task;
ALTER TABLE approval_opinion MODIFY COLUMN task_id bigint unsigned NULL COMMENT '审批任务ID，提交类意见为空';
