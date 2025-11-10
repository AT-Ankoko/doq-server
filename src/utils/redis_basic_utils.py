# utils/redis_utils.py

# 'redis_' pref
from redis.exceptions import RedisError

# 단일 키의 값을 조회
# - key: 조회할 Redis 키
# - return: 문자열 값 또는 None
async def redis_get(ctx, key):
    try:
        client = ctx.redis_handler.client
        value = await client.get(key)
        ctx.log.debug("REDIS", f"== GET {key} > {value}")

        return value
    except RedisError as e:
        ctx.log.error("REDIS", f"-- GET error: {key}, {str(e)}")
        return None


# 단일 키-값을 저장
# - expire_sec: 초 단위 만료 시간 (None이면 무제한)
# - return: 성공 시 True, 실패 시 False
async def redis_set(ctx, key, value, expire_sec=None):
    try:
        client = ctx.redis_handler.client
        success = await client.set(key, value, ex=expire_sec)
        if not success:
            ctx.log.warning("REDIS", f"- SET failed: {key}")
        ctx.log.debug("REDIS", f"!! SET {key} = {value} (expire: {expire_sec})")
        return success
    except RedisError as e:
        ctx.log.error("REDIS", f"-- SET error: {key}, {str(e)}")
        return False


# 기존 키가 있을 경우에만 값 갱신
# - return: 갱신 성공 시 True, 키 없으면 False
async def redis_update(ctx, key, new_value):
    try:
        client = ctx.redis_handler.client
        if await client.exists(key) > 0:
            await client.set(key, new_value)
            ctx.log.debug("REDIS", f"!! UPDATE {key} = {new_value}")
            return True
        else:
            ctx.log.warning("REDIS", f"- UPDATE failed: {key} not found")
            return False
    except RedisError as e:
        ctx.log.error("REDIS", f"-- UPDATE error: {key}, {str(e)}")
        return False


# 주어진 prefix로 시작하는 키 검색, 값 함께 반환
# - return: {key: value} 형태의 딕셔너리
async def redis_search_by_prefix(ctx, prefix):
    try:
        client = ctx.redis_handler.client
        pattern = f"{prefix}*"
        keys = await client.keys(pattern)
        results = {k: await client.get(k) for k in keys}
        ctx.log.debug("REDIS", f"SEARCH prefix: {prefix}, found: {len(results)} keys")
        return results
    except RedisError as e:
        ctx.log.error("REDIS", f"-- SEARCH error: {prefix}, {str(e)}")
        return {}


# 주어진 키 삭제
# - return: 삭제된 키가 있으면 True, 없으면 False
async def redis_delete(ctx, key):
    try:
        client = ctx.redis_handler.client
        result = await client.delete(key)
        ctx.log.debug("REDIS", f"-- DELETE {key} > {result}")
        return result > 0
    except RedisError as e:
        ctx.log.error("REDIS", f"-- DELETE error: {key}, {str(e)}")
        return False


# 키의 존재 여부 확인
# - return: 존재하면 True, 없으면 False
async def redis_exists(ctx, key):
    try:
        client = ctx.redis_handler.client
        result = await client.exists(key) > 0
        ctx.log.debug("REDIS", f"== EXISTS {key} > {result}")
        return result
    except RedisError as e:
        ctx.log.error("REDIS", f"-- EXISTS error: {key}, {str(e)}")
        return False


# 키에 TTL(만료 시간) 설정
# - ttl: 초 단위 만료 시간
# - return: 설정 성공 시 True
async def redis_expire(ctx, key, ttl: int):
    try:
        client = ctx.redis_handler.client
        result = await client.expire(key, ttl)
        ctx.log.debug("REDIS", f"!! EXPIRE {key} > {ttl}s")
        return result
    except RedisError as e:
        ctx.log.error("REDIS", f"-- EXPIRE error: {key}, {str(e)}")
        return False