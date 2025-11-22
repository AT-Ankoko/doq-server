# 웹소켓 기본 예제
# 웹소켓 핸들러를 사용하여 클라이언트와 서버 간의 메시지를 주고받는 예제임.
# routes/chat_ws.py

from fastapi import APIRouter, WebSocket
from src.service.messaging.ws_processor import processor
from src.utils.chat_stream_utils import store_chat_message

from src.service.ai.asset.prompts.prompts_cfg import SYSTEM_PROMPTS

router = APIRouter(prefix="/v1/session", tags=["Session"])

async def handle_user_message(ctx, websocket, msg: dict):
    """
    사용자 메시지를 처리합니다.
    - 메시지 로깅
    - Redis Stream에 저장
    - 클라이언트에 확인 응답 전송
    """
    try:
        # 메시지에서 필요한 정보 추출
        sid = msg.get("sid", "unknown")
        participant = msg.get("participant", "user")
        
        ctx.log.info("WS", f"-- User message from {participant} in session {sid}")
        ctx.log.debug("WS", f"-- Message: {msg}")
        
        # 사용자 메시지 확인 응답
        response = {
            "hd": {"event": "chat.message.ack", "role": "server"},
            "bd": {"status": "received"},
            "sid": sid,
            "participant": "server"
        }
        
        return response
    
    except Exception as e:
        ctx.log.error("WS", f"-- User message handling error: {e}")
        sid = msg.get("sid", "unknown")
        return {
            "hd": {"event": "chat.message.error", "role": "server"},
            "bd": {"text": f"메시지 처리 오류: {str(e)}"},
            "sid": sid,
            "participant": "server"
        }

async def handle_llm_invocation(ctx, websocket, msg: dict):
    """
    LLM 호출을 처리합니다.
    - LLM 호출 로깅
    - 향후 실제 LLM 호출 (Gemini) 추가
    - 결과를 Redis Stream에 저장
    """
    try:
        # 메시지에서 필요한 정보 추출
        sid = msg.get("sid", "unknown")
        participant = msg.get("participant", "user")
        
        ctx.log.info("WS", f"-- LLM invocation from {participant} in session {sid}")
        ctx.log.debug("WS", f"-- Message: {msg}")
        
        # TODO: 실제 LLM 호출 구현
        resp_text = await ctx.llm_manager.generate(
            SYSTEM_PROMPTS,
            placeholders = {
                'user_name': participant,
            },
            temperature=0.7
        )

        # 현재는 mock 응답만 반환
        llm_response = {
            "hd": {"event": "llm.response", "role": "llm"},
            "bd": {"text": resp_text},
            "sid": sid,
            "participant": "llm"
        }
        
        # Redis Stream에 LLM 응답 저장
        await store_chat_message(ctx, sid, "llm", llm_response)
        
        return llm_response
    
    except Exception as e:
        ctx.log.error("WS", f"-- LLM invocation error: {e}")
        sid = msg.get("sid", "unknown")
        return {
            "hd": {"event": "llm.error", "role": "llm"},
            "bd": {"text": f"LLM 오류: {str(e)}"},
            "sid": sid,
            "participant": "llm"
        }

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
    
    # receive_and_respond는 순수하게 메시지 중계만 담당
    # 클라이언트에서 보내는 메시지의 hd["role"] 필드로 participant를 지정합니다.
    # 예: {"hd": {"event": "chat.message", "role": "A"}, "bd": {...}}
    
    # 여기서는 receive_and_respond에 LLM 처리 콜백을 넘길 수도 있지만,
    # 현재는 ws_handler가 단순 중계만 하므로 향후 필요시 별도 핸들러 추가
    await ctx.ws_handler.receive_and_respond(websocket, processor=processor)
