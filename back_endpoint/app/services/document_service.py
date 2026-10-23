"""单据主链路：校验、创建、提交/重提/撤回、确认完成、恢复、列表与详情。"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import AuthUser
from app.core.errors import (
    bad_request,
    data_scope_denied,
    forbidden,
    not_found,
    state_conflict,
    version_conflict,
)
from app.core.permissions import can_view_doc, compute_permissions, is_owner
from app.models import (
    ApprovalOpinion,
    ApprovalTask,
    Attachment,
    AttachmentParseResult,
    DictTable,
    Document,
    DocumentItem,
    Report,
    RiskAnalysis,
    RiskEvidence,
    RiskItem,
    RiskRule,
    User,
)
from app.services import (
    approval_service,
    log_service,
    notification_service,
    parse_service,
    snapshot_service,
)
from app.services.state_machine import NODE_NAMES, transition
from app.utils.ids import next_doc_no
from app.utils.pagination import page_out, paginate, sort_apply
from app.utils.storage import file_type_of, parse_size_label
from app.utils.timefmt import day_after, day_start, money, now, parse_date, today

INVOICE_PATTERN = re.compile(r"^(\d{8}|\d{10}|(INV|HT)-\d+)$", re.IGNORECASE)
REIMBURSE_TYPES = ("费用报销", "差旅费报销")
CONTRACT_TYPES = ("采购付款", "合同付款")

_dict_cache: dict[str, tuple[datetime, list[DictTable]]] = {}
_CACHE_SECONDS = 60


def _dict_rows(db: Session, dict_type: str) -> list[DictTable]:
    cached = _dict_cache.get(dict_type)
    if cached and (now() - cached[0]).total_seconds() < _CACHE_SECONDS:
        return cached[1]
    rows = db.execute(
        select(DictTable)
        .where(DictTable.dict_type == dict_type, DictTable.enabled == 1)
        .order_by(DictTable.sort, DictTable.id)
    ).scalars().all()
    _dict_cache[dict_type] = (now(), list(rows))
    return list(rows)


def doc_types(db: Session) -> list[str]:
    return [row.dict_value for row in _dict_rows(db, "doc_type")]


def expense_types(db: Session, doc_type: str) -> list[str]:
    return [
        row.dict_value
        for row in _dict_rows(db, "expense_type")
        if not row.scope or row.scope == doc_type
    ]


def _field(row, name: str, default=None):
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _normalize_detail(db: Session, row, doc_type: str, index: int) -> dict:
    expense_type = (_field(row, "expense_type", "") or "").strip()
    raw_date = _field(row, "expense_date")
    amount = _field(row, "amount")
    if not expense_type or raw_date in (None, "") or amount is None:
        raise bad_request("请补全费用明细的类型、日期与金额")
    if expense_type not in expense_types(db, doc_type):
        raise bad_request(f"费用明细第 {index} 行类型不正确")
    if isinstance(raw_date, datetime):
        expense_date = raw_date.date()
    elif isinstance(raw_date, date):
        expense_date = raw_date
    else:
        try:
            expense_date = parse_date(str(raw_date))
        except ValueError:
            raise bad_request("费用日期格式应为 YYYY-MM-DD") from None
    if expense_date > today():
        raise bad_request("费用日期不能晚于今天")
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise bad_request("金额格式不正确") from None
    if amount <= 0:
        raise bad_request("金额必须大于 0")
    if amount.as_tuple().exponent < -2:
        raise bad_request("金额最多保留 2 位小数")
    invoice_no = (_field(row, "invoice_no") or "")
    invoice_no = invoice_no.strip() or None
    if invoice_no == "—":
        invoice_no = None
    if invoice_no and not INVOICE_PATTERN.match(invoice_no):
        raise bad_request(f"发票号格式不正确（明细：{expense_type} {expense_date}）")
    remark = (_field(row, "remark") or _field(row, "description") or "").strip() or None
    if remark and len(remark) > 200:
        raise bad_request("备注最多 200 字")
    return {
        "expense_type": expense_type,
        "expense_date": expense_date,
        "amount": amount.quantize(Decimal("0.01")),
        "invoice_no": invoice_no,
        "description": remark,
    }


def validate_document(
    db: Session,
    *,
    doc_type: str,
    title: str,
    project: str | None,
    details: list,
    attachment_names: list[str],
    total_amount: Decimal | None = None,
    check_attachments: bool = False,
) -> tuple[list[dict], Decimal]:
    """契约 §4.4 全量校验；返回规范化明细与合计金额。"""
    title = (title or "").strip()
    if not title:
        raise bad_request("请填写单据标题")
    if len(title) > 100:
        raise bad_request("单据标题最多 100 字")
    project = (project or "").strip()
    if not project:
        raise bad_request("请填写费用项目")
    if len(project) > 100:
        raise bad_request("费用项目最多 100 字")
    if not doc_type:
        raise bad_request("请选择单据类型")
    if doc_type not in doc_types(db):
        raise bad_request("单据类型不正确")
    if not details:
        raise bad_request("请至少添加一条费用明细")

    normalized = [_normalize_detail(db, row, doc_type, index) for index, row in enumerate(details, start=1)]
    computed_total = sum((row["amount"] for row in normalized), Decimal("0.00"))

    if total_amount is not None:
        claimed = Decimal(str(total_amount))
        if abs(claimed - computed_total) > Decimal("0.01"):
            raise bad_request("合计金额与明细不一致")

    if check_attachments and doc_type in REIMBURSE_TYPES:
        for row in normalized:
            if not row["invoice_no"]:
                raise bad_request(
                    f"报销类单据发票号必填（明细：{row['expense_type']} {row['expense_date']}）"
                )
        if not any("发票" in name or "票据" in name for name in attachment_names):
            raise bad_request("报销类单据必须上传至少 1 个发票附件")
    if check_attachments and doc_type in CONTRACT_TYPES:
        if not any("合同" in name for name in attachment_names):
            raise bad_request("采购付款/合同付款必须上传合同附件")
    return normalized, computed_total


def _new_document(auth: AuthUser, payload, total: Decimal, dept: str | None) -> Document:
    moment = now()
    return Document(
        doc_no="",
        doc_type=payload.doc_type,
        doc_type_name=payload.doc_type,
        title=payload.title.strip(),
        project=(payload.project or "").strip() or None,
        dept_id=None,
        status="draft",
        version=1,
        current_node=None,
        risk_level="none",
        risk_count=0,
        delete_flag=0,
        total_amount=total,
        currency="CNY",
        applicant_id=auth.id,
        department=dept,
        description=((payload.remark or payload.description or "").strip() or None),
        submit_time=None,
        finish_time=None,
        created_at=moment,
        updated_at=moment,
    )


def _insert_with_doc_no(db: Session, doc: Document) -> None:
    for _ in range(20):
        doc.doc_no = next_doc_no(db, Document.doc_no, today())
        savepoint = db.begin_nested()
        db.add(doc)
        try:
            db.flush()
            savepoint.commit()
            return
        except IntegrityError:
            savepoint.rollback()
            if doc in db:
                db.expunge(doc)
    raise bad_request("单据编号生成失败，请重试")


def _add_attachment_meta(db: Session, doc: Document, auth: AuthUser, meta) -> Attachment:
    name = (meta.file_name or "").strip()
    if not name:
        raise bad_request("附件文件名不能为空")
    if len(name) > 255:
        raise bad_request("附件文件名过长")
    size_bytes = meta.size
    if size_bytes:
        size_kb = max(1, int(size_bytes) // 1024)
    else:
        size_kb = parse_size_label(meta.size_label) or 0
    att = Attachment(
        document_id=doc.id,
        file_name=name,
        file_type=meta.file_type or file_type_of(name),
        file_size=size_kb,
        file_url=f"/files/{doc.doc_no}/v{doc.version}/{name}",
        parse_status="parsing",
        upload_by=auth.id,
        upload_time=now(),
    )
    db.add(att)
    db.flush()
    parse_service.simulate_parse(db, att, doc)
    return att


def create_document(db: Session, auth: AuthUser, payload) -> dict:
    normalized, total = validate_document(
        db,
        doc_type=payload.doc_type,
        title=payload.title,
        project=payload.project,
        details=payload.details,
        attachment_names=[item.file_name for item in payload.attachments],
        total_amount=payload.total_amount,
    )
    dept = (payload.dept or payload.dept_name or auth.department or "").strip() or None
    doc = _new_document(auth, payload, total, dept)
    _insert_with_doc_no(db, doc)

    moment = now()
    for index, row in enumerate(normalized, start=1):
        db.add(
            DocumentItem(
                document_id=doc.id,
                item_no=index,
                expense_type=row["expense_type"],
                expense_date=row["expense_date"],
                amount=row["amount"],
                invoice_no=row["invoice_no"],
                description=row["description"],
                created_at=moment,
            )
        )
    db.flush()

    for meta in payload.attachments:
        _add_attachment_meta(db, doc, auth, meta)

    log_service.record(
        db, "创建单据", doc_id=doc.id, user=auth,
        detail=f"创建{doc.doc_type} {doc.doc_no}，金额 {money(doc.total_amount):.2f} 元",
    )

    if payload.submit:
        _do_submit(db, auth, doc, "submit")
    db.commit()
    return document_out_with_name(db, doc, auth.real_name)


def document_out_with_name(db: Session, doc: Document, applicant_name: str | None = None) -> dict:
    from app.services.serializers import document_out

    if applicant_name is None:
        applicant_name = db.execute(select(User.real_name).where(User.id == doc.applicant_id)).scalar()
    return document_out(doc, applicant_name)


def _attachments_of(db: Session, doc_id: int) -> list[Attachment]:
    return db.execute(
        select(Attachment).where(Attachment.document_id == doc_id).order_by(Attachment.id)
    ).scalars().all()


def _items_of(db: Session, doc_id: int) -> list[DocumentItem]:
    return db.execute(
        select(DocumentItem).where(DocumentItem.document_id == doc_id).order_by(DocumentItem.item_no)
    ).scalars().all()


def _do_submit(db: Session, auth: AuthUser, doc: Document, action: str, reason: str | None = None) -> dict:
    if not is_owner(auth, doc):
        raise data_scope_denied()
    items = _items_of(db, doc.id)
    attachments = _attachments_of(db, doc.id)
    validate_document(
        db,
        doc_type=doc.doc_type,
        title=doc.title,
        project=doc.project,
        details=items,
        attachment_names=[att.file_name for att in attachments],
        total_amount=doc.total_amount,
        check_attachments=True,
    )

    transition(doc, action)
    snapshot_service.ensure_version(db, doc)
    snapshot_service.create_snapshot(db, doc)
    flow = approval_service.reset_flow(db, doc)
    task, approver = approval_service.create_task(db, flow, doc, NODE_NAMES[0])

    log_text = "提交审批" if action == "submit" else "重新提交"
    opinion_text = (reason or "").strip() or ("提交审批" if action == "submit" else "修改后重新提交")
    db.add(
        ApprovalOpinion(
            task_id=None,
            opinion=opinion_text[:500],
            action=action,
            node="申请人提交",
            create_by=auth.id,
            create_time=now(),
        )
    )
    log_service.record(db, log_text, doc_id=doc.id, user=auth, detail=opinion_text)
    return {
        "doc_id": str(doc.id),
        "doc_no": doc.doc_no,
        "status": doc.status,
        "version": doc.version,
        "snapshot_version": doc.version,
        "approval_instance_id": str(flow.id),
        "first_task_id": str(task.id),
        "first_approver": approver.real_name,
        "parse_task_ids": [],
        "analysis_task_id": None,
    }


def _get_doc(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if not doc or doc.delete_flag:
        raise not_found()
    return doc


def _get_visible(db: Session, auth: AuthUser, doc_id: int) -> Document:
    doc = _get_doc(db, doc_id)
    if not can_view_doc(auth, doc):
        raise data_scope_denied()
    return doc


def get_visible_doc(db: Session, auth: AuthUser, doc_id: int) -> Document:
    return _get_visible(db, auth, doc_id)


def submit_document(db: Session, auth: AuthUser, doc_id: int, version: int | None = None) -> dict:
    doc = _get_visible(db, auth, doc_id)
    if not is_owner(auth, doc):
        raise data_scope_denied()
    if doc.status != "draft":
        raise state_conflict()
    if version is not None and doc.version != version:
        raise version_conflict(doc.version)
    result = _do_submit(db, auth, doc, "submit")
    db.commit()
    return result


def resubmit_document(db: Session, auth: AuthUser, doc_id: int, version: int | None = None, reason: str | None = None) -> dict:
    doc = _get_visible(db, auth, doc_id)
    if not is_owner(auth, doc):
        raise data_scope_denied()
    if doc.status != "returned":
        raise state_conflict()
    if version is not None and doc.version != version:
        raise version_conflict(doc.version)
    result = _do_submit(db, auth, doc, "resubmit", reason)
    db.commit()
    return result


def withdraw_document(db: Session, auth: AuthUser, doc_id: int, reason: str | None = None) -> dict:
    doc = _get_visible(db, auth, doc_id)
    if not is_owner(auth, doc):
        raise data_scope_denied()
    if doc.status != "pending_approval":
        raise state_conflict()
    flow = approval_service.get_flow(db, doc.id)
    db.execute(
        update(ApprovalTask)
        .where(ApprovalTask.document_id == doc.id, ApprovalTask.task_status == "pending")
        .values(task_status="cancelled", handle_time=now())
    )
    if flow:
        flow.status = "returned"
        flow.end_time = now()
    transition(doc, "withdraw")
    text = (reason or "").strip() or "申请人撤回单据"
    db.add(
        ApprovalOpinion(
            task_id=None,
            opinion=text[:500],
            action="withdraw",
            node="申请人提交",
            create_by=auth.id,
            create_time=now(),
        )
    )
    for task, _ in db.execute(
        select(ApprovalTask, User.real_name)
        .join(User, User.id == ApprovalTask.approver_id)
        .where(ApprovalTask.document_id == doc.id, ApprovalTask.task_status == "cancelled")
    ).all():
        notification_service.notify(
            db, task.approver_id, doc.id, f"{doc.doc_no} 已撤回", text, "system"
        )
    notification_service.notify(db, doc.applicant_id, doc.id, "撤单成功", f"{doc.doc_no} 已撤回，可修改后重新提交", "system")
    log_service.record(db, "撤回单据", doc_id=doc.id, user=auth, detail=text)
    db.commit()
    return document_out_with_name(db, doc, auth.real_name)


def complete_document(db: Session, auth: AuthUser, doc_id: int) -> dict:
    if not auth.is_finance_or_admin:
        raise forbidden()
    doc = _get_visible(db, auth, doc_id)
    if doc.status != "approved":
        raise state_conflict()
    transition(doc, "complete")
    notification_service.notify(db, doc.applicant_id, doc.id, f"{doc.doc_no} 已完成", "财务已确认完成", "system")
    log_service.record(db, "审批完成", doc_id=doc.id, user=auth, detail="财务确认完成")
    db.commit()
    return document_out_with_name(db, doc)


def restore_document(db: Session, auth: AuthUser, doc_id: int, reason: str | None) -> dict:
    if not auth.is_admin:
        raise forbidden()
    doc = _get_doc(db, doc_id)
    text = (reason or "").strip()
    if not text:
        raise bad_request("请填写恢复原因")
    if len(text) > 200:
        raise bad_request("恢复原因最多 200 字")
    if doc.status != "rejected":
        raise state_conflict()
    transition(doc, "restore")
    flow = approval_service.get_flow(db, doc.id)
    if flow and flow.status == "running":
        flow.status = "cancelled"
        flow.end_time = now()
    notification_service.notify(db, doc.applicant_id, doc.id, f"{doc.doc_no} 已恢复", text, "system")
    log_service.record(db, "恢复单据", doc_id=doc.id, user=auth, detail=text)
    db.commit()
    return document_out_with_name(db, doc)


def get_page(db: Session, auth: AuthUser, filters: dict, page: int, page_size: int) -> dict:
    stmt = (
        select(Document, User.real_name)
        .join(User, User.id == Document.applicant_id)
        .where(Document.delete_flag == 0)
    )
    if auth.role_code == "APPLICANT":
        stmt = stmt.where(Document.applicant_id == auth.id)
    elif auth.role_code == "DEPT_MANAGER":
        stmt = stmt.where(Document.department == auth.department)

    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            Document.title.like(like)
            | Document.doc_no.like(like)
            | User.real_name.like(like)
            | Document.department.like(like)
            | Document.project.like(like)
        )
    if filters.get("doc_type"):
        stmt = stmt.where(Document.doc_type == filters["doc_type"])
    if filters.get("status"):
        stmt = stmt.where(Document.status == filters["status"])
    if filters.get("risk_level"):
        stmt = stmt.where(Document.risk_level == filters["risk_level"])
    if filters.get("date_from"):
        try:
            stmt = stmt.where(Document.created_at >= day_start(filters["date_from"]))
        except ValueError:
            raise bad_request("开始日期格式应为 YYYY-MM-DD") from None
    if filters.get("date_to"):
        try:
            stmt = stmt.where(Document.created_at < day_after(filters["date_to"]))
        except ValueError:
            raise bad_request("结束日期格式应为 YYYY-MM-DD") from None

    stmt = sort_apply(
        stmt,
        {
            "amount": Document.total_amount,
            "submit_time": Document.submit_time,
            "created_at": Document.created_at,
            "create_time": Document.created_at,
            "updated_at": Document.updated_at,
        },
        filters.get("sort_by"),
        filters.get("sort_order"),
        "created_at",
    )
    rows, total = paginate(db, stmt, page, page_size)
    from app.services.serializers import document_out

    items = [document_out(doc, name) for doc, name in rows]
    return page_out(items, total, page, page_size)


def _risk_items_block(db: Session, analysis: RiskAnalysis | None, doc_id: int) -> list[dict]:
    if not analysis:
        return []
    from app.services.serializers import risk_item_out

    rows = db.execute(
        select(RiskItem, RiskRule)
        .join(RiskRule, RiskRule.id == RiskItem.rule_id)
        .where(RiskItem.analysis_id == analysis.id)
        .order_by(RiskItem.id)
    ).all()
    evidences = db.execute(
        select(RiskEvidence)
        .where(RiskEvidence.risk_item_id.in_([item.id for item, _ in rows]))
        .order_by(RiskEvidence.id)
    ).scalars().all() if rows else []
    by_item: dict[int, list[RiskEvidence]] = {}
    for evidence in evidences:
        by_item.setdefault(evidence.risk_item_id, []).append(evidence)

    result = []
    for item, rule in rows:
        data = risk_item_out(item, rule, by_item.get(item.id, []))
        data["doc_id"] = str(doc_id)
        result.append(data)
    return result


def get_detail(db: Session, auth: AuthUser, doc_id: int) -> dict:
    from app.services.serializers import (
        attachment_out,
        document_out,
        item_out,
        parse_result_out,
        report_out,
        risk_analysis_out,
    )

    doc = _get_visible(db, auth, doc_id)
    applicant_name = db.execute(select(User.real_name).where(User.id == doc.applicant_id)).scalar()
    items = _items_of(db, doc.id)
    attachments = _attachments_of(db, doc.id)
    parse_rows = db.execute(
        select(AttachmentParseResult).where(
            AttachmentParseResult.attachment_id.in_([att.id for att in attachments])
        )
    ).scalars().all() if attachments else []
    parse_map = {row.attachment_id: row for row in parse_rows}

    analysis = approval_service.latest_analysis(db, doc)
    risk_items = _risk_items_block(db, analysis, doc.id)
    current_task = approval_service.current_pending_task(db, doc)
    has_open_risk = any(item["status"] == "open" for item in risk_items)
    report = db.execute(
        select(Report).where(Report.document_id == doc.id).order_by(Report.id.desc()).limit(1)
    ).scalar_one_or_none()

    return {
        "doc": document_out(doc, applicant_name),
        "details": [item_out(item) for item in items],
        "attachments": [attachment_out(att) for att in attachments],
        "snapshots": snapshot_service.list_snapshots(db, doc.id),
        "risk_analysis": risk_analysis_out(analysis) if analysis else None,
        "risk_items": risk_items,
        "parse_results": [
            parse_result_out(att, parse_map[att.id]) for att in attachments if att.id in parse_map
        ],
        "approval_flow": approval_service.flow_chain(db, doc),
        "logs": log_service.recent_for_doc(db, doc.id),
        "report": report_out(report) if report else None,
        "permissions": compute_permissions(auth, doc, current_task, has_open_risk),
    }


def get_logs_page(db: Session, auth: AuthUser, doc_id: int, page: int, page_size: int) -> dict:
    _get_visible(db, auth, doc_id)
    return log_service.page_for_doc(db, doc_id, page, page_size)


def list_snapshots(db: Session, auth: AuthUser, doc_id: int) -> list[dict]:
    _get_visible(db, auth, doc_id)
    return snapshot_service.list_snapshots(db, doc_id)


def get_snapshot(db: Session, auth: AuthUser, doc_id: int, version: int) -> dict:
    _get_visible(db, auth, doc_id)
    snapshot = snapshot_service.get_snapshot(db, doc_id, version)
    return {"snapshot": snapshot, "payload": snapshot.get("payload")}
