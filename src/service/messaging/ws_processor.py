import src.common.common_codes as codes
from src.utils.event_dispatcher_utils import dispatch_event

async def processor(ctx, websocket, msg):
    event = msg.get("hd", {}).get("event")  # 또는 "event"로 바꾸는 것도 고려 가능
    return await dispatch_event(
        ctx,
        event=event,
        source_type="ws",
        websocket=websocket,
        msg=msg
    )
