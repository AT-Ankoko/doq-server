# handler/websocket_handler.py
from fastapi import WebSocket, WebSocketDisconnect
import orjson

class WebSocketHandler:
    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
        self.active_connections: list[WebSocket] = []
        self.session_map: dict[str, list[WebSocket]] = {}  # 1:N 세션 구조

    async def connect(self, websocket: WebSocket, id: str = None):
        """
        websocket에 세션 id를 속성으로 붙여둡니다.
        같은 세션 id로 여러 클라이언트가 접속 가능합니다.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

        # attach metadata to websocket object for easy lookup
        setattr(websocket, "_sid", id)

        if id:
            if id not in self.session_map:
                self.session_map[id] = []
            self.session_map[id].append(websocket)
            self.log.info("WS", f"- Connected: ID={id}, Client={websocket.client}, Session connections: {len(self.session_map[id])}")
        else:
            self.log.info("WS", f"- Connected: Client={websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
            # session_map에서도 제거
            sid = getattr(websocket, "_sid", None)
            if sid and sid in self.session_map:
                if websocket in self.session_map[sid]:
                    self.session_map[sid].remove(websocket)
                # 세션에 연결이 없으면 세션 제거
                if not self.session_map[sid]:
                    del self.session_map[sid]
                    self.log.info("WS", f"- Session {sid} removed (no active connections)")
            
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

                # Dispatch to processor / handlers
                # (각 핸들러에서 자신의 format으로 Redis에 저장하므로 여기서는 저장하지 않음)
                try:
                    response = await processor(self.ctx, websocket, msg)
                except Exception as e:
                    self.log.error("WS", f"- Handler error: {str(e)}")
                    response = {
                        "status": "error",
                        "message": str(e)
                    }

                # 핸들러가 응답을 이미 보냈다면 (response가 None) 다시 보내지 않음
                # NOTE: LLM 핸들러는 자체 send_json_safe()로 브로드캐스트하므로 여기서 중복 전송하지 않음
                if response is not None:
                    # 다른 핸들러의 응답은 세션 브로드캐스트
                    if sid:
                        await self.broadcast_to_session(sid, response)
                    else:
                        # sid가 없으면 발신자에게만 전송
                        await websocket.send_json(response)
                    self.log.debug("WS", f"<< Send response: {response}")

        except WebSocketDisconnect:
            self.disconnect(websocket)

        except Exception as e:
            self.log.error("WS", f"- Unexpected error: {str(e)}")
            try:
                error_msg = {
                    "status": "error",
                    "errMsg": str(e)
                }
                sid = getattr(websocket, "_sid", None)
                if sid:
                    # 세션에 브로드캐스트
                    await self.broadcast_to_session(sid, error_msg)
                else:
                    # sid가 없으면 발신자에게만 전송
                    await websocket.send_json(error_msg)
            except Exception:
                # If sending error message fails (e.g. socket closed), just ignore
                pass
            self.disconnect(websocket)

    async def broadcast_to_session(self, sid: str, message: dict, exclude_sender: WebSocket = None):
        """
        같은 세션의 모든 클라이언트에게 메시지를 브로드캐스트합니다.
        exclude_sender가 지정되면 발신자를 제외합니다.
        """
        if sid not in self.session_map:
            self.log.warning("WS", f"- Session {sid} not found for broadcast")
            return
        
        failed_clients = []
        for ws in self.session_map[sid]:
            # 발신자 제외 옵션
            if exclude_sender and ws is exclude_sender:
                continue
            
            try:
                await ws.send_json(message)
            except Exception as e:
                self.log.warning("WS", f"- Failed to broadcast to {ws.client}: {e}")
                failed_clients.append(ws)
        
        # 실패한 클라이언트는 연결 해제 처리
        for ws in failed_clients:
            self.disconnect(ws)

    async def disconnect_all(self):
        self.log.info("WS", "- Disconnecting all clients...")
        for websocket in list(self.active_connections):  # 복사본 사용
            try:
                await websocket.close()
            except Exception as e:
                self.log.warning("WS", f"- Failed to close client {websocket.client}: {e}")
            self.disconnect(websocket)  # 내부적으로 remove + log