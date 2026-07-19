from typing import Any, Dict

import orjson

from src.core.responses import ResponseStatus as ApiResponseStatus
from src.core.responses import build_response_body, build_success_response
from src.service.ai.chat_state_manager import SessionStateCache
from src.utils.redis_stream_utils import redis_stream_range


async def list_archived_sessions(ctx) -> Dict[str, Any]:
    try:
        sessions = await SessionStateCache.list_all(ctx)

        summary_list = []
        for sid, data in sessions.items():
            summary_list.append({
                "sid": sid,
                "userId": data.get("user_info", {}).get("userId"),
                "client_name": data.get("user_info", {}).get("client_name"),
                "provider_name": data.get("user_info", {}).get("provider_name"),
                "current_step": data.get("current_step"),
                "updated_at": data.get("updated_at"),
                "progress": data.get("progress_percentage"),
            })

        summary_list.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

        return build_success_response(summary_list)
    except Exception as e:
        ctx.log.error(f"[ARCHIVE] Failed to list sessions: {e}")
        return build_response_body(ApiResponseStatus.SERVER_ERROR, {"detail": str(e)})


async def get_session_archive(ctx, sid: str) -> Dict[str, Any]:
    try:
        state_manager = await SessionStateCache.get(sid, ctx)
        if not state_manager:
            return build_response_body(ApiResponseStatus.NOT_FOUND, {"detail": f"Session {sid} not found"})

        session_state = state_manager.to_dict()
        stream_key = f"session:chat:{sid}"
        stream_data = await redis_stream_range(ctx, stream_key)

        chat_history = []
        for msg_id, data in stream_data:
            try:
                body_str = data.get("body", "{}")
                body = orjson.loads(body_str)

                chat_history.append({
                    "id": msg_id,
                    "participant": data.get("participant"),
                    "timestamp": body.get("hd", {}).get("timestamp"),
                    "message": body,
                })
            except Exception as parse_err:
                ctx.log.warning(f"[ARCHIVE] Failed to parse message {msg_id}: {parse_err}")
                continue

        return build_success_response({"state": session_state, "chat_history": chat_history})
    except Exception as e:
        ctx.log.error(f"[ARCHIVE] Failed to get session {sid}: {e}")
        return build_response_body(ApiResponseStatus.SERVER_ERROR, {"detail": str(e)})
