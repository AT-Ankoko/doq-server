from fastapi import APIRouter, WebSocket
from src.service.messaging.ws_processor import processor
from src.utils.chat_stream_utils import store_chat_message
from src.service.ai.chat_state_manager import SessionStateCache, ChatStateManager, ChatStep, ChatEvent

import src.service.ai.asset.prompts.prompts_cfg as prompt
from src.service.ai.rag_manager import RAGManager
from src.service.ai.chat_session_manager import ChatSessionManager

import orjson
import json
import re
from datetime import datetime

router = APIRouter(prefix="/api/session", tags=["Session"])

@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    ctx = websocket.app.state.ctx

    # 쿼리 파라미터에서 sid 추출
    sid = websocket.query_params.get("sid")
    ctx.log.info(f"[WS] Connection request: sid={sid}, query_params={websocket.query_params}")
    if not sid:
        await websocket.close(code=4001)
        return

    # sid 전달하여 로그용 식별자 사용
    is_first_connection = len(ctx.ws_handler.session_map.get(sid, [])) == 0
    await ctx.ws_handler.connect(websocket, id=sid)

    # 연결 직후 선제 인사 전송 (최초 연결 시에만)
    if is_first_connection:
        try:
            # Redis에서 세션 정보 로드
            session_key = f"session:info:{sid}"
            session_info_json = None
            client_name = "의뢰인"
            provider_name = "용역자"
            contract_date = None
            
            try:
                redis_client = ctx.redis_handler.get_client()
                session_info_json = await redis_client.get(session_key)
                if session_info_json:
                    session_info = orjson.loads(session_info_json)
                    client_name = session_info.get("client_name") or "의뢰인"
                    provider_name = session_info.get("provider_name") or "용역자"
                    contract_date = session_info.get("contract_date")
                else:
                    # Redis에 없으면 쿼리 파라미터에서 읽어서 Redis에 저장 (최초 1회)
                    client_name = websocket.query_params.get("client_name") or "의뢰인"
                    provider_name = websocket.query_params.get("provider_name") or "용역자"
                    contract_date = websocket.query_params.get("contract_date")
                    
                    # Redis에 저장
                    new_info = {
                        "client_name": client_name,
                        "provider_name": provider_name,
                        "contract_date": contract_date
                    }
                    await redis_client.set(session_key, orjson.dumps(new_info))

            except Exception as e:
                ctx.log.warning(f"[WS]        -- Failed to load session info from Redis: {e}")
                # 폴백: 쿼리 파라미터에서 읽기
                client_name = websocket.query_params.get("client_name") or "의뢰인"
                provider_name = websocket.query_params.get("provider_name") or "용역자"
                contract_date = websocket.query_params.get("contract_date")

            # START_MESSAGE_PROMPT 렌더링 (간단 치환)
            greeting_text = prompt.START_MESSAGE_PROMPT
            greeting_text = greeting_text.replace("{{client_name}}", client_name)
            greeting_text = greeting_text.replace("{{service_provider_name}}", provider_name)

            greeting_response = {
                "hd": {
                    "sid": sid,
                    "event": ChatEvent.LLM_RESPONSE.value,
                    "role": "assistant",
                    "asker": None,
                    "step": ChatStep.INTRODUCTION.value,
                    "user_name": client_name,
                    "role_name": "client",
                    "contract_date": contract_date,
                },
                "bd": {
                    "text": greeting_text,
                    "contract_draft": None,
                    "state": codes.ResponseStatus.SUCCESS,
                },
            }
            await store_chat_message(
                ctx,
                sid,
                "assistant",
                {"hd": greeting_response["hd"], "bd": greeting_response["bd"], "sid": sid},
            )
            # 초기 인사 메시지를 세션의 모든 클라이언트에게 브로드캐스트
            await ctx.ws_handler.broadcast_to_session(sid, greeting_response)
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to send initial greeting: {e}")
    else:
        # 후속 접속 시: Redis에서 채팅 히스토리 로드 및 전송
        try:
            redis_client = ctx.redis_handler.get_client()
            stream_key = f"session:chat:{sid}"
            messages = await redis_client.xrange(stream_key, count=50)  # 최근 50개
            
            ctx.log.info(f"[WS]        -- Loading chat history for late-joined user: {len(messages)} messages")
            
            for msg_id, fields in messages:
                try:
                    if not isinstance(fields, dict):
                        continue
                    
                    body_json = fields.get("body", "{}")
                    participant = fields.get("participant", "user")
                    
                    if isinstance(body_json, str):
                        body_data = orjson.loads(body_json)
                    else:
                        body_data = body_json
                    
                    # 히스토리 메시지 구성
                    history_msg = {
                        "hd": body_data.get("hd", {
                            "sid": sid,
                            "event": ChatEvent.CHAT_MESSAGE.value,
                            "role": participant,
                        }),
                        "bd": body_data.get("bd", {"text": "", "state": codes.ResponseStatus.SUCCESS})
                    }
                    
                    # 헤더 보충
                    if "sid" not in history_msg["hd"]:
                        history_msg["hd"]["sid"] = sid
                    if "event" not in history_msg["hd"]:
                        history_msg["hd"]["event"] = ChatEvent.CHAT_MESSAGE.value
                    if "role" not in history_msg["hd"]:
                        history_msg["hd"]["role"] = participant
                    
                    # 새로 접속한 클라이언트에게만 히스토리 전송
                    await websocket.send_json(history_msg)
                    
                except Exception as hist_err:
                    ctx.log.warning(f"[WS]        -- Failed to send history message: {hist_err}")
                    continue
            
            ctx.log.info(f"[WS]        -- Chat history loaded and sent to late-joined user")
            
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to load chat history: {e}")

    await ctx.ws_handler.receive_and_respond(websocket, processor=processor)

async def handle_llm_invocation(ctx, websocket, msg: dict):
    """
    간소화된 LLM 호출 처리
    - 프롬프트 인젝션 체크
    - 세션 관리
    - ChatSessionManager에 위임
    """
    sid = msg.get("sid")
    hd = msg.get("hd", {})
    bd = msg.get("bd", {})
    asker = hd.get("asker") or hd.get("role")
    user_query = bd.get("text") or ""
    role = hd.get("role", "client")

    async def send_json_safe(payload):
        """세션에 응답 브로드캐스트"""
        try:
            await ctx.ws_handler.broadcast_to_session(sid, payload)
        except Exception as send_err:
            ctx.log.warning(f"[WS] Broadcast failed: {send_err}")

    try:
        ctx.log.info(f"[WS] LLM invocation (asker={asker}) in session {sid}")
        
        # 1단계: 프롬프트 인젝션 체크
        manager = ctx.llm_manager
        if manager._is_prompt_injection(user_query):
            ctx.log.warning(f"[WS] Prompt injection detected: {user_query[:50]}")
            injection_response = {
                "hd": {
                    "sid": sid,
                    "event": ChatEvent.LLM_RESPONSE.value,
                    "role": "assistant",
                    "asker": asker,
                },
                "bd": {
                    "text": "아직 없는 기능입니다",
                    "state": codes.ResponseStatus.SUCCESS
                }
            }
            await store_chat_message(ctx, sid, "assistant", 
                {"hd": injection_response["hd"], "bd": injection_response["bd"]})
            await send_json_safe(injection_response)
            return

        # 2단계: 세션 상태 로드/생성
        state_manager = await SessionStateCache.get(sid, ctx)
        if not state_manager:
            user_info = {
                "userId": hd.get("userId"),
                "client_name": hd.get("client_name"),
                "provider_name": hd.get("provider_name"),
            }
            state_manager = ChatStateManager(sid, user_info)
            await SessionStateCache.save(state_manager, ctx)
            ctx.log.info(f"[WS] New session state created for {sid}")
        
        # 3단계: 사용자 입력 기록
        state_manager.add_role_input(role, user_query)
        
        # 사용자 메시지 저장
        user_message_data = {
            "hd": {"sid": sid, "event": ChatEvent.CHAT_MESSAGE.value, "role": role},
            "bd": {"text": user_query}
        }
        await store_chat_message(ctx, sid, role, user_message_data)
        
        # 다른 세션 참여자에게 브로드캐스트
        user_broadcast = {
            "hd": {
                "sid": sid,
                "event": ChatEvent.CHAT_MESSAGE.value,
                "role": role,
                "asker": role,
                "user_name": state_manager.user_info.get("user_name") or role,
                "role_name": state_manager.user_info.get("role"),
                "contract_date": state_manager.user_info.get("contract_date"),
            },
            "bd": {
                "text": user_query,
                "state": codes.ResponseStatus.SUCCESS
            }
        }
        await ctx.ws_handler.broadcast_to_session(sid, user_broadcast, exclude_sender=websocket)

        # 4단계: 대화 이력 로드
        chat_history = []
        previous_contract_draft = None
        stream_key = f"session:chat:{sid}"
        try:
            redis_client = ctx.redis_handler.get_client()
            messages = await redis_client.xrange(stream_key, count=20)
            
            for msg_id, fields in reversed(messages):
                if not isinstance(fields, dict):
                    continue
                
                body_json = fields.get("body", "{}")
                participant_field = fields.get("participant", "user")
                
                if isinstance(body_json, str):
                    try:
                        body_data = orjson.loads(body_json)
                    except Exception:
                        continue
                else:
                    body_data = body_json
                
                if not isinstance(body_data, dict):
                    continue
                
                text = body_data.get("bd", {}).get("text", "") if isinstance(body_data.get("bd"), dict) else ""
                
                # 이전 계약서 추출 (최신 1개)
                if previous_contract_draft is None:
                    contract_draft_from_msg = body_data.get("bd", {}).get("contract_draft") if isinstance(body_data.get("bd"), dict) else None
                    if contract_draft_from_msg:
                        previous_contract_draft = contract_draft_from_msg
                
                # 라벨 결정
                if text:
                    if participant_field in ["client", "provider"]:
                        role_korean = "의뢰인(갑)" if participant_field == "client" else "용역자(을)"
                        label = f"{participant_field}({role_korean})"
                    elif participant_field == "assistant":
                        label = "assistant"
                    else:
                        label = participant_field
                    chat_history.append(f"{label}: {text}")
                    
        except Exception as e:
            ctx.log.warning(f"[WS] Failed to load chat history: {e}")
            chat_history = []

        ctx.log.info(f"[WS] Chat history loaded: {len(chat_history)} messages")
        
        # 5단계: ChatSessionManager에서 처리
        session_manager = ChatSessionManager(ctx)
        
        chat_history.reverse()  # 시간 순서로 정렬
        
        llm_response, step_advance_response, question_answered = await session_manager.process_user_input(
            sid=sid,
            user_query=user_query,
            role=role,
            hd=hd,
            manager=manager,
            state_manager=state_manager,
            chat_history=chat_history,
            previous_contract_draft=previous_contract_draft
        )
        
        # 6단계: 응답 저장 및 전송
        if llm_response:
            await store_chat_message(ctx, sid, "assistant",
                {"hd": llm_response["hd"], "bd": llm_response["bd"]})
            await send_json_safe(llm_response)
            ctx.log.info(f"[WS] LLM response sent")
        
        # 단계 진행 응답 전송 (있는 경우)
        if step_advance_response:
            await store_chat_message(ctx, sid, "assistant",
                {"hd": step_advance_response["hd"], "bd": step_advance_response["bd"]})
            await send_json_safe(step_advance_response)
            ctx.log.info(f"[WS] Step advance response sent")
        
        # 7단계: 상태 저장
        await SessionStateCache.save(state_manager, ctx)
        
    except Exception as e:
        ctx.log.error(f"[WS] LLM invocation unexpected error: {e}")
        import traceback
        ctx.log.error(f"[WS] Traceback: {traceback.format_exc()}")
        
        error_user_name = hd.get("user_name") or hd.get("asker") or "사용자"
        error_role = hd.get("role") or "client"
        error_contract_date = hd.get("contract_date")
        
        error_response = {
            "hd": {
                "sid": sid,
                "event": ChatEvent.LLM_ERROR.value,
                "role": "assistant",
                "user_name": error_user_name,
                "role_name": error_role,
                "contract_date": error_contract_date,
            },
            "bd": {
                "text": "처리 중 오류가 발생했습니다. 다시 시도해주세요.",
                "state": codes.ResponseStatus.SERVER_ERROR,
                "detail": str(e)
            }
        }
        await send_json_safe(error_response)