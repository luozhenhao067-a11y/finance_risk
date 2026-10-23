"""认证依赖：解析 Bearer token → 当前用户；角色守卫。"""

from dataclasses import dataclass, field

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, BizError, unauthorized
from app.core.security import decode_token
from app.database import get_db
from app.models import Permission, Role, RolePermission, User, UserRole

# 物理角色 → 逻辑角色
ROLE_MAP = {
    "admin": "ADMIN",
    "finance_manager": "FINANCE",
    "finance_staff": "FINANCE",
    "auditor": "FINANCE",
    "dept_manager": "DEPT_MANAGER",
    "employee": "APPLICANT",
}
LOGICAL_ROLE_NAME = {
    "ADMIN": "系统管理员",
    "FINANCE": "财务审核人",
    "DEPT_MANAGER": "部门负责人",
    "APPLICANT": "申请人",
}
_ROLE_PRIORITY = {"ADMIN": 4, "FINANCE": 3, "DEPT_MANAGER": 2, "APPLICANT": 1}


@dataclass
class AuthUser:
    id: int
    username: str
    real_name: str
    department: str | None
    position: str | None
    role_code: str  # 逻辑角色
    role_name: str
    physical_roles: list[str] = field(default_factory=list)
    perm_codes: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return self.role_code == "ADMIN"

    @property
    def is_finance(self) -> bool:
        return self.role_code == "FINANCE"

    @property
    def is_finance_or_admin(self) -> bool:
        return self.role_code in ("FINANCE", "ADMIN")

    @property
    def avatar(self) -> str:
        return self.real_name[:1] if self.real_name else "U"

    def to_dict(self) -> dict:
        from app.utils.ids import dept_pseudo_id

        return {
            "id": str(self.id),
            "name": self.real_name,
            "role": self.role_name,
            "role_code": self.role_code,
            "dept": self.department,
            "dept_id": dept_pseudo_id(self.department),
            "avatar": self.avatar,
        }


def _load_user(db: Session, user_id: int) -> AuthUser:
    user = db.get(User, user_id)
    if not user or user.status != 1:
        raise unauthorized()

    role_rows = db.execute(
        select(Role.role_code, Role.role_name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    ).all()
    physical = [row[0] for row in role_rows]
    logical_codes = [ROLE_MAP.get(code) for code in physical if ROLE_MAP.get(code)]
    logical = max(logical_codes, key=lambda c: _ROLE_PRIORITY[c], default="APPLICANT")

    perm_codes = [
        row[0]
        for row in db.execute(
            select(Permission.perm_code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user.id)
        ).all()
    ]

    return AuthUser(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        department=user.department,
        position=user.position,
        role_code=logical,
        role_name=LOGICAL_ROLE_NAME.get(logical, "申请人"),
        physical_roles=physical,
        perm_codes=sorted(set(perm_codes)),
    )


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized()
    token = authorization[7:].strip()
    if not token:
        raise unauthorized()
    user_id = decode_token(token)
    return _load_user(db, user_id)


def require_roles(*role_codes: str):
    """角色守卫：不满足 → 40301。"""

    def _dep(auth: AuthUser = Depends(get_current_user)) -> AuthUser:
        if auth.role_code not in role_codes:
            raise BizError(ErrorCode.FORBIDDEN, "无权执行该操作")
        return auth

    return _dep


require_admin = require_roles("ADMIN")
require_finance_or_admin = require_roles("FINANCE", "ADMIN")
