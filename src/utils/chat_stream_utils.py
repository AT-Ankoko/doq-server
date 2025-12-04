# utils/chat_stream_utils.py
import orjson
from utils.redis_stream_utils import redis_stream_add

async def store_chat_message(ctx, sid: str, participant: str, msg: dict, stream_key: str | None = None):
    """
    세션별 Redis Stream에 채팅 메시지를 저장합니다.
    
    Args:
        ctx: 애플리케이션 컨텍스트
        sid: 세션 ID
        participant: 참여자 타입 ("user" | "assistant")
                    - "user": 사용자 메시지 (msg.hd.role에는 "client" 또는 "provider")
                    - "assistant": AI 어시스턴트 응답
        msg: 메시지 객체 (dict)
            - hd: 헤더 정보 {"role": "client" | "provider", ...}
            - bd: 바디 정보 {"text": "...", ...}
        stream_key: Redis stream 키 (기본값: `chat:session:{sid}`)
    
    Redis Stream 저장 형태:
    {
        "participant": "user" | "assistant",    # 발신자 타입
        "body": '{"hd": {...}, "bd": {...}}'   # JSON 문자열
    }
    
    예시:
    - 클라이언트(의뢰인) 메시지: participant="user", msg.hd.role="client"
    - 서비스 제공자 메시지: participant="user", msg.hd.role="provider"
    - AI 응답: participant="assistant"
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
