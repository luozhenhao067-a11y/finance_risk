"""审批：审批人解析、任务流转、待办/已办、流程链。"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.core.errors import (
    BizError,
    ErrorCode,
    bad_request,
    data_scope_denied,
    forbidden,
    not_found,
    state_conflict,
    version_conflict,
)
from app.core.permissions import can_view_doc
from app.models import (
    ApprovalFlow,
    ApprovalOpinion,
    ApprovalTask,
    Document,
    RiskAnalysis,
    Role,
    User,
    UserRole,
)
from app.services import log_service, notification_service
from app.services.serializers import (
    document_out,
    flow_out,
    opinion_out,
    task_out,
)
from app.services.state_machine import NODE_NAMES, next_node_after, node_no_of, transition
from app.utils.pagination import paginate, page_out
from app.utils.timefmt import now

ACTION_TO_DB = {"approve": "approved", "return": "returned", "reject": "rejected"}
LOG_ACTION = {"approve": "审批通过", "return": "退回单据", "reject": "驳回单据"}
DEFAULT_OPINION = {
    "approve": "同意，审批通过。",
    "return": "材料需补充，退回申请人修改后重新提交。",
    "reject": "不符合报销规范，予以驳回。",
}


def _users_with_role(db: Session, role_code: str) -> list[User]:
    return db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.role_code == role_code, User.status == 1)
        .order_by(User.id)
    ).scalars().all()


def _first_of_roles(db: Session, role_codes: tuple[str, ...]) -> User | None:
    for code in role_codes:
        users = _users_with_role(db, code)
        if users:
            return users[0]
    return None


def resolve_approver(db: Session, node_name: str, doc: Document) -> User:
    if node_name == NODE_NAMES[0]:
        managers = _users_with_role(db, "dept_manager")
        match = next((user for user in managers if user.department == doc.department), None)
        approver = match or _first_of_roles(db, ("finance_manager", "admin"))
    elif node_name == NODE_NAMES[1]:
        approver = _first_of_roles(db, ("finance_staff", "finance_manager", "admin"))
    else:
        approver = _first_of_roles(db, ("finance_manager", "admin"))
    if not approver:
        raise BizError(ErrorCode.SYSTEM_ERROR, "未找到可用的审批人")
    return approver


def create_task(db: Session, flow: ApprovalFlow, doc: Document, node_name: str):
    approver = resolve_approver(db, node_name, doc)
    task = ApprovalTask(
        flow_id=flow.id,
        document_id=doc.id,
        node_no=node_no_of(node_name),
        node_name=node_name,
        approver_id=approver.id,
        task_status="pending",
        action=None,
        assign_time=now(),
        handle_time=None,
    )
    db.add(task)
    db.flush()
    notification_service.notify(
        db, approver.id, doc.id, "您有新的单据待审批", f"{doc.doc_no} {doc.title}", "approval"
    )
    return task, approver


def get_flow(db: Session, doc_id: int) -> ApprovalFlow | None:
    return db.execute(
        select(ApprovalFlow).where(ApprovalFlow.document_id == doc_id)
    ).scalar_one_or_none()


def reset_flow(db: Session, doc: Document) -> ApprovalFlow:
    """提交/重提时重置审批流（uk_flow_doc 唯一，不可重复插入）。"""
    flow = get_flow(db, doc.id)
    if flow:
        flow.status = "running"
        flow.current_node = 1
        flow.total_nodes = len(NODE_NAMES)
        flow.start_time = now()
        flow.end_time = None
        db.flush()
        return flow
    flow = ApprovalFlow(
        document_id=doc.id,
        flow_name=f"{doc.doc_no}审批流",
        current_node=1,
        total_nodes=len(NODE_NAMES),
        status="running",
        start_time=now(),
        end_time=None,
    )
    db.add(flow)
    db.flush()
    return flow


def current_pending_task(db: Session, doc: Document) -> ApprovalTask | None:
    flow = get_flow(db, doc.id)
    if not flow:
        return None
    return db.execute(
        select(ApprovalTask)
        .where(
            ApprovalTask.document_id == doc.id,
            ApprovalTask.node_no == flow.current_node,
            ApprovalTask.task_status == "pending",
        )
        .order_by(ApprovalTask.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def open_risk_exists(db: Session, doc: Document) -> bool:
    analysis = latest_analysis(db, doc)
    if not analysis:
        return False
    from app.models import RiskItem

    row = db.execute(
        select(RiskItem.id).where(RiskItem.analysis_id == analysis.id, RiskItem.status == "open").limit(1)
    ).first()
    return bool(row)


def latest_analysis(db: Session, doc: Document) -> RiskAnalysis | None:
    return db.execute(
        select(RiskAnalysis)
        .where(RiskAnalysis.document_id == doc.id)
        .order_by(RiskAnalysis.doc_version.desc(), RiskAnalysis.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def approve(db: Session, auth: AuthUser, doc_id: int, action: str, opinion: str | None, version: int | None) -> dict:
    if action not in ACTION_TO_DB:
        raise bad_request("审批动作不合法")
    doc = db.get(Document, doc_id)
    if not doc or doc.delete_flag:
        raise not_found()
    if not can_view_doc(auth, doc):
        raise data_scope_denied()
    if doc.status != "pending_approval":
        raise state_conflict()
    if version is not None and doc.version != version:
        raise version_conflict(doc.version)

    flow = get_flow(db, doc.id)
    if not flow or flow.status != "running":
        raise state_conflict()

    task = current_pending_task(db, doc)
    if not task:
        handled = db.execute(
            select(ApprovalTask.id)
            .where(
                ApprovalTask.document_id == doc.id,
                ApprovalTask.node_no == flow.current_node,
                ApprovalTask.task_status == "done",
            )
            .limit(1)
        ).first()
        if handled:
            raise BizError(ErrorCode.TASK_HANDLED, "该审批任务已被处理")
        raise state_conflict()

    if task.approver_id != auth.id and not auth.is_finance_or_admin:
        handled_before = db.execute(
            select(ApprovalTask.id)
            .where(
                ApprovalTask.document_id == doc.id,
                ApprovalTask.approver_id == auth.id,
                ApprovalTask.task_status == "done",
                ApprovalTask.handle_time >= (flow.start_time or doc.submit_time or doc.created_at),
            )
            .limit(1)
        ).first()
        if handled_before:
            raise BizError(ErrorCode.TASK_HANDLED, "该审批任务已被处理")
        raise forbidden()

    text = (opinion or "").strip()
    if action in ("return", "reject") and not text:
        raise bad_request("请填写审批意见")
    text = text or DEFAULT_OPINION[action]
    if len(text) > 500:
        raise bad_request("审批意见最多 500 字")

    task.task_status = "done"
    task.action = ACTION_TO_DB[action]
    task.handle_time = now()
    db.add(
        ApprovalOpinion(
            task_id=task.id,
            opinion=text,
            action=action,
            node=task.node_name,
            create_by=auth.id,
            create_time=now(),
        )
    )

    next_task_out = None
    if action == "approve":
        next_name = next_node_after(task.node_name)
        if next_name:
            flow.current_node = node_no_of(next_name)
            transition(doc, "advance", next_node=next_name)
            new_task, approver = create_task(db, flow, doc, next_name)
            next_task_out = task_out(new_task, approver.real_name)
            log_service.record(
                db, "审批通过", doc_id=doc.id, user=auth,
                detail=f"{task.node_name}通过，流转至{next_name}",
            )
        else:
            flow.status = "completed"
            flow.end_time = now()
            transition(doc, "approve_final")
            db.flush()
            from app.services import report_service

            report_service.generate_report(db, doc, auth, commit=False)
            notification_service.notify(
                db, doc.applicant_id, doc.id, f"{doc.doc_no} 审批通过", "单据已通过审批，待财务确认完成", "system"
            )
            log_service.record(
                db, "审批通过", doc_id=doc.id, user=auth,
                detail=f"{task.node_name}通过，单据已通过审批，待财务确认完成",
            )
    else:
        db.execute(
            update(ApprovalTask)
            .where(
                ApprovalTask.document_id == doc.id,
                ApprovalTask.task_status == "pending",
                ApprovalTask.id != task.id,
            )
            .values(task_status="cancelled", handle_time=now())
        )
        flow.status = "returned" if action == "return" else "rejected"
        flow.end_time = now()
        transition(doc, action)
        title = "单据已退回" if action == "return" else "单据已驳回"
        notification_service.notify(db, doc.applicant_id, doc.id, f"{doc.doc_no} {title}", text, "system")
        log_service.record(db, LOG_ACTION[action], doc_id=doc.id, user=auth, detail=text)

    db.commit()
    return {
        "doc_id": str(doc.id),
        "doc_status": doc.status,
        "current_node": doc.current_node,
        "next_task": next_task_out,
    }


def todo(db: Session, auth: AuthUser, doc_type: str | None = None) -> list[dict]:
    stmt = (
        select(ApprovalTask, Document, RiskAnalysis)
        .join(Document, Document.id == ApprovalTask.document_id)
        .outerjoin(
            RiskAnalysis,
            (RiskAnalysis.document_id == Document.id) & (RiskAnalysis.doc_version == Document.version),
        )
        .where(
            ApprovalTask.approver_id == auth.id,
            ApprovalTask.task_status == "pending",
            Document.status == "pending_approval",
            Document.delete_flag == 0,
        )
        .order_by(Document.submit_time.asc(), Document.id.asc())
    )
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    rows = db.execute(stmt).all()

    applicant_names = dict(
        db.execute(select(User.id, User.real_name).where(User.id.in_([row[1].applicant_id for row in rows]))).all()
        if rows
        else []
    )
    result = []
    for task, doc, analysis in rows:
        result.append(
            {
                "task_id": str(task.id),
                "node": task.node_name,
                "doc": document_out(doc, applicant_names.get(doc.applicant_id)),
                "risk_analysis": (
                    {
                        "overall_level": analysis.overall_level or "none",
                        "high_count": analysis.high_count,
                        "mid_count": analysis.mid_count,
                        "low_count": analysis.low_count,
                        "recommendation_label": analysis.recommendation_label or "",
                        "summary": analysis.summary or "",
                    }
                    if analysis
                    else None
                ),
            }
        )
    return result


def done(db: Session, auth: AuthUser, doc_type: str | None, page_no: int, page_size: int) -> dict:
    stmt = (
        select(ApprovalTask, ApprovalOpinion, Document)
        .join(ApprovalOpinion, ApprovalOpinion.task_id == ApprovalTask.id)
        .join(Document, Document.id == ApprovalTask.document_id)
        .where(
            ApprovalTask.approver_id == auth.id,
            ApprovalTask.task_status == "done",
            Document.delete_flag == 0,
        )
        .order_by(ApprovalTask.handle_time.desc(), ApprovalTask.id.desc())
    )
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    rows, total = paginate(db, stmt, page_no, page_size)
    items = []
    for task, opinion, doc in rows:
        items.append(
            {
                "task": task_out(task, auth.real_name),
                "doc": document_out(doc),
                "opinion": opinion_out(opinion, doc.id, auth.real_name),
            }
        )
    return page_out(items, total, page_no, page_size)


def flow_chain(db: Session, doc: Document) -> dict:
    flow = get_flow(db, doc.id)
    tasks = db.execute(
        select(ApprovalTask, User.real_name)
        .join(User, User.id == ApprovalTask.approver_id)
        .where(ApprovalTask.document_id == doc.id)
        .order_by(ApprovalTask.id)
    ).all()
    opinions = db.execute(
        select(ApprovalOpinion, User.real_name)
        .join(User, User.id == ApprovalOpinion.create_by)
        .where(ApprovalOpinion.task_id.in_([task.id for task, _ in tasks]))
        .order_by(ApprovalOpinion.id)
    ).all() if tasks else []

    task_out_map = {task.id: (task, name) for task, name in tasks}
    applicant_name = db.execute(select(User.real_name).where(User.id == doc.applicant_id)).scalar()

    chain = []
    finished = doc.status in ("approved", "completed")

    # 申请人提交
    submit_opinion = db.execute(
        select(ApprovalOpinion)
        .where(
            ApprovalOpinion.task_id.is_(None),
            ApprovalOpinion.node == "申请人提交",
            ApprovalOpinion.create_by == doc.applicant_id,
        )
        .order_by(ApprovalOpinion.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    chain.append(
        {
            "node": "申请人提交",
            "status": "done" if doc.submit_time else "pending",
            "person": applicant_name or "",
            "opinion": opinion_out(submit_opinion, doc.id, applicant_name) if submit_opinion else None,
        }
    )

    for node_name in NODE_NAMES:
        node_tasks = [(task, name) for task, name in tasks if task.node_name == node_name]
        latest = max(node_tasks, key=lambda pair: pair[0].id) if node_tasks else None
        if finished:
            status = "done"
        elif latest and latest[0].task_status == "done":
            status = "done"
        elif latest and latest[0].task_status == "pending" and doc.status == "pending_approval":
            status = "current"
        else:
            status = "pending"
        person = latest[1] if latest else (resolve_approver(db, node_name, doc).real_name)
        node_opinion = None
        if latest:
            row = db.execute(
                select(ApprovalOpinion, User.real_name)
                .join(User, User.id == ApprovalOpinion.create_by)
                .where(ApprovalOpinion.task_id == latest[0].id)
                .order_by(ApprovalOpinion.id.desc())
                .limit(1)
            ).first()
            if row:
                node_opinion = opinion_out(row[0], doc.id, row[1])
        chain.append(
            {"node": node_name, "status": status, "person": person, "opinion": node_opinion}
        )

    chain.append(
        {
            "node": "审批完成",
            "status": "done" if finished else "pending",
            "person": "系统",
            "opinion": None,
        }
    )

    return {
        "chain": chain,
        "instance": flow_out(flow) if flow else None,
        "tasks": [
            task_out(task, name)
            for task, name in sorted(task_out_map.values(), key=lambda pair: pair[0].id)
        ],
        "opinions": [
            opinion_out(op, doc.id, name) for op, name in opinions
        ],
    }
