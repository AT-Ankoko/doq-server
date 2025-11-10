# utils/redis_hash_utils.py

# 'redis_' pref
from redis.exceptions import RedisError

# 해시 구조의 필드에 값 설정 / 단일필드
# - return: True (성공), False (실패)
async def redis_hset(ctx, key, field, value):
    try:
        client = ctx.redis_handler.client
        result = await client.hset(key, field, value)
        ctx.log.debug("REDIS", f"!! HSET {key}[{field}] = {value}")
        return True  # 성공으로 처리
    except RedisError as e:
        ctx.log.error("REDIS", f"-- HSET error: {key}[{field}], {str(e)}")
        return False

# 해시 구조의 필드에 값 설정 / 다중필드
async def redis_hset_multi(ctx, key, field_dict: dict):
    try:
        client = ctx.redis_handler.client
        result = await client.hset(key, mapping=field_dict)
        ctx.log.debug("REDIS", f"!! HSET {key} = {field_dict}")
        return True
    except RedisError as e:
        ctx.log.error("REDIS", f"-- HSET error: {key}, {str(e)}")
        return False

# 해시 구조에서 특정 필드 값을 증가시키는 함수
# - return: 증가된 결과 값 (int) 또는 None (에러 시)
async def redis_hincrby(ctx, key, field, amount=1):
    try:
        client = ctx.redis_handler.client
        result = await client.hincrby(key, field, amount)
        ctx.log.debug("REDIS", f"++ HINCRBY {key}[{field}] += {amount} > {result}")
        return result  # 증가된 값 반환
    except RedisError as e:
        ctx.log.error("REDIS", f"-- HINCRBY error: {key}[{field}] += {amount}, {str(e)}")
        return None

# 해시 구조에서 필드 존재 여부 확인
# - return: True / False
async def redis_hexists(ctx, key, field):
    try:
        client = ctx.redis_handler.client
        exists = await client.hexists(key, field)
        ctx.log.debug("REDIS", f"== HEXISTS {key}[{field}] > {exists}")
        return exists
    except RedisError as e:
        ctx.log.error("REDIS", f"-- HEXISTS error: {key}[{field}], {str(e)}")
        return False

# 해시 구조에서 필드의 값 조회
# - return: 값 또는 None
async def redis_hget(ctx, key, field):
    try:
        client = ctx.redis_handler.client
        value = await client.hget(key, field)
        ctx.log.debug("REDIS", f"== HGET {key}[{field}] > {value}")
        return value
    except RedisError as e:
        ctx.log.error("REDIS", f"-- HGET error: {key}[{field}], {str(e)}")
        return None