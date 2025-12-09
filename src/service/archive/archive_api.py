from fastapi import APIRouter, Request, HTTPException
from typing import List, Dict, Any, Optional
import orjson

from src.service.ai.chat_state_manager import SessionStateCache
from src.utils.redis_stream_utils import redis_stream_range
import src.common.common_codes as codes

router = APIRouter(prefix="/v1/archive", tags=["Archive"])

@router.get("/sessions", response_model=Dict[str, Any])
async def list_archived_sessions(request: Request):
    """
    활성화된(Redis에 저장된) 모든 세션 목록을 조회합니다.
    """
    ctx = request.app.state.ctx
    try:
        sessions = await SessionStateCache.list_all(ctx)
        
        # 요약 정보만 반환
        summary_list = []
        for sid, data in sessions.items():
            summary_list.append({
                "sid": sid,
                "user_name": data.get("user_info", {}).get("user_name"),
                "current_step": data.get("current_step"),
                "updated_at": data.get("updated_at"),
                "progress": data.get("progress_percentage")
            })
            
        return {
            "state": codes.ResponseStatus.SUCCESS,
            "data": summary_list
        }
    except Exception as e:
        ctx.log.error(f"[ARCHIVE] Failed to list sessions: {e}")
        return {
            "state": codes.ResponseStatus.SERVER_ERROR,
            "detail": str(e)
        }

@router.get("/session/{sid}", response_model=Dict[str, Any])
async def get_session_archive(sid: str, request: Request):
    """
    특정 세션의 상세 정보(상태 + 채팅 내역)를 조회합니다.
    """
    ctx = request.app.state.ctx
    try:
        # 1. 세션 상태 조회
        state_manager = await SessionStateCache.get(sid, ctx)
        if not state_manager:
            return {
                "state": codes.ResponseStatus.NOT_FOUND,
                "detail": f"Session {sid} not found"
            }
            
        session_state = state_manager.to_dict()
        
        # 2. 채팅 내역 조회 (Redis Stream)
        stream_key = f"session:chat:{sid}"
        stream_data = await redis_stream_range(ctx, stream_key)
        
        chat_history = []
        for msg_id, data in stream_data:
            # data는 {"participant": "...", "body": "..."} 형태
            try:
                body_str = data.get("body", "{}")
                body = orjson.loads(body_str)
                
                chat_history.append({
                    "id": msg_id,
                    "participant": data.get("participant"),
                    "timestamp": body.get("hd", {}).get("timestamp"), # 만약 timestamp가 있다면
                    "message": body
                })
            except Exception as parse_err:
                ctx.log.warning(f"[ARCHIVE] Failed to parse message {msg_id}: {parse_err}")
                continue
                
        return {
            "state": codes.ResponseStatus.SUCCESS,
            "data": {
                "state": session_state,
                "chat_history": chat_history
            }
        }
        
    except Exception as e:
        ctx.log.error(f"[ARCHIVE] Failed to get session {sid}: {e}")
        return {
            "state": codes.ResponseStatus.SERVER_ERROR,
            "detail": str(e)
        }
