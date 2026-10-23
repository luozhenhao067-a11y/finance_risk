"""规则引擎上下文与结果数据结构。"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import (
    Attachment,
    AttachmentParseResult,
    Document,
    DocumentItem,
    ExpenseStandard,
    User,
    Vendor,
)


@dataclass
class EvidenceDraft:
    evidence_type: str
    snippet: str
    source: str | None = None
    attachment_id: int | None = None
    page: int = 1
    confidence: float = 90.0


@dataclass
class RuleFinding:
    rule_code: str
    risk_level: str
    risk_desc: str
    score: int
    risk_type: str | None = None
    evidences: list[EvidenceDraft] = field(default_factory=list)


@dataclass
class EngineContext:
    db: Session
    doc: Document
    applicant: User | None
    items: list[DocumentItem]
    attachments: list[Attachment]
    parse_results: dict[int, AttachmentParseResult]
    standards: list[ExpenseStandard]
    vendors: list[Vendor]

    def fields_of(self, att_id: int) -> list[dict]:
        result = self.parse_results.get(att_id)
        if not result or not isinstance(result.result_json, list):
            return []
        return [row for row in result.result_json if isinstance(row, dict)]

    def field_value(self, att_id: int, label: str) -> str | None:
        for row in self.fields_of(att_id):
            if str(row.get("label", "")) == label:
                return str(row.get("value", "")).strip() or None
        return None

    def parsed_text(self) -> str:
        chunks: list[str] = []
        for att_id in self.parse_results:
            for row in self.fields_of(att_id):
                chunks.append(f"{row.get('label', '')} {row.get('value', '')}")
        return " ".join(chunks)
