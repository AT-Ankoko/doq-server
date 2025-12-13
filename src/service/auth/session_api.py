# src/service/api/cli_session_api.py

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from src.common.id_generator import generate_sid
import src.utils.redis_basic_utils as ru
import orjson
from typing import Optional

router = APIRouter(prefix="/v1/session", tags=["Session"])

class SessionConnectRequest(BaseModel):
    userId: str
    client_name: str
    provider_name: str
    contract_date: Optional[str] = None
    client_business_number: Optional[str] = None
    client_contact: Optional[str] = None
    provider_business_number: Optional[str] = None
    provider_contact: Optional[str] = None

class SessionConnectResponse(BaseModel):
    sid: str

# 세션 연결 및 ID 발급
@router.post("/connect", response_model=SessionConnectResponse)
async def connect_session(request: Request, body: SessionConnectRequest):
    """
    세션을 생성하고 세션 ID 반환
    client_name, provider_name, contract_date 등의 정보를 함께 저장
    """
    ctx = request.app.state.ctx
    user_id = body.userId.strip()

    if not user_id:
        raise HTTPException(status_code=400, detail="userId는 필수입니다.")

    sid = generate_sid()

    # 세션 정보 저장 (Redis에 저장)
    session_info = {
        "userId": user_id,
        "client_name": body.client_name,
        "provider_name": body.provider_name,
        "contract_date": body.contract_date,
        "client_business_number": body.client_business_number,
        "client_contact": body.client_contact,
        "provider_business_number": body.provider_business_number,
        "provider_contact": body.provider_contact,
        "createdAt": None,
    }
    
    try:
        # Redis에 세션 정보 저장 (TTL: 24시간)
        session_key = f"session:info:{sid}"
        await ru.redis_set(
            ctx,
            session_key,
            orjson.dumps(session_info).decode(),
            ex=86400  # 24시간
        )
    except Exception as e:
        ctx.log.warning(f"[AUTH] Failed to save session info to Redis: {e}")
        # Redis 실패 시에도 진행 (메모리에만 저장)
        if not hasattr(ctx, "sessions"):
            ctx.sessions = {}
        ctx.sessions[sid] = session_info

    return {"sid": sid}
