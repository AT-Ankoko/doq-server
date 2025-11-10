# websocket_handler.py

from fastapi import WebSocket, WebSocketDisconnect
import time

class WebSocketHandler:
    def __init__(self, ctx):
        self.log = ctx.log
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.log.debug(f"Connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.log.debug(f"Disconnected: {websocket.client}")

    async def receive_and_respond(self, websocket: WebSocket, mode="default"):
        try:
            while True:
                message = await websocket.receive_text()
                self.log.debug(f"[{mode.upper()}] Received: {message}")

                start_time = time.time()
                response = {
                    "status": "success",
                    "mode": mode,
                    "timestamp": start_time,
                    "echo": message
                }
                await websocket.send_json(response)
                self.log.debug(f"[{mode.upper()}] send response: {response}")

        except WebSocketDisconnect:
            self.disconnect(websocket)

        except Exception as e:
            await websocket.send_json({
                "status": "error",
                "message": str(e)
            })
            self.disconnect(websocket)
