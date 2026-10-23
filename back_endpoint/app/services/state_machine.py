"""单据状态机 —— 唯一允许修改 document.status / current_node / version 的模块。

任何不在 TRANSITIONS 中的流转一律 40901；乐观锁版本不符 40903。
"""

from app.core.errors import state_conflict, version_conflict
from app.models import Document
from app.utils.timefmt import now

NODE_NAMES = ["部门经理审批", "财务专员审核", "财务经理复核"]
FINAL_NODE = NODE_NAMES[-1]

TRANSITIONS: dict[str, dict[str, str]] = {
    "draft": {"submit": "submitted"},
    "submitted": {"start_analysis": "analyzing"},
    "analyzing": {"finish_analysis": "pending_approval", "fail_analysis": "pending_approval"},
    "pending_approval": {
        "advance": "pending_approval",
        "approve_final": "approved",
        "return": "returned",
        "reject": "rejected",
        "withdraw": "returned",
    },
    "returned": {"resubmit": "submitted"},
    "rejected": {"restore": "draft"},
    "approved": {"complete": "completed"},
}


def transition(
    doc: Document,
    action: str,
    *,
    version: int | None = None,
    next_node: str | None = None,
) -> str:
    allowed = TRANSITIONS.get(doc.status)
    if not allowed or action not in allowed:
        raise state_conflict()

    if version is not None and doc.version != version:
        raise version_conflict(doc.version)

    new_status = allowed[action]
    moment = now()

    if action == "submit":
        doc.submit_time = moment
        doc.current_node = "—"
    elif action == "resubmit":
        doc.version += 1
        doc.submit_time = moment
        doc.current_node = "—"
    elif action == "start_analysis":
        doc.current_node = "—"
    elif action == "finish_analysis":
        doc.current_node = next_node or NODE_NAMES[0]
    elif action == "advance":
        doc.current_node = next_node or NODE_NAMES[0]
    elif action == "approve_final":
        doc.current_node = "审批完成"
    elif action in ("return", "reject", "withdraw", "restore"):
        doc.current_node = None
    elif action == "complete":
        doc.current_node = "审批完成"
        doc.finish_time = moment

    doc.status = new_status
    doc.updated_at = moment
    return new_status


def next_node_after(node_name: str) -> str | None:
    """返回下一审批节点名；已是末节点返回 None。"""
    try:
        index = NODE_NAMES.index(node_name)
    except ValueError:
        return NODE_NAMES[0]
    return NODE_NAMES[index + 1] if index + 1 < len(NODE_NAMES) else None


def node_no_of(node_name: str) -> int:
    try:
        return NODE_NAMES.index(node_name) + 1
    except ValueError:
        return 1
