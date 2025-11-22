# src/service/api/cli_session_api.py

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from src.common.id_generator import generate_sid
import random

router = APIRouter(prefix="/v1/session", tags=["Session"])

class SessionConnectRequest(BaseModel):
    userId: str

class SessionConnectResponse(BaseModel):
    sid: str

# 세션 연결 및 ID 발급
@router.post("/connect", response_model=SessionConnectResponse)
async def connect_session(request: Request, body: SessionConnectRequest):
    """
    세션을 생성하고 세션 ID 반환
    """
    ctx = request.app.state.ctx
    user_id = body.userId.strip()

    if not user_id:
        raise HTTPException(status_code=400, detail="userId는 필수입니다.")

    sid = generate_sid()

    # ctx.sessions은 세션 정보를 저장하는 dict라고 가정
    if not hasattr(ctx, "sessions"):
        ctx.sessions = {}

    ctx.sessions[sid] = {
        "userId": user_id,
        "messages": [],
        "createdAt": request.scope.get("time", None),  # 타임스탬프 저장 (선택)
    }

    return {"sid": sid}
