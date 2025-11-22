import src.common.common_codes as codes
from src.utils.event_dispatcher_utils import dispatch_event

async def processor(ctx, websocket, msg):
    """
    WebSocket 메시지를 받아서 이벤트 디스패처로 전달합니다.
    LLM 관련 객체는 직접 전달하지 않으며, LLM 결과는 메시지 필드로 전달되어야 합니다.
    """
    event = msg.get("hd", {}).get("event")  # 또는 "event"로 바꾸는 것도 고려 가능
    return await dispatch_event(
        ctx,
        event=event,
        source_type="ws",
        websocket=websocket,
        msg=msg
    )
