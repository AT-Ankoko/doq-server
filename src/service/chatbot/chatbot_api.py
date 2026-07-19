from typing import Any, Dict

from fastapi import APIRouter, Request, WebSocket

from src.service.chatbot.chatbot_schema import ChatbotPreviewRequest
from src.service.chatbot.chatbot_service import ChatbotService

router = APIRouter(prefix="/api/session", tags=["Session"])


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    ctx = websocket.app.state.ctx
    service = ChatbotService(ctx)
    await service.handle_websocket_connection(websocket)


@router.post("/respond")
async def preview_response(request: Request, body: ChatbotPreviewRequest) -> Dict[str, Any]:
    ctx = request.app.state.ctx
    service = ChatbotService(ctx)
    return await service.build_preview_response(body)
