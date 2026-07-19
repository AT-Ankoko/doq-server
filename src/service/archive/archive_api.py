from fastapi import APIRouter, Request

from src.service.archive.archive_service import get_session_archive as get_session_archive_service
from src.service.archive.archive_service import list_archived_sessions as list_archived_sessions_service

router = APIRouter(prefix="/api/archive", tags=["Archive"])

@router.get("/sessions")
async def list_archived_sessions(request: Request):
    ctx = request.app.state.ctx
    return await list_archived_sessions_service(ctx)

@router.get("/session/{sid}")
async def get_session_archive(sid: str, request: Request):
    ctx = request.app.state.ctx
    return await get_session_archive_service(ctx, sid)
