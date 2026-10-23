"""智能问答接口：审批人可就单据风险向系统提问。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.services import ai_qa_service

router = APIRouter(tags=["ai"])


class AiQuestionIn(BaseModel):
    question: str = Field(default="", max_length=500)


@router.post("/documents/{doc_id}/ai-qa")
def ask_document_ai(
    doc_id: int,
    payload: AiQuestionIn,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = ai_qa_service.answer_question(db, auth, doc_id, payload.question)
    return ok(data)
