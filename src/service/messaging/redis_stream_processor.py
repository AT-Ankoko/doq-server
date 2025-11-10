from src.utils.event_dispatcher_utils import dispatch_event
from typing import Dict, Any

async def processor(ctx, msg: Dict[str, Any]):
    event = msg.get("event")
    return await dispatch_event(
        ctx,
        event=event,
        source_type="redis",
        msg=msg
    )
