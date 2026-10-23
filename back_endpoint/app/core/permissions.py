"""单据操作权限计算（契约 §1.5 权限矩阵）。

返回详情页 permissions 块，同时供 service 层做操作校验。
"""

from app.core.deps import AuthUser
from app.models import ApprovalTask, Document

EDITABLE_STATUS = ("draft", "returned")


def can_view_doc(auth: AuthUser, doc: Document) -> bool:
    """数据范围：APPLICANT 本人；DEPT_MANAGER 本部门；FINANCE/ADMIN 全部。"""
    if doc.delete_flag:
        return False
    if auth.is_finance_or_admin:
        return True
    if auth.role_code == "DEPT_MANAGER":
        return doc.department == auth.department
    return doc.applicant_id == auth.id


def is_owner(auth: AuthUser, doc: Document) -> bool:
    return doc.applicant_id == auth.id


def compute_permissions(
    auth: AuthUser,
    doc: Document,
    current_task: ApprovalTask | None = None,
    has_open_risk: bool = False,
) -> dict:
    owner = is_owner(auth, doc)
    return {
        "can_edit": owner and doc.status in EDITABLE_STATUS,
        "can_withdraw": owner and doc.status == "pending_approval",
        "can_resubmit": owner and doc.status == "returned",
        "can_approve": doc.status == "pending_approval"
        and current_task is not None
        and current_task.task_status == "pending"
        and (
            auth.is_finance_or_admin
            or (auth.role_code == "DEPT_MANAGER" and doc.department == auth.department)
        ),
        "can_confirm_complete": doc.status == "approved" and auth.is_finance_or_admin,
        "can_restore": doc.status == "rejected" and auth.is_admin,
        "can_handle_risk": has_open_risk
        and (auth.is_finance_or_admin or (auth.role_code == "DEPT_MANAGER" and doc.department == auth.department)),
        "can_rerun_analysis": auth.is_finance_or_admin
        and doc.status in ("pending_approval", "approved", "completed"),
        "can_export_report": auth.is_finance_or_admin,
    }
