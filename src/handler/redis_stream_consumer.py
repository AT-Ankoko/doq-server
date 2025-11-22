from src.utils.event_dispatcher_utils import dispatch_event
from redis.exceptions import ResponseError
import asyncio

from src.service.messaging.redis_stream_processor import processor

class RedisStreamConsumer:
    def __init__(self, ctx):
        self.ctx = ctx
        cfg = ctx.cfg.redis_consumer
        self.stream_key = cfg.stream_key           # 예: "ankoko:task:stream"
        self.group_name = cfg.group_name           # 예: "worker-group"
        self.consumer_name = cfg.consumer_name     # 예: "consumer-1"

    async def init_group(self):
        try:
            await self.ctx.redis_handler.client.xgroup_create(
                name=self.stream_key, groupname=self.group_name, id="0", mkstream=True
            )
            self.ctx.log.info("REDIS", f"- Consumer group '{self.group_name}' created on stream '{self.stream_key}'")
        except ResponseError as e:
            if "BUSYGROUP" in str(e):
                self.ctx.log.info("REDIS", f"- Consumer group '{self.group_name}' already exists")
            else:
                self.ctx.log.error("REDIS", f"!! Failed to create group '{self.group_name}': {e}")
                raise

    async def consume(self):
        self.ctx.log.info(
            "REDIS",
            f"- Redis consumer starting: group={self.group_name}, stream={self.stream_key}, consumer={self.consumer_name}"
        )

        while True:
            try:
                resp = await self.ctx.redis_handler.client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_key: '>'},
                    count=1,
                    block=1000
                )

                if not resp:
                    continue

                for stream, messages in resp:
                    self.ctx.log.debug("REDIS", f"== Received {len(messages)} message(s) from stream '{stream}'")
                    for msg_id, fields in messages:
                        self.ctx.log.debug("REDIS", f"-- Handling message ID {msg_id} | fields={fields}")
                        asyncio.create_task(self._process_message(msg_id, fields))

            except Exception as e:
                self.ctx.log.error("REDIS", f"!! Error while consuming stream: {e}")
                
                if "Buffer is closed" in str(e) or "Connection closed" in str(e):
                    self.ctx.log.warning("REDIS", ">> Detected closed buffer. Attempting reconnect...")
                    try:
                        await self.ctx.redis_handler.reconnect()
                    except Exception as re:
                        self.ctx.log.error("REDIS", f"!! Reconnect failed: {re}")
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(1)

    # 비동기 처리 분리 함수
    async def _process_message(self, msg_id, fields):
        try:
            await processor(self.ctx, fields)
            await self.ctx.redis_handler.client.xack(self.stream_key, self.group_name, msg_id)
            self.ctx.log.debug("REDIS", f"-- Acknowledged message ID {msg_id}")
        except Exception as e:
            self.ctx.log.error("REDIS", f"!! Failed to process message {msg_id}: {e}")

    async def stop(self):
        # 소비 루프 중단 및 Redis 연결 해제
        self._running = False
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
        try:
            await self.ctx.redis_handler.client.close()
            self.ctx.log.info("REDIS", f">> Connection closed for '{self.stream_key}'")
        except Exception as e:
            self.ctx.log.error("REDIS", f"!! Error closing connection: {e}")