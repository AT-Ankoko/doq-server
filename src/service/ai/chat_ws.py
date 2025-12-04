from fastapi import APIRouter, WebSocket
from src.service.messaging.ws_processor import processor
from src.utils.chat_stream_utils import store_chat_message
from src.service.ai.chat_state_manager import SessionStateCache, ChatStateManager, ChatStep, ChatEvent
from src.service.ai.llm_manager import LLMManager

from src.service.ai.asset.prompts.prompts_cfg import SYSTEM_PROMPTS
from src.service.ai.asset.prompts.doq_chat_scenario import (
    NORMAL_RESPONSE_PROMPT_TEMPLATE,
    STEP_TRANSITION_PROMPT_TEMPLATE
)
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
                {"hd": response["hd"], "bd": response["bd"], "sid": sid}
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
        
        # 3.5. 사용자 입력을 Redis 스트림에 저장
        await store_chat_message(
            ctx, sid, user_role,
            {"hd": {"sid": sid, "event": ChatEvent.CHAT_MESSAGE.value, "role": user_role}, 
             "bd": {"text": user_query}}
        )
        
        # 4. "확정" 키워드 체크 → 다음 step으로 (이동만 하고 계속 진행)
        confirmation_message_sent = False
        if state_manager.handle_user_confirm(user_query):
            next_step = state_manager.move_to_next_step()
            SessionStateCache.save(state_manager)
            ctx.log.info(f"[WS]        -- User confirmed, moved to next step: {next_step.value}")
            
            # 확정 메시지 전송 (다음 단계 안내)
            response_text = f"다음 단계로 이동합니다. (현재: {next_step.value})"
            confirmation_response = {
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
                {"hd": confirmation_response["hd"], "bd": confirmation_response["bd"], "sid": sid}
            )
            await websocket.send_json(confirmation_response)
            confirmation_message_sent = True
            # 계속 진행하여 다음 step의 프롬프트도 전송
        
        # 5. 대화 이력 가져오기 (Redis에서)
        chat_history = []
        stream_key = f"chat:session:{sid}"
        try:
            redis_client = ctx.redis_handler.get_client()
            messages = await redis_client.xrange(stream_key, count=20)  # 최근 20개 메시지
            
            for msg_id, fields in messages:
                # fields가 dict인지 확인
                if not isinstance(fields, dict):
                    ctx.log.debug(f"[WS]        -- Unexpected fields type: {type(fields)}")
                    continue
                
                # body는 JSON 문자열로 저장되어 있음
                body_json = fields.get("body", "{}")
                participant_field = fields.get("participant", "user")  # Redis에 저장된 participant 필드 사용
                
                # body_json을 dict로 파싱
                if isinstance(body_json, str):
                    try:
                        body_data = orjson.loads(body_json)
                    except Exception as parse_err:
                        ctx.log.warning(f"[WS]        -- Failed to parse body JSON: {parse_err}, body_json={body_json}")
                        continue
                else:
                    body_data = body_json
                
                # body_data가 dict여야 함
                if not isinstance(body_data, dict):
                    ctx.log.warning(f"[WS]        -- body_data is not dict, got {type(body_data)}: {body_data}")
                    continue
                
                text = body_data.get("bd", {}).get("text", "") if isinstance(body_data.get("bd"), dict) else ""
                
                if text:
                    chat_history.append(f"{participant_field}: {text}")
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to load chat history: {e}")
            import traceback
            ctx.log.debug(f"[WS]        -- Traceback: {traceback.format_exc()}")
            chat_history = []  # 이력 로드 실패 시 빈 배열로 계속 진행
        
        # 6. 현재 step에 맞는 프롬프트 가져오기
        current_step_prompt = state_manager.current_step.prompt
        
        # 6.5. 응답 분류 및 데이터 추출 (옵션: 사용자 응답 분석)
        # 현재 step이 introduction이 아닌 경우에만 응답 분석
        classification_result = None
        if state_manager.current_step != ChatStep.INTRODUCTION:
            try:
                classification_result = await manager.classify_response(
                    user_response=user_query,
                    current_step=state_manager.current_step.value,
                    user_name=state_manager.user_info.get("user_name"),
                    user_role=user_role
                )
                ctx.log.debug(f"[WS]        -- Response classification: {classification_result}")
                
                # 분류 결과에서 추출된 데이터 저장
                if classification_result.get("extracted_fields"):
                    for key, value in classification_result["extracted_fields"].items():
                        state_manager.update_data(key, value)
                
            except Exception as e:
                ctx.log.warning(f"[WS]        -- Response classification failed: {e}")
                classification_result = None
        
        # 7. LLM에 전달할 프롬프트 구성
        conversation_context = "\n".join(chat_history[-10:])  # 최근 10개만
        
        # 분류 결과가 있으면 clarification이 필요한지 체크
        if classification_result and classification_result.get("next_action") == "ask_clarification":
            # clarification이 필요한 경우
            response_text = classification_result.get("clarification_needed", "응답을 정확히 이해하기 위해 다시 설명해주실 수 있을까요?")
            ctx.log.info(f"[WS]        -- Clarification needed for step: {state_manager.current_step.value}")
        elif confirmation_message_sent:
            # 확정 메시지를 보낸 후, 다음 step의 시작 프롬프트 생성
            full_prompt = STEP_TRANSITION_PROMPT_TEMPLATE.format(system_prompt=SYSTEM_PROMPTS)
            full_prompt = full_prompt.replace("{{current_step}}", state_manager.current_step.value)
            full_prompt = full_prompt.replace("{{step_guide}}", current_step_prompt)
            full_prompt = full_prompt.replace("{{conversation_context}}", conversation_context)
            
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
        else:
            # 정상적인 LLM 응답 생성
            full_prompt = NORMAL_RESPONSE_PROMPT_TEMPLATE.format(system_prompt=SYSTEM_PROMPTS)
            full_prompt = full_prompt.replace("{{current_step}}", state_manager.current_step.value)
            full_prompt = full_prompt.replace("{{step_guide}}", current_step_prompt)
            full_prompt = full_prompt.replace("{{conversation_context}}", conversation_context)
            full_prompt = full_prompt.replace("{{user_role}}", user_role)
            full_prompt = full_prompt.replace("{{user_query}}", user_query)
            
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
            {"hd": response["hd"], "bd": response["bd"], "sid": sid}
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