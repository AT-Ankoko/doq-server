from fastapi import APIRouter, WebSocket
from src.service.messaging.ws_processor import processor
from src.utils.chat_stream_utils import store_chat_message
from src.service.ai.chat_state_manager import SessionStateCache, ChatStateManager, ChatStep, ChatEvent
from src.service.ai.llm_manager import LLMManager

from src.service.ai.asset.prompts.prompts_cfg import SYSTEM_PROMPTS
import src.common.common_codes as codes
import orjson

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
    """LLM 호출 처리"""
    try:
        sid = msg.get("sid")
        hd = msg.get("hd", {})
        bd = msg.get("bd", {})
        asker = hd.get("asker") or hd.get("role")
        user_query = bd.get("text") or ""
        
        ctx.log.info(f"[WS]        -- LLM invocation (asker={asker}) in session {sid}")
        ctx.log.debug(f"[WS]        -- Message: {msg}")
        
        # 1. 프롬프트 인젝션 체크 (설정 파일의 LLM 매니저 사용)
        manager = ctx.llm_manager
        if manager._is_prompt_injection(user_query):
            ctx.log.warning(f"[WS]        -- Prompt injection detected: {user_query[:50]}")
            response_text = "아직 없는 기능입니다"
            
            response = {
                "hd": {
                    "sid": sid,
                    "event": ChatEvent.LLM_RESPONSE.value,
                    "role": "llm",
                    "asker": asker,
                },
                "bd": {
                    "text": response_text,
                    "state": codes.ResponseStatus.SUCCESS
                }
            }
            
            await store_chat_message(
                ctx, sid, "llm", 
                orjson.dumps({"hd": response["hd"], "bd": response["bd"], "sid": sid}).decode("utf-8")
            )
            await websocket.send_json(response)
            return
        
        # 2. 세션 상태 로드 또는 생성
        state_manager = SessionStateCache.get(sid)
        if not state_manager:
            user_info = {
                "user_name": hd.get("user_name") or hd.get("asker"),
                "user_role": hd.get("user_role") or hd.get("role"),
                "contract_date": hd.get("contract_date"),
            }
            state_manager = ChatStateManager(sid, user_info)
            SessionStateCache.save(state_manager)
            ctx.log.info(f"[WS]        -- New session state created for {sid}, user: {user_info.get('user_name')} ({user_info.get('user_role')})")
        else:
            ctx.log.debug(f"[WS]        -- Loaded session state for {sid}, current_step: {state_manager.current_step.value}")
        
        # 3. 사용자 입력 기록
        user_role = state_manager.user_info.get("user_role", "갑")
        state_manager.add_role_input(user_role, user_query)
        
        # 4. "확정" 키워드 체크 → 다음 step으로
        if state_manager.handle_user_confirm(user_query):
            next_step = state_manager.move_to_next_step()
            SessionStateCache.save(state_manager)
            ctx.log.info(f"[WS]        -- User confirmed, moved to next step: {next_step.value}")
            
            response_text = f"다음 단계로 이동합니다. (현재: {next_step.value})"
            response = {
                "hd": {
                    "sid": sid,
                    "event": ChatEvent.LLM_RESPONSE.value,
                    "role": "llm",
                    "asker": asker,
                    "step": next_step.value
                },
                "bd": {
                    "text": response_text,
                    "state": codes.ResponseStatus.SUCCESS
                }
            }
            
            await store_chat_message(
                ctx, sid, "llm",
                orjson.dumps({"hd": response["hd"], "bd": response["bd"], "sid": sid}).decode("utf-8")
            )
            await websocket.send_json(response)
            return
        
        # 5. 대화 이력 가져오기 (Redis에서)
        chat_history = []
        stream_key = f"chat:session:{sid}"
        try:
            redis_client = ctx.redis_handler.get_client()
            messages = await redis_client.xrange(stream_key, count=20)  # 최근 20개 메시지
            
            for msg_id, fields in messages:
                # fields가 dict인지 확인
                if isinstance(fields, dict):
                    body_json = fields.get("body", "{}")
                else:
                    ctx.log.debug(f"[WS]        -- Unexpected fields type: {type(fields)}")
                    continue
                
                # body_json이 이미 dict일 수도 있음
                if isinstance(body_json, str):
                    body_data = orjson.loads(body_json)
                else:
                    body_data = body_json
                
                participant = body_data.get("hd", {}).get("role", "user")
                text = body_data.get("bd", {}).get("text", "")
                
                if text:
                    chat_history.append(f"{participant}: {text}")
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to load chat history: {e}")
            import traceback
            ctx.log.debug(f"[WS]        -- Traceback: {traceback.format_exc()}")
            chat_history = []  # 이력 로드 실패 시 빈 배열로 계속 진행
        
        # 6. 현재 step에 맞는 프롬프트 구성
        step_prompts = {
            ChatStep.INTRODUCTION: "사용자를 환영하고, 계약서 작성을 시작합니다.",
            ChatStep.WORK_SCOPE: "작업 범위(예: 로고 디자인, 웹 디자인 등)를 구체적으로 질문하세요.",
            ChatStep.WORK_PERIOD: "작업 기간(시작일, 종료일)을 질문하세요.",
            ChatStep.BUDGET: "대금(금액, 지급 조건)을 질문하세요.",
            ChatStep.REVISIONS: "수정 횟수 및 조건을 질문하세요.",
            ChatStep.COPYRIGHT: "저작권 귀속(갑/을)을 질문하세요.",
            ChatStep.CONFIDENTIALITY: "기밀 유지 조항 및 특약 사항을 질문하세요.",
            ChatStep.FINALIZATION: "모든 조건을 최종 확인하고 계약서 생성을 안내하세요.",
        }
        
        current_step_prompt = step_prompts.get(state_manager.current_step, "")
        
        # 7. LLM에 전달할 프롬프트 구성
        conversation_context = "\n".join(chat_history[-10:])  # 최근 10개만
        
        full_prompt = f"""{SYSTEM_PROMPTS}

현재 단계: {state_manager.current_step.value}
단계별 가이드: {current_step_prompt}

이전 대화:
{conversation_context}

사용자({user_role}): {user_query}

위 대화 맥락을 고려하여, 현재 단계({state_manager.current_step.value})에 맞는 질문이나 안내를 자연스럽게 해주세요.
"""
        
        # 8. LLM 호출 (플레이스홀더 치환을 위해 사용자 정보 전달)
        placeholders = {
            "user_name": state_manager.user_info.get("user_name") or asker,
            "user_role": state_manager.user_info.get("user_role") or hd.get("role"),
            "contract_date": state_manager.user_info.get("contract_date") or hd.get("contract_date"),
        }
        response_text = await manager.generate(
            full_prompt,
            placeholders=placeholders,
            max_output_tokens=500,
            temperature=0.7
        )
        
        # 응답이 비어있는 경우 체크
        if not response_text or response_text.strip() == "":
            ctx.log.warning(f"[WS]        -- Empty response from LLM for session {sid}")
            response_text = "죄송합니다. 응답을 생성할 수 없습니다. 다시 시도해주세요."
        
        # 9. 응답 저장 및 전송
        response = {
            "hd": {
                "sid": sid,
                "event": ChatEvent.LLM_RESPONSE.value,
                "role": "llm",
                "asker": asker,
                "step": state_manager.current_step.value
            },
            "bd": {
                "text": response_text,
                "state": codes.ResponseStatus.SUCCESS
            }
        }
        
        await store_chat_message(
            ctx, sid, "llm",
            orjson.dumps({"hd": response["hd"], "bd": response["bd"], "sid": sid}).decode("utf-8")
        )
        
        ctx.log.info(f"[WS]        -- LLM response sent (step: {state_manager.current_step.value})")
        await websocket.send_json(response)
        
        # 10. 상태 저장
        SessionStateCache.save(state_manager)
        
    except Exception as e:
        ctx.log.error(f"[WS]        -- LLM invocation unexpected error: {e}")
        await websocket.send_json({
            "hd": {"sid": sid, "event": ChatEvent.LLM_ERROR.value, "role": "llm"},
            "bd": {"state": codes.ResponseStatus.SERVER_ERROR, "detail": str(e)}
        })