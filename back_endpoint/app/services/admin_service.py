"""系统管理：用户、部门、风险规则。"""

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.core.errors import bad_request, not_found
from app.models import RiskRule, Role, User, UserRole
from app.services import log_service
from app.services.serializers import admin_user_out, rule_out
from app.utils.ids import dept_pseudo_id
from app.utils.pagination import page_out, paginate_scalars

LOGICAL_ORDER = {"ADMIN": 0, "FINANCE": 1, "DEPT_MANAGER": 2, "APPLICANT": 3}
DB_LEVEL = {"mid": "medium", "medium": "medium", "high": "high", "low": "low", "blocking": "blocking"}


def _roles_of(db: Session) -> dict[int, list[tuple[str, str]]]:
    rows = db.execute(
        select(UserRole.user_id, Role.role_code, Role.role_name)
        .join(Role, Role.id == UserRole.role_id)
        .order_by(Role.id)
    ).all()
    result: dict[int, list[tuple[str, str]]] = {}
    for user_id, code, name in rows:
        result.setdefault(user_id, []).append((code, name))
    return result


def users_page(db: Session, keyword: str | None, page: int, page_size: int) -> dict:
    stmt = select(User).order_by(User.id)
    text = (keyword or "").strip()
    if text:
        like = f"%{text}%"
        stmt = stmt.where(
            or_(User.username.like(like), User.real_name.like(like), User.department.like(like))
        )
    rows, total = paginate_scalars(db, stmt, page, page_size)
    roles = _roles_of(db)
    items = []
    for user in rows:
        user_roles = roles.get(user.id, [])
        role_name = "、".join(name for _, name in user_roles) or "申请人"
        items.append(admin_user_out(user, role_name))
        items[-1]["roles"] = [{"code": code, "name": name} for code, name in user_roles]
    return page_out(items, total, page, page_size)


def depts(db: Session) -> list[dict]:
    rows = db.execute(
        select(User.department, func.count(User.id))
        .where(User.status == 1, User.department.is_not(None))
        .group_by(User.department)
        .order_by(User.department)
    ).all()
    managers = db.execute(
        select(User.department, User.real_name)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.role_code == "dept_manager", User.status == 1)
        .order_by(User.id)
    ).all()
    manager_map: dict[str, str] = {}
    for department, name in managers:
        manager_map.setdefault(department, name)
    return [
        {
            "id": dept_pseudo_id(department),
            "name": department,
            "manager": manager_map.get(department, ""),
            "user_count": int(count),
        }
        for department, count in rows
    ]


def risk_rules(db: Session) -> list[dict]:
    rows = db.execute(select(RiskRule).order_by(RiskRule.id)).scalars().all()
    return [rule_out(row) for row in rows]


def update_rule(db: Session, auth: AuthUser, code: str, patch: dict) -> dict:
    rule = db.execute(select(RiskRule).where(RiskRule.rule_code == code)).scalar_one_or_none()
    if not rule:
        raise not_found("风险规则不存在", code=40404)

    changed: list[str] = []
    if "enabled" in patch and patch["enabled"] is not None:
        rule.enabled = 1 if bool(patch["enabled"]) else 0
        changed.append(f"enabled={bool(rule.enabled)}")
    if "threshold" in patch:
        value = patch["threshold"]
        if value is None:
            rule.threshold = None
        else:
            try:
                rule.threshold = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise bad_request("threshold 必须为数字") from None
        changed.append(f"threshold={value}")
    if "params" in patch:
        rule.params = (str(patch["params"]).strip() or None) if patch["params"] is not None else None
        changed.append("params")
    if "description" in patch:
        rule.description = (str(patch["description"]).strip() or None) if patch["description"] is not None else None
        changed.append("description")
    if "risk_level" in patch and patch["risk_level"]:
        level = str(patch["risk_level"]).lower()
        if level not in DB_LEVEL:
            raise bad_request("risk_level 不合法")
        rule.risk_level = DB_LEVEL[level]
        changed.append(f"risk_level={rule.risk_level}")

    if not changed:
        raise bad_request("没有可更新的字段")
    log_service.record(
        db, "规则配置", doc_id=None, user=auth,
        detail=f"更新风险规则 {rule.rule_code} {rule.rule_name}：{', '.join(changed)}",
    )
    db.commit()
    return rule_out(rule)
