# src/modules/redis_keyevent_listener.py
import asyncio
from redis.asyncio import Redis
from src.utils.event_dispatcher_utils import dispatch_redis_event
import traceback

async def start_keyevent_listener(ctx):
    client: Redis = ctx.redis_handler.get_client()
    pubsub = client.pubsub()
    
    try:
        # keyevent 패턴으로 구독 (expire 이벤트만)
        await pubsub.psubscribe("__keyevent@0__:expired")
        ctx.log.info("REDIS", ">> Keyevent listener started")
        ctx.log.info("REDIS", ">> Subscribed to __keyevent@0__:expired")

        async for message in pubsub.listen():
            try:
                if message["type"] == "pmessage":
                    event_type = str(message["channel"])
                    expired_key = str(message["data"])

                    ctx.log.info("REDIS", f"!! EVENT {event_type}: {expired_key}")
                    ctx.log.debug("REDIS", f".. Full message: {message}")

                    # expired 이벤트 처리
                    if "expired" in event_type:
                        ctx.log.info("REDIS", f">> Handling expired key: {expired_key}")
                        await handle_expired_key(ctx, expired_key)
                    
            except Exception as inner_err:
                ctx.log.error("REDIS", f"!! Error while handling event: {inner_err}")
                ctx.log.error("REDIS", f"!! Message: {message}")
                ctx.log.error("REDIS", f"!! Traceback: {traceback.format_exc()}")

    except Exception as err:
        ctx.log.error("REDIS", f"-- Redis keyevent listener crashed: {err}")
        ctx.log.error("REDIS", f"-- Stack trace: {traceback.format_exc()}")
        raise
    finally:
        await pubsub.close()


async def handle_expired_key(ctx, key: str):
    try:
        ctx.log.info("REDIS", f">> Processing expired key: {key}")
        
        # 주의: expire된 키는 이미 삭제되어 데이터를 가져올 수 없음
        # 대안: expire 직전에 별도 백업 키에 데이터 저장하거나
        # 키 이름에서 정보 추출
        
        # 키 이름에서 정보 추출 (예: test-ping:1640995200000)
        if ":" in key:
            event_type, tid = key.split(":", 1)
            ctx.log.info("REDIS", f">> Extracted - event: {event_type}, tid: {tid}")
            
            # 백업 키에서 데이터 조회 시도
            backup_key = f"backup:{key}"
            data = await ctx.redis_handler.client.hgetall(backup_key)
            
            if data:
                # 안전한 디코딩 처리
                fields = {}
                for k, v in data.items():
                    key = k.decode() if isinstance(k, bytes) else str(k)
                    value = v.decode() if isinstance(v, bytes) else str(v)
                    fields[key] = value
                    
                ctx.log.debug("REDIS", f".. Retrieved backup data: {fields}")
                
                result = await dispatch_redis_event(ctx, event_type, key, fields)
                ctx.log.info("REDIS", f"!! Event dispatch result: {result}")
                
                # 백업 키도 정리
                await ctx.redis_handler.client.delete(backup_key)
            else:
                ctx.log.warning("REDIS", f"- No backup data for expired key: {key}")
        else:
            ctx.log.warning("REDIS", f"- Invalid key format: {key}")

    except Exception as e:
        ctx.log.error("REDIS", f"-- Failed to handle expired key {key}: {e}")
        ctx.log.error("REDIS", f"-- Stack trace: {traceback.format_exc()}")
