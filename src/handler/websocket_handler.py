# handler/websocket_handler.py
from fastapi import WebSocket, WebSocketDisconnect
import orjson

from utils.chat_stream_utils import store_chat_message

class WebSocketHandler:
    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
        self.active_connections: list[WebSocket] = []
        self.session_map: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, id: str = None):
        """
        websocket에 세션 id를 속성으로 붙여둡니다.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

        # attach metadata to websocket object for easy lookup
        setattr(websocket, "_sid", id)

        if id:
            self.session_map[id] = websocket
            self.log.info("WS", f"- Connected: ID={id}, Client={websocket.client}")
        else:
            self.log.info("WS", f"- Connected: Client={websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.log.info("WS", f"- Disconnected: Client={websocket.client}")

    async def receive_and_respond(self, websocket: WebSocket, processor):
        try:
            while True:
                str_msg = await websocket.receive_text()
                msg = orjson.loads(str_msg)
                self.log.debug("WS", f">> Received message: {msg}")

                hd = msg.get("hd", {}) if isinstance(msg.get("hd", {}), dict) else {}
                sid = hd.get("sid") or getattr(websocket, "_sid", None)
                
                role = hd.get("role", "user")

                hd["asker"] = role
                msg["hd"] = hd

                if sid:
                    msg.setdefault("sid", sid)
                    hd["sid"] = sid

                # Persist to Redis Stream for the session
                try:
                    if sid:
                        # 저장용으로 role는 별도 인자로 전달
                        store_msg = dict(msg)
                        store_msg.pop("role", None)
                        await store_chat_message(self.ctx, sid, role, store_msg)
                except Exception as e:
                    self.log.error("WS", f"-- Failed to persist chat to stream: {e}")

                # Dispatch to processor / handlers
                try:
                    response = await processor(self.ctx, websocket, msg)
                except Exception as e:
                    self.log.error("WS", f"- Handler error: {str(e)}")
                    response = {
                        "status": "error",
                        "message": str(e)
                    }

                await websocket.send_json(response)
                self.log.debug("WS", f"<< Send response: {response}")

        except WebSocketDisconnect:
            self.disconnect(websocket)

        except Exception as e:
            self.log.error("WS", f"- Unexpected error: {str(e)}")
            await websocket.send_json({
                "status": "error",
                "errMsg": str(e)
            })
            self.disconnect(websocket)

    async def disconnect_all(self):
        self.log.info("WS", "- Disconnecting all clients...")
        for websocket in list(self.active_connections):  # 복사본 사용
            try:
                await websocket.close()
            except Exception as e:
                self.log.warning("WS", f"- Failed to close client {websocket.client}: {e}")
            self.disconnect(websocket)  # 내부적으로 remove + log