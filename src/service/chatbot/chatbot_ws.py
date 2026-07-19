from typing import Any

import orjson
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter(prefix="/api/session", tags=["Session"])


def to_json_safe(value: Any) -> Any:
    """Redis의 bytes 값을 WebSocket JSON 응답에 사용할 수 있게 변환한다."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    if isinstance(value, str):
        try:
            return orjson.loads(value)
        except orjson.JSONDecodeError:
            return value

    if isinstance(value, dict):
        return {to_json_safe(k): to_json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]

    return value


async def send_check(
    websocket: WebSocket,
    sid: str,
    event: str,
    data: dict[str, Any],
) -> None:
    await websocket.send_json(
        {
            "hd": {
                "sid": sid,
                "event": event,
                "role": "system",
            },
            "bd": data,
        }
    )


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    WebSocket 점검 전용 엔드포인트.

    1. 연결 및 최초 정보 확인
    2. Redis 캐시 확인
    3. 수신 이벤트 타입 확인
    """
    ctx = websocket.app.state.ctx
    sid = websocket.query_params.get("sid")

    if not sid:
        await websocket.close(code=4001, reason="sid is required")
        return

    is_first_connection = len(ctx.ws_handler.session_map.get(sid, [])) == 0
    initial_info = dict(websocket.query_params)

    await ctx.ws_handler.connect(websocket, id=sid)
    ctx.log.info(f"[WS] Connected: sid={sid}, initial_info={initial_info}")

    try:
        # 1. 연결 및 최초 정보 확인
        await send_check(
            websocket,
            sid,
            "CONNECTION_CHECK",
            {
                "connected": True,
                "is_first_connection": is_first_connection,
                "initial_info": initial_info,
            },
        )

        # 2. Redis 캐싱 내용 확인
        try:
            redis = ctx.redis_handler.get_client()
            session_key = f"session:info:{sid}"
            stream_key = f"session:chat:{sid}"

            session_info = await redis.get(session_key)
            cached_messages = await redis.xrange(stream_key, count=50)

            await send_check(
                websocket,
                sid,
                "REDIS_CACHE_CHECK",
                {
                    "success": True,
                    "session_key": session_key,
                    "session_info": to_json_safe(session_info),
                    "stream_key": stream_key,
                    "message_count": len(cached_messages),
                    "messages": to_json_safe(cached_messages),
                },
            )
        except Exception as error:
            ctx.log.warning(f"[WS] Redis check failed: sid={sid}, error={error}")
            await send_check(
                websocket,
                sid,
                "REDIS_CACHE_CHECK",
                {
                    "success": False,
                    "error": str(error),
                },
            )

        # 3. 이후 수신 메시지는 hd.event 값만 확인
        while True:
            message = await websocket.receive_json()
            header = message.get("hd", {}) if isinstance(message, dict) else {}
            event_type = header.get("event")

            ctx.log.info(f"[WS] Event received: sid={sid}, event={event_type}")

            await send_check(
                websocket,
                sid,
                "EVENT_TYPE_CHECK",
                {
                    "received_event": event_type,
                    "event_exists": event_type is not None,
                },
            )

    except WebSocketDisconnect:
        ctx.log.info(f"[WS] Disconnected: sid={sid}")
    except Exception as error:
        ctx.log.error(f"[WS] Error: sid={sid}, error={error}")
    finally:
        disconnect = getattr(ctx.ws_handler, "disconnect", None)
        if disconnect:
            try:
                await disconnect(websocket, id=sid)
            except TypeError:
                await disconnect(websocket)