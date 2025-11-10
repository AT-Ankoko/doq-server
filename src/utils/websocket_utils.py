# utils/websocket_utils.py
# 'ws_' prefix

import orjson
from utils import redis_basic_utils

async def ws_send_response(ctx, sid: str, body: dict) -> bool:
    """
    WebSocket을 통해 클라이언트로 응답 메시지를 전송합니다.
    
    :param ctx: AppContext
    :param sid: str
    :param body: 보낼 메시지 (dict)
    """
    log = ctx.log
    ws_handler = ctx.ws_handler
    
    # 1. WebSocket 전송 시도
    ws = ws_handler.session_map.get(sid)
    if ws:
        try:
            await ws.send_json(body)
            log.info("WS", f">> Send message to sid={sid}: {body}")
            return True
        except Exception as e:
            log.warning("WS", f"- Failed to send to sid={sid}: {e}")
            # WebSocket 전송 실패 시에도 백업으로 진행
    else:
        log.warning("WS", f"- No active websocket for sid={sid}")
    
    # 2. WebSocket이 없거나 전송 실패 시 Redis 백업
    return await _backup_message_to_redis(ctx, sid, body)


async def _backup_message_to_redis(ctx, sid: str, body: dict) -> bool:
    """Redis에 메시지 백업"""
    try:
        backup_key = f"chat:buffer:{sid}"
        message_data = orjson.dumps(body)
        await redis_basic_utils.redis_lpush(ctx, backup_key, message_data)
        
        # TTL 설정 (예: 1시간)
        await redis_basic_utils.redis_expire(ctx, backup_key, 3600)
        
        ctx.log.info("WS", f"!! Backup message to Redis: {backup_key}")
        return True
    except Exception as e:
        ctx.log.error("WS", f"-- Redis backup failed: sid={sid}, error={e}")
        return False