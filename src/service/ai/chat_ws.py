# 웹소켓 기본 예제
# 웹소켓 핸들러를 사용하여 클라이언트와 서버 간의 메시지를 주고받는 예제임.
# routes/chat_ws.py

from fastapi import APIRouter, WebSocket
from src.service.messaging.ws_processor import processor

router = APIRouter(prefix="/v1/session", tags=["Session"])

@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    ctx = websocket.app.state.ctx

    # 쿼리 파라미터에서 sid 추출
    sid = websocket.query_params.get("sid")
    if not sid:
        await websocket.close(code=4001)
        return

    # sid 전달하여 로그용 식별자 사용
    await ctx.ws_handler.connect(websocket, id=sid)
    await ctx.ws_handler.receive_and_respond(websocket, processor=processor)