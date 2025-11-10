# utils/redis_utils.py

# 'redis_' pref
from redis.exceptions import RedisError
import orjson
import asyncio

# Redis Stream에 메시지 추가
async def redis_stream_add(ctx, stream_key, message: dict):
    try:
        client = ctx.redis_handler.client
        message_id = await client.xadd(stream_key, message)
        ctx.log.debug("REDIS", f"++ XADD {stream_key} > {message_id}, {message}")
        return message_id
    except RedisError as e:
        ctx.log.error("REDIS", f"-- XADD error: {stream_key}, {str(e)}")
        return None

# Redis Stream에서 메시지 읽기
async def redis_stream_read(ctx, stream_key, last_id="$", block_ms=0):
    try:
        client = ctx.redis_handler.client
        response = await client.xread({stream_key: last_id}, block=block_ms)
        ctx.log.debug(f"REDIS", "== XREAD {stream_key} from {last_id} > {response}")
        return response
    except RedisError as e:
        ctx.log.error("REDIS", f"-- XREAD error: {stream_key}, {str(e)}")
        return []


# Consumer Group에서 메시지 읽기
async def redis_stream_group_read(ctx, group, consumer, stream_key, count=1):
    try:
        client = ctx.redis_handler.client
        response = await client.xreadgroup(group, consumer, {stream_key: ">"}, count=count)
        ctx.log.debug("REDIS", f"== XREADGROUP {group}/{consumer} > {response}")
        return response
    except RedisError as e:
        ctx.log.error("REDIS", f"-- XREADGROUP error: {group}, {str(e)}")
        return []


# 메시지 ACK
async def redis_stream_ack(ctx, stream_key, group, message_id):
    try:
        client = ctx.redis_handler.client
        result = await client.xack(stream_key, group, message_id)
        ctx.log.debug("REDIS", f"!! XACK {stream_key}/{group} > {message_id} > {result}")
        return result
    except RedisError as e:
        ctx.log.error("REDIS", f"-- XACK error: {stream_key}, {message_id}, {str(e)}")
        return False

# Consumer Group 생성
async def redis_stream_create_group(ctx, stream_key, group_name):
    try:
        client = ctx.redis_handler.client
        await client.xgroup_create(stream_key, group_name, id="0", mkstream=True)
        ctx.log.debug("REDIS", f"++ XGROUP.CREATE {stream_key} > {group_name}")
        return True
    except RedisError as e:
        if "BUSYGROUP" in str(e):
            ctx.log.debug("REDIS", f"- XGROUP already exists: {group_name} on {stream_key}")
            return True
        ctx.log.error("REDIS", f"-- XGROUP.CREATE error: {stream_key}, {str(e)}")
        return False
    

async def redis_stream_wait_result(ctx, stream_key: str, timeout=10_000):
    """
    Redis Stream에서 지정된 키의 결과를 블로킹으로 대기하여 반환합니다.

    :param ctx: AppContext (redis_handler 필요)
    :param stream_key: stream 이름 (예: sandbox_result:<task_id>)
    :param timeout: 블로킹 시간 (ms)
    :return: 메시지 dict or None
    """
    log = ctx.log
    redis = ctx.redis_handler.get_client()

    try:
        entries = await redis.xread({stream_key: "0"}, block=timeout, count=1)

        if entries:
            _, messages = entries[0]
            message_id, data = messages[0]

            # 값이 JSON 문자열인 경우 파싱 시도
            parsed_data = {
                k: orjson.loads(v) if isinstance(v, str) and v.startswith("{") else v
                for k, v in data.items()
            }

            log.info("REDIS", f"<< Result received from '{stream_key}': {parsed_data}")
            return parsed_data

        log.warning("REDIS", f"== No result in '{stream_key}' (timeout={timeout}ms)")
        return None

    except Exception as e:
        log.error("REDIS", f"-- Error reading stream '{stream_key}': {e}")
        return None
