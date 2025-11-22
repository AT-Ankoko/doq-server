from fastapi import APIRouter, WebSocket
from src.service.messaging.ws_processor import processor
from src.utils.chat_stream_utils import store_chat_message

from src.service.ai.asset.prompts.prompts_cfg import SYSTEM_PROMPTS
import src.common.common_codes as codes

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

async def handle_llm_invocation(ctx, websocket, msg: dict):
    """
    LLM 호출을 처리합니다.
    - LLM 호출 로깅
    - 향후 실제 LLM 호출 (Gemini) 추가
    - 결과를 Redis Stream에 저장
    """
    try:
        hd = msg.get("hd", {}) or {}
        sid = hd.get("sid") or getattr(websocket, '_sid', None) or "unknown"
        asker = hd.get("asker") or hd.get("role") or "user"

        ctx.log.info("WS", f"-- LLM invocation (asker={asker}) in session {sid}")
        ctx.log.debug("WS", f"-- Message: {msg}")

        state_msg = {
            "hd": {
                "sid": sid,
                "event": "llm.state", 
            },
            "bd": {
                "state": { 
                    "code": codes.ResponseStatus.SUCCESS["code"], 
                    "msg": "generation_started"
                }
            },
        }
        try:
            await websocket.send_json(state_msg)
            ctx.log.debug("WS", f"<< Sent LLM generation state: {state_msg}")
        except Exception as e:
            ctx.log.warning("WS", f"-- Failed to send LLM state message: {e}")

        manager = ctx.llm_manager
        if manager is None or not callable(getattr(manager, 'generate', None)):
            err = codes.ResponseStatus.SERVER_ERROR
            ctx.log.error("WS", "-- No LLM manager available")
            error_msg = {
                "hd": {
                    "sid": sid,
                    "event": "llm.error", 
                    "role": "llm", 
                    "asker": asker
                },
                "bd": {
                    "code": err['code'], 
                    "msg": err['msg'], 
                    "detail": "No LLM manager configured"
                },
            }
            return error_msg

        # 3) 실제 LLM 호출
        try:
            resp_text = await manager.generate(
                SYSTEM_PROMPTS,
                placeholders={
                    'user_name': asker,
                },
                temperature=0.7
            )
        except Exception as e:
            ctx.log.error("WS", f"-- LLM generate failed: {e}")
            err = codes.ResponseStatus.SERVER_ERROR
            error_msg = {
                "hd": {
                    "sid": sid,
                    "event": "llm.error", 
                    "role": "llm", 
                    "asker": asker
                },
                "bd": {
                    "code": err['code'], 
                    "msg": err['msg'], 
                    "detail": str(e)
                }
            }
            return error_msg

        # 4) LLM 응답 생성 및 저장
        # llm.response 메시지에는 'asker' 필드 유지
        llm_response = {
            "hd": {
                "sid": sid,
                "event": "llm.response", 
                "role": "llm", 
                "asker": asker 
            },
            "bd": {
                "text": resp_text, 
                "state": { 
                    "code": codes.ResponseStatus.SUCCESS['code'],
                    "msg": codes.ResponseStatus.SUCCESS['msg']
                }
            }
        }

        await store_chat_message(ctx, sid, "llm", llm_response)
        
        return llm_response

    except Exception as e:
        ctx.log.error("WS", f"-- LLM invocation unexpected error: {e}")
        err = codes.ResponseStatus.SERVER_ERROR
        sid = msg.get("hd", {}).get("sid", "unknown")

        error_msg = {
            "hd": {
                "sid": sid,
                "event": "llm.error", 
                "role": "llm"
            },
            "bd": {
                "code": err['code'], 
                "msg": err['msg'], 
                "detail": str(e)
            },
        }
        try:
            await websocket.send_json(error_msg)
        except Exception:
            pass
        return error_msg