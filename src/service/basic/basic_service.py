
# service/scripts/basic_service.py

from datetime import datetime
import time, uuid, orjson

def ping(ctx):
    tid = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    ctx.log.debug(f"Ping requested in service layer | tid={tid}")

    return {
        "status": "pong",
        "message": "Hello from basic_service",
        "tid": tid
    }