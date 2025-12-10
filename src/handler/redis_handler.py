# handler/redis_handler.py

from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError

class RedisHandler:
    def __init__(self, ctx):
        self.log = ctx.log
        self.cfg = ctx.cfg.redis
        self.client: Redis = None

    async def connect(self):
        try:
            if self.client:
                try:
                    if await self.client.ping():
                        self.log.info("REDIS", " == Already connected")
                        return
                except Exception:
                    self.log.warning("REDIS", " - Ping failed, reconnecting")
                    pass  # 연결 끊겼을 수 있음 재연결 진행

            self.log.debug("REDIS", " - Connecting...")
            self.client = Redis(
                host=self.cfg.host,
                port=self.cfg.port,
                db=self.cfg.db,
                password=self.cfg.password,
                decode_responses=True,
                ssl=self.cfg.ssl,
                ssl_cert_reqs=None
            )

            if await self.client.ping():
                self.log.info("REDIS", " == Connected")
            else:
                self.log.warning("REDIS", " - Ping returned false")

        except (RedisError, ConnectionError) as e:
            self.log.error("REDIS", f" -- Connection error: {str(e)}")
            raise
        
    async def reconnect(self):
        self.log.info("REDIS", " -- Reconnecting to Redis...")
        await self.disconnect()
        await self.connect()

    async def disconnect(self):
        if self.client:
            try:
                self.log.debug("REDIS", "  - Disconnecting...")
                await self.client.close()
                self.log.info("REDIS", "  -- Disconnected")
            except Exception as e:
                self.log.warning("REDIS", f" - Disconnect failed: {str(e)}")

    # 사용할 때 비동기 호출 (await client.get(...))
    def get_client(self) -> Redis:
        if not self.client:
            self.log.error("REDIS", " - Client not connected")
            raise RuntimeError("Redis client is not connected")
        return self.client
