from fastapi import APIRouter, Request

import src.service.session.session_schema as session_schema
from src.service.session.session_service import connect_session as connect_session_service

router = APIRouter(prefix="/api/session", tags=["Session"])

# 세션 연결 및 ID 발급
@router.post("/connect")
async def connect_session(request: Request, body: session_schema.SessionConnectRequest):
    ctx = request.app.state.ctx
    return await connect_session_service(ctx, body)
