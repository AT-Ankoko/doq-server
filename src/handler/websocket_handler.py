# handler/websocket_handler.py
from fastapi import WebSocket, WebSocketDisconnect
import orjson

class WebSocketHandler:
    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
        self.active_connections: list[WebSocket] = []
        self.session_map: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
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