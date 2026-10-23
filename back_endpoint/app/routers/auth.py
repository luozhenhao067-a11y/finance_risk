"""认证路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import AuthUser, get_current_user
from app.core.response import ok
from app.database import get_db
from app.schemas.auth import LoginIn
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    return ok(auth_service.login(db, body.username, body.password))


@router.post("/logout")
def logout(_: AuthUser = Depends(get_current_user)):
    return ok(None)


@router.get("/me")
def me(auth: AuthUser = Depends(get_current_user)):
    return ok(auth_service.me(auth))
