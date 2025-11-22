# utils/chat_stream_utils.py
import orjson
from utils.redis_stream_utils import redis_stream_add

async def store_chat_message(ctx, sid: str, participant: str, msg: dict, stream_key: str | None = None):
    """
    세션별 Redis Stream에 채팅 메시지를 저장합니다.
    - stream_key가 주어지지 않으면 기본값으로 `chat:session:{sid}`를 사용합니다.
    - message 필드는 'participant'와 'body'를 포함합니다. 'body'는 JSON 문자열입니다.
    """
    try:
        key = stream_key or f"chat:session:{sid}"
        body_json = orjson.dumps(msg).decode()
        payload = {
            "participant": participant,
            "body": body_json
        }
        message_id = await redis_stream_add(ctx, key, payload)
        ctx.log.debug("WS", f"++ Chat saved to stream {key} > {message_id}")
        return message_id
    except Exception as e:
        ctx.log.error("WS", f"-- Failed to store chat to stream: sid={sid}, err={e}")
        return None
