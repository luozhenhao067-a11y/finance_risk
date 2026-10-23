"""启动时幂等迁移。

1. document 增加 project / dept_id 列（契约 Document 结构要求，原表缺失）
2. approval_opinion.task_id 改可空（契约要求提交/撤回类意见 task_id=null）
3. 注入 AI 增强规则 R-11 / R-12（已存在则跳过）
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    ).scalar()
    return bool(row)


def _constraint_exists(conn, table: str, constraint: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = :t AND CONSTRAINT_NAME = :c"
        ),
        {"t": table, "c": constraint},
    ).scalar()
    return bool(row)


def _column_nullable(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    ).scalar()
    return (row or "NO").upper() == "YES"


AI_RULES = (
    {
        "code": "R-11",
        "name": "主体名称语义一致性",
        "type": "subject",
        "level": "high",
        "description": "语义比对合同乙方、发票抬头、付款对象等公司名称是否指向同一主体，支持简称/全称。",
        "threshold": None,
        "params": "AI 语义比对，兜底为名称归一化规则",
    },
    {
        "code": "R-12",
        "name": "消费异常智能检测",
        "type": "consumption",
        "level": "mid",
        "description": "结合单据金额、报销类型、历史均值与城市判断消费是否异常。",
        "threshold": 1.50,
        "params": "AI 综合判断，兜底阈值为历史均值 1.5 倍",
    },
)


def _seed_ai_rules(conn) -> None:
    for rule in AI_RULES:
        exists = conn.execute(
            text("SELECT COUNT(*) FROM risk_rule WHERE rule_code = :code"),
            {"code": rule["code"]},
        ).scalar()
        if exists:
            continue
        conn.execute(
            text(
                "INSERT INTO risk_rule "
                "(rule_code, rule_name, rule_type, risk_level, description, threshold, params, enabled, created_at) "
                "VALUES (:code, :name, :type, :level, :description, :threshold, :params, 1, NOW())"
            ),
            rule,
        )
        logger.info("migrate: AI rule %s seeded", rule["code"])


def run_migrations(engine: Engine) -> None:
    with engine.begin() as conn:
        if not _column_exists(conn, "document", "project"):
            conn.execute(text("ALTER TABLE `document` ADD COLUMN `project` varchar(100) NULL COMMENT '费用项目' AFTER `title`"))
            logger.info("migrate: document.project added")

        if not _column_exists(conn, "document", "dept_id"):
            conn.execute(text("ALTER TABLE `document` ADD COLUMN `dept_id` bigint unsigned NULL COMMENT '申请部门ID' AFTER `project`"))
            logger.info("migrate: document.dept_id added")

        if _constraint_exists(conn, "approval_opinion", "fk_opinion_task"):
            conn.execute(text("ALTER TABLE `approval_opinion` DROP FOREIGN KEY `fk_opinion_task`"))
            logger.info("migrate: approval_opinion.fk_opinion_task dropped")

        if not _column_nullable(conn, "approval_opinion", "task_id"):
            conn.execute(text("ALTER TABLE `approval_opinion` MODIFY COLUMN `task_id` bigint unsigned NULL COMMENT '审批任务ID(提交/撤回类为NULL)'"))
            logger.info("migrate: approval_opinion.task_id made nullable")

        _seed_ai_rules(conn)
