from fastapi import APIRouter, WebSocket
from src.service.messaging.ws_processor import processor
from src.utils.chat_stream_utils import store_chat_message
from src.service.ai.chat_state_manager import SessionStateCache, ChatStateManager, ChatStep, ChatEvent

from src.service.ai.asset.prompts.prompts_cfg import SYSTEM_PROMPTS
import src.service.ai.asset.prompts.doq_prompts_chat_scenario as scenario
from src.service.ai.asset.prompts.doq_contract_template import CONTRACT_TEMPLATE
from src.service.ai.asset.prompts.doq_prompts_rag import QUESTION_DETECTION_PROMPT, RAG_ANSWER_PROMPT, RAG_ANSWER_ALREADY_SENT_PROMPT
from src.service.ai.asset.prompts.doq_prompts_confirmation import _CONTRACT_COMPLETION_PATTERNS
from src.service.ai.rag_manager import RAGManager

import src.common.common_codes as codes
import orjson
import json
import re
from langchain_core.output_parsers import JsonOutputParser

router = APIRouter(prefix="/v1/session", tags=["Session"])

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
    await ctx.ws_handler.connect(websocket, id=sid)

    # 연결 직후 선제 인사 전송 (1회)
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
        greeting_text = scenario.START_MESSAGE_PROMPT
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
        await websocket.send_json(greeting_response)
    except Exception as e:
        ctx.log.warning(f"[WS]        -- Failed to send initial greeting: {e}")

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
            
            # 프롬프트 인젝션 응답에도 user_info 포함
            user_name_val = hd.get("user_name") or hd.get("asker") or "사용자"
            role_val = hd.get("role") or "client"
            contract_date_val = hd.get("contract_date")
            
            response = {
                "hd": {
                    "sid": sid,
                    "event": ChatEvent.LLM_RESPONSE.value,
                    "role": "assistant",
                    "asker": asker,
                    "user_name": user_name_val,
                    "role_name": role_val,
                    "contract_date": contract_date_val,
                },
                "bd": {
                    "text": response_text,
                    "state": codes.ResponseStatus.SUCCESS
                }
            }
            
            await store_chat_message(
                ctx, sid, "assistant", 
                {"hd": response["hd"], "bd": response["bd"], "sid": sid}
            )
            await websocket.send_json(response)
            return
        
        # Redis에서 session_info 로드 (참여자 이름 확인)
        client_name_fixed = "의뢰인"
        provider_name_fixed = "용역자"
        try:
            redis_client = ctx.redis_handler.get_client()
            session_key = f"session:info:{sid}"
            session_info_json = await redis_client.get(session_key)
            if session_info_json:
                session_info = orjson.loads(session_info_json)
                client_name_fixed = session_info.get("client_name") or "의뢰인"
                provider_name_fixed = session_info.get("provider_name") or "용역자"
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to load session info in handler: {e}")
            # 폴백: 쿼리 파라미터에서 읽기 (하지만 handle_llm_invocation에는 websocket 객체가 직접 전달되지 않음)
            # 대신 state_manager의 user_info를 활용하거나 기본값 사용

        # 2. 세션 상태 로드 또는 생성
        state_manager = await SessionStateCache.get(sid, ctx)
        if not state_manager:
            user_info = {
                "user_name": hd.get("user_name") or hd.get("asker"),
                "role": hd.get("role"),
                "contract_date": hd.get("contract_date"),
            }
            state_manager = ChatStateManager(sid, user_info)
            await SessionStateCache.save(state_manager, ctx)

        
            # 역할 한글 표현
            role_korean = "의뢰인(갑)" if user_info.get('role') == 'client' else "용역자(을)"
            ctx.log.info(f"[WS]        -- New session state created for {sid}, user: {user_info.get('user_name')} ({user_info.get('role')})")
        else:
            ctx.log.debug(f"[WS]        -- Loaded session state for {sid}, current_step: {state_manager.current_step.value}")
            # 매 메시지마다 user_info 업데이트 (프론트에서 전송된 최신 정보로)
            if hd.get("user_name"):
                state_manager.user_info["user_name"] = hd.get("user_name")
            if hd.get("role"):
                state_manager.user_info["role"] = hd.get("role")
            if hd.get("contract_date"):
                state_manager.user_info["contract_date"] = hd.get("contract_date")
        
        # [Fix] collected_data에 참여자 이름 정보 동기화
        if client_name_fixed and client_name_fixed != "의뢰인":
            state_manager.collected_data["client_name"] = client_name_fixed
        if provider_name_fixed and provider_name_fixed != "용역자":
            state_manager.collected_data["provider_name"] = provider_name_fixed

        # 3. 사용자 입력 기록
        role = state_manager.user_info.get("role", "client")
        state_manager.add_role_input(role, user_query)
        
        # 3.5. 사용자 입력을 Redis 스트림에 저장 (participant에 역할 포함)
        await store_chat_message(
            ctx, sid, role,  # "client" 또는 "provider"로 저장
            {"hd": {"sid": sid, "event": ChatEvent.CHAT_MESSAGE.value, "role": role}, 
             "bd": {"text": user_query}}
        )
        
        # 4. 대화 이력 가져오기 (Redis에서)
        chat_history = []
        previous_contract_draft = None  # 이전 contract_draft 저장
        stream_key = f"session:chat:{sid}"
        try:
            redis_client = ctx.redis_handler.get_client()
            messages = await redis_client.xrange(stream_key, count=20)  # 최근 20개 메시지
            
            # 메시지를 역순으로 처리하여 가장 최신의 contract_draft 찾기
            for msg_id, fields in reversed(messages):
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
                
                # 이전 contract_draft 추출 (가장 최근 것을 한 번만)
                if previous_contract_draft is None:
                    contract_draft_from_msg = body_data.get("bd", {}).get("contract_draft") if isinstance(body_data.get("bd"), dict) else None
                    if contract_draft_from_msg:
                        previous_contract_draft = contract_draft_from_msg
                
                # 라벨 결정: client/provider/assistant로 표기
                if text:
                    if participant_field in ["client", "provider"]:
                        # 새로운 방식: participant가 직접 역할을 나타냄
                        role_korean = "의뢰인(갑)" if participant_field == "client" else "용역자(을)"
                        label = f"{participant_field}({role_korean})"
                    elif participant_field == "user":
                        # 하위 호환성: 기존 "user" 방식도 지원
                        role_from_msg = body_data.get("hd", {}).get("role", "user") if isinstance(body_data.get("hd"), dict) else "user"
                        role_korean = "의뢰인(갑)" if role_from_msg == "client" else "용역자(을)" if role_from_msg == "provider" else ""
                        label = f"user({role_from_msg}/{role_korean})" if role_korean else f"user({role_from_msg})"
                    elif participant_field == "assistant":
                        label = "assistant"
                    else:
                        label = participant_field
                    chat_history.append(f"{label}: {text}")
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to load chat history: {e}")
            import traceback
            ctx.log.debug(f"[WS]        -- Traceback: {traceback.format_exc()}")
            chat_history = []  # 이력 로드 실패 시 빈 배열로 계속 진행

        # 대화 이력 로그 출력 (디버깅용)
        ctx.log.info(f"[WS]        -- Chat history loaded: {len(chat_history)} messages")
        if chat_history:
            ctx.log.debug(f"[WS]        -- History preview: {chat_history[-3:]}")  # 최근 3개

        # [NEW] 4.5. 질문 감지 및 RAG 답변 (Question Answering)
        # 사용자가 계약 내용 입력이 아닌, 용어 정의나 법률적 질문을 한 경우 먼저 답변을 제공
        question_answered = False
        if user_query.strip():
            try:
                # 프롬프트 파일에서 로드한 템플릿 사용
                detection_prompt = QUESTION_DETECTION_PROMPT.format(
                    user_query=user_query,
                    current_step=state_manager.current_step.value
                )
                
                detection_res = await manager.generate(detection_prompt, temperature=0.1)
                
                # 파싱 로직 강화: 다양한 형식 처리
                det_parsed = None
                det_json_str = detection_res.strip()
                
                # 1차: 마크다운 코드블록에서 추출
                det_json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", detection_res, re.DOTALL)
                if det_json_match:
                    det_json_str = det_json_match.group(1)
                
                # 2차: 순수 JSON 객체 추출 (코드블록 없이 {...} 형태)
                if not det_json_match:
                    json_obj_match = re.search(r"(\{[^{}]*\"is_question\"[^{}]*\})", detection_res, re.DOTALL)
                    if json_obj_match:
                        det_json_str = json_obj_match.group(1)
                
                # 3차: JSON 파싱 시도
                try:
                    det_parsed = orjson.loads(det_json_str)
                except Exception:
                    # 4차: is_question 값만 추출 (불완전한 JSON 대응)
                    is_q_match = re.search(r'"is_question"\s*:\s*(true|false)', detection_res, re.IGNORECASE)
                    if is_q_match:
                        is_question_val = is_q_match.group(1).lower() == "true"
                        search_q_match = re.search(r'"search_query"\s*:\s*"([^"]*)"', detection_res)
                        det_parsed = {
                            "is_question": is_question_val,
                            "search_query": search_q_match.group(1) if search_q_match else ""
                        }
                
                if det_parsed and det_parsed.get("is_question"):
                    search_q = det_parsed.get("search_query") or user_query
                    ctx.log.info(f"[WS]        -- Question detected: {search_q}")
                    
                    # RAG Search
                    rag_manager_qa = RAGManager()
                    rag_results_qa = rag_manager_qa.search(search_q, k=2)
                    
                    # Generate Answer
                    ans_prompt = RAG_ANSWER_PROMPT.format(
                        user_query=user_query,
                        rag_context=rag_results_qa
                    )
                    
                    rag_answer_text = await manager.generate(ans_prompt, temperature=0.7)
                    
                    # Send Answer Message
                    ans_response = {
                        "hd": {
                            "sid": sid,
                            "event": ChatEvent.LLM_RESPONSE.value,
                            "role": "assistant",
                            "asker": asker,
                            "step": state_manager.current_step.value,
                            "user_name": "DoQ",
                            "role_name": "assistant",
                            "type": "question_answer"
                        },
                        "bd": {
                            "text": rag_answer_text,
                            "state": codes.ResponseStatus.SUCCESS
                        }
                    }
                    await store_chat_message(ctx, sid, "assistant", {"hd": ans_response["hd"], "bd": ans_response["bd"], "sid": sid})
                    await websocket.send_json(ans_response)
                    
                    question_answered = True
                    ctx.log.info(f"[WS]        -- Sent RAG answer for question")
                    
            except Exception as e:
                ctx.log.warning(f"[WS]        -- Question detection/answering failed: {e}")

        # 5. 대화 로그 기반 단계 진행 의사 분류 (Gemini 호출)
        confirmation_message_sent = False
        # chat_history를 다시 정렬 (역순으로 추출했으므로)
        chat_history.reverse()
        conversation_context = "\n".join(chat_history[-10:])  # 최근 10개만 사용
        current_step_prompt = state_manager.current_step.prompt
        should_advance = False
        
        # [DEBUG] 프론트 전송용 step advance 메타 정보
        step_advance_meta = {"advance": False, "reason": "", "source": "llm"}
        try:
            decision_text = await manager.generate(
                scenario.STEP_ADVANCE_CLASSIFICATION_PROMPT,
                placeholders={
                    "conversation_context": conversation_context,
                    "current_step": state_manager.current_step.value,
                    "current_step_prompt": current_step_prompt,
                    "user_query": user_query,
                },
                max_output_tokens=200,
                temperature=0.2,
            )

            # 파싱 로직 강화: 다양한 형식 처리
            decision_json_str = decision_text.strip()
            
            # 1차: 마크다운 코드블록에서 추출
            decision_json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", decision_text, re.DOTALL)
            if decision_json_match:
                decision_json_str = decision_json_match.group(1)
            
            # 2차: 순수 JSON 객체 추출 (코드블록 없이 {...} 형태)
            if not decision_json_match:
                json_obj_match = re.search(r"(\{[^{}]*\"advance\"[^{}]*\})", decision_text, re.DOTALL)
                if json_obj_match:
                    decision_json_str = json_obj_match.group(1)

            # 관대하게 파싱: 불리언 문자열/대소문자 섞여도 허용
            parsed = None
            try:
                parsed = orjson.loads(decision_json_str)
            except Exception:
                # 3차: advance 값만 추출 (불완전한 JSON 대응)
                adv_match = re.search(r'"advance"\s*:\s*(true|false)', decision_text, re.IGNORECASE)
                if adv_match:
                    advance_val = adv_match.group(1).lower() == "true"
                    reason_match = re.search(r'"reason"\s*:\s*"([^"]*)"', decision_text)
                    parsed = {
                        "advance": advance_val,
                        "reason": reason_match.group(1) if reason_match else "regex_extracted"
                    }
                else:
                    # 4차: 단순 true/false 문자열만 온 경우 처리
                    text_lower = decision_json_str.strip().lower()
                    if text_lower in ("true", "false"):
                        parsed = {"advance": text_lower == "true", "reason": "boolean_only"}
            if parsed:
                should_advance = bool(parsed.get("advance"))
                step_advance_meta = {
                    "advance": should_advance,
                    "reason": parsed.get("reason", ""),
                    "source": "llm"
                }
                ctx.log.info(f"[WS]        -- Step advance decision: {should_advance}, reason={parsed.get('reason')}")
            else:
                raise ValueError("Cannot parse advance decision")
            
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Step advance classification failed, fallback to keyword: {e}")
            # 예외 발생 시에만 handle_user_confirm 호출 (상태 변경 포함)
            should_advance = state_manager.handle_user_confirm(user_query)
            step_advance_meta = {
                "advance": should_advance,
                "reason": f"LLM 파싱 실패, 키워드 폴백: {str(e)[:50]}",
                "source": "fallback"
            }

        # [Relaxation] LLM이 False라고 했더라도, 사용자가 명확한 진행 키워드를 사용했다면 진행 (상태 변경 없이 플래그만 True)
        # 실제 상태 변경은 아래 if should_advance: 블록에서 move_to_next_step() 호출로 처리됨
        if not should_advance and state_manager.check_confirm_pattern(user_query):
            should_advance = True
            step_advance_meta = {
                "advance": True,
                "reason": f"키워드 패턴 매칭: {user_query[:30]}",
                "source": "keyword_override"
            }
            ctx.log.info(f"[WS]        -- Step advance override by keyword pattern: {user_query}")

        # 추가 폴백: 소개 단계에서 사용자가 의미 있는 입력을 하면 진행
        if not should_advance and state_manager.current_step == ChatStep.INTRODUCTION and user_query.strip():
            should_advance = True
            step_advance_meta = {
                "advance": True,
                "reason": "소개 단계 자동 진행 (사용자 입력 감지)",
                "source": "auto_intro"
            }
            ctx.log.info("[WS]        -- Auto-advance from introduction due to user input")

        # [NEW] finalization 단계에서 계약서 완료 키워드 감지 시 completed로 강제 전환
        is_contract_completion_request = False
        if state_manager.current_step == ChatStep.FINALIZATION:
            for pattern in _CONTRACT_COMPLETION_PATTERNS:
                if re.search(pattern, user_query, flags=re.IGNORECASE):
                    is_contract_completion_request = True
                    should_advance = True
                    step_advance_meta = {
                        "advance": True,
                        "reason": f"계약서 완료 키워드 감지: {user_query[:30]}",
                        "source": "contract_completion"
                    }
                    ctx.log.info(f"[WS]        -- Contract completion keyword detected: {user_query}")
                    break

        # [CRITICAL] completed 단계에서는 더 이상 단계 진행하지 않음 (무한 루프 방지)
        if state_manager.current_step == ChatStep.COMPLETED:
            should_advance = False
            step_advance_meta = {
                "advance": False,
                "reason": "이미 completed 단계 (최종 단계)",
                "source": "completed_guard"
            }
            ctx.log.info("[WS]        -- Already at COMPLETED step, no further advancement")

        if should_advance:
            # INTRODUCTION 단계를 포함한 모든 단계에서 진행 가능
            
            # 현재 단계 데이터 저장 (단계 전환 전에!)
            # introduction에서 work_scope로 갈 때는 current_step이 아직 introduction
            # 따라서 현재 단계의 사용자 입력을 "이전 단계 → 다음 단계의 필드"로 매핑해서 저장
            current_step_to_field_mapping = {
                ChatStep.INTRODUCTION: None,  # introduction의 입력은 별도 처리 필요 없음
                ChatStep.WORK_SCOPE: "work_scope",
                ChatStep.WORK_PERIOD: "work_period",
                ChatStep.BUDGET: "budget",
                ChatStep.REVISIONS: "revision_count",
                ChatStep.COPYRIGHT: "copyright_owner",
                ChatStep.CONFIDENTIALITY: "confidentiality_terms",
            }
            
            # introduction → work_scope 특수 케이스 처리
            if state_manager.current_step == ChatStep.INTRODUCTION:
                if user_query.strip() and state_manager.collected_data.get("work_scope") is None:
                    state_manager.update_data("work_scope", user_query.strip())
                    ctx.log.info(f"[WS]        -- Auto-saved user input from introduction to work_scope: {user_query[:50]}...")
            else:
                # 다른 단계에서의 입력 저장 (현재 단계 필드에)
                current_field = current_step_to_field_mapping.get(state_manager.current_step)
                
                # [NEW] LLM을 이용한 단계별 최종 합의 내용 요약 및 저장
                if current_field:
                    try:
                        summary_prompt = scenario.STEP_SUMMARY_PROMPT
                        summary_text = await manager.generate(
                            summary_prompt,
                            placeholders={
                                "conversation_context": conversation_context,
                                "current_step": state_manager.current_step.value,
                                "target_field": current_field
                            },
                            max_output_tokens=500,
                            temperature=0.1
                        )
                        
                        # JSON 파싱
                        summary_json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", summary_text, re.DOTALL)
                        if summary_json_match:
                            summary_json_str = summary_json_match.group(1)
                        else:
                            summary_json_str = summary_text
                            
                        try:
                            summary_parsed = orjson.loads(summary_json_str)
                        except:
                            summary_parsed = json.loads(summary_json_str, strict=False)
                            
                        extracted_value = summary_parsed.get("extracted_value")
                        if extracted_value:
                            state_manager.update_data(current_field, extracted_value)
                            ctx.log.info(f"[WS]        -- Summarized and saved {current_field}: {extracted_value}")
                        else:
                            # 요약 실패 시 기존 방식(마지막 입력) 폴백
                            if user_query.strip() and state_manager.collected_data.get(current_field) is None:
                                state_manager.update_data(current_field, user_query.strip())
                                ctx.log.info(f"[WS]        -- Summary failed, fallback to user input for {current_field}")

                    except Exception as e:
                        ctx.log.warning(f"[WS]        -- Step summary failed: {e}")
                        # 예외 발생 시 기존 방식 폴백
                        if user_query.strip() and state_manager.collected_data.get(current_field) is None:
                            state_manager.update_data(current_field, user_query.strip())
            
            next_step = state_manager.move_to_next_step()

            # 혹시라도 current_step이 string이면 Enum으로 변환
            if not isinstance(state_manager.current_step, ChatStep):
                try:
                    state_manager.current_step = ChatStep(state_manager.current_step)
                except Exception:
                    state_manager.current_step = ChatStep.INTRODUCTION

            # step_history도 Enum만 유지
            state_manager.step_history = [s if isinstance(s, ChatStep) else ChatStep(s) for s in state_manager.step_history]
            await SessionStateCache.save(state_manager, ctx)
            ctx.log.info(f"[WS]        -- User confirmed, moved to next step: {next_step.value}")

            # 단계 전환 후 프롬프트 갱신
            current_step_prompt = state_manager.current_step.prompt

            # 진행률도 Enum 기준으로 계산 (0% ~ 100%)
            total_steps = len(ChatStep)
            current_idx = list(ChatStep).index(state_manager.current_step)
            if total_steps > 1:
                progress_percentage = round((current_idx / (total_steps - 1)) * 100, 1)
            else:
                progress_percentage = 100.0

            # 단계별 한국어 명칭 매핑
            step_names_kr = {
                ChatStep.INTRODUCTION: "프로젝트 시작",
                ChatStep.WORK_SCOPE: "작업 범위 확인",
                ChatStep.WORK_PERIOD: "작업 기간 설정",
                ChatStep.BUDGET: "대금 및 지급 조건",
                ChatStep.REVISIONS: "수정 조건",
                ChatStep.COPYRIGHT: "저작권 귀속",
                ChatStep.CONFIDENTIALITY: "비밀 유지 및 특약",
                ChatStep.CONFLICT_RESOLUTION: "의견 조율",
                ChatStep.FINALIZATION: "최종 확인",
                ChatStep.COMPLETED: "계약서 작성 완료"
            }

            # 이전 단계 이름 가져오기
            prev_step = state_manager.step_history[-2] if len(state_manager.step_history) >= 2 else None
            prev_step_name = step_names_kr.get(prev_step, "이전") if prev_step else "소개"
            
            # 현재(다음) 단계 이름 가져오기
            next_step_name = step_names_kr.get(next_step, next_step.value)

            # 확정 메시지 전송 (다음 단계 안내)
            template_key = "complete" if next_step == ChatStep.COMPLETED else "next"
            template = scenario.MESSAGE_TEMPLATES[template_key]
            response_text = template.format(step=prev_step_name, next_step=next_step_name)

            # [NEW] COMPLETED 단계 진입 시 계약서 전문 생성
            final_contract_draft = None
            if next_step == ChatStep.COMPLETED:
                # 진행률 100%로 설정
                progress_percentage = 100.0
                
                # 계약서 전문 생성 (이전 contract_draft가 있으면 사용, 없으면 LLM으로 생성)
                if previous_contract_draft and len(previous_contract_draft) > 100:
                    final_contract_draft = previous_contract_draft
                    ctx.log.info(f"[WS]        -- Using existing contract draft for completion")
                else:
                    # LLM을 통해 최종 계약서 생성
                    try:
                        final_contract_prompt = scenario.FINAL_CONTRACT_GENERATION_PROMPT.format(
                            collected_data_json=collected_data_json,
                            contract_template=CONTRACT_TEMPLATE
                        )
                        final_contract_draft = await manager.generate(
                            final_contract_prompt,
                            max_output_tokens=4000,
                            temperature=0.3
                        )
                        ctx.log.info(f"[WS]        -- Generated final contract draft via LLM")
                    except Exception as e:
                        ctx.log.warning(f"[WS]        -- Failed to generate final contract: {e}")
                        final_contract_draft = previous_contract_draft or "계약서 생성에 실패했습니다. 다시 시도해주세요."
                
                # 완료 메시지 커스터마이징
                response_text = scenario.COMPLETION_MESSAGE

            confirmation_response = {
                "hd": {
                    "sid": sid,
                    "event": ChatEvent.LLM_RESPONSE.value,
                    "role": "assistant",
                    "asker": asker,
                    "step": next_step.value,
                    "user_name": state_manager.user_info.get("user_name") or asker,
                    "role_name": state_manager.user_info.get("role"),
                    "contract_date": state_manager.user_info.get("contract_date"),
                },
                "bd": {
                    "text": response_text,
                    "contract_draft": final_contract_draft,  # COMPLETED일 때 계약서 전문 포함
                    "current_step": next_step.value,
                    "progress_percentage": 100.0 if next_step == ChatStep.COMPLETED else progress_percentage,
                    "is_completed": next_step == ChatStep.COMPLETED,  # 프론트엔드에서 세션 종료 처리용
                    "state": codes.ResponseStatus.SUCCESS
                }
            }
            await store_chat_message(
                ctx, sid, "assistant",
                {"hd": confirmation_response["hd"], "bd": confirmation_response["bd"], "sid": sid}
            )
            await websocket.send_json(confirmation_response)
            confirmation_message_sent = True
            
            # [NEW] COMPLETED 단계면 여기서 처리 종료 (추가 LLM 호출 불필요)
            if next_step == ChatStep.COMPLETED:
                ctx.log.info(f"[WS]        -- Contract completed for session {sid}, no further LLM calls needed")
                await SessionStateCache.save(state_manager, ctx)
                return

        # 6. 현재 step에 맞는 프롬프트 가져오기
        # (이미 분류 시 계산됨)
        
        # 6.5. 응답 분류 및 데이터 추출 (옵션: 사용자 응답 분석)
        # introduction 제외 모든 단계에서 응답 분석 (단, 단계 진행 후 아님)
        classification_result = None
        if not confirmation_message_sent and state_manager.current_step != ChatStep.INTRODUCTION:
            try:
                classification_placeholders = {
                    "current_step": state_manager.current_step.value,
                    "user_response": user_query,
                    "user_name": state_manager.user_info.get("user_name") or asker,
                    "role": role
                }
                
                classification_result = await manager.classify_response(
                    user_response=user_query,
                    current_step=state_manager.current_step.value,
                    placeholders=classification_placeholders
                )
                ctx.log.debug(f"[WS]        -- Response classification: {classification_result}")
                
                # 분류 결과에서 추출된 데이터 저장
                if classification_result.get("extracted_fields"):
                    for key, value in classification_result["extracted_fields"].items():
                        state_manager.update_data(key, value)
                
                ctx.log.info(f"[WS]        -- Extracted fields saved: {classification_result.get('extracted_fields', {})}")
            except Exception as e:
                ctx.log.warning(f"[WS]        -- Response classification failed: {e}")
                classification_result = None
        
        # 6.6 분류 실패 시 현재 단계에 맞게 간단히 데이터 저장
        # (예: work_scope 단계면 사용자 입력 전체를 work_scope으로 저장)
        if not confirmation_message_sent and state_manager.current_step != ChatStep.INTRODUCTION:
            if not classification_result or not classification_result.get("extracted_fields"):
                step_key_mapping = {
                    ChatStep.WORK_SCOPE: "work_scope",
                    ChatStep.WORK_PERIOD: "work_period",
                    ChatStep.BUDGET: "budget",
                    ChatStep.REVISIONS: "revision_count",
                    ChatStep.COPYRIGHT: "copyright_owner",
                    ChatStep.CONFIDENTIALITY: "confidentiality_terms",
                }
                step_key = step_key_mapping.get(state_manager.current_step)
                if step_key and user_query.strip():
                    state_manager.update_data(step_key, user_query.strip())
                    ctx.log.info(f"[WS]        -- Auto-saved user input to collected_data[{step_key}]: {user_query[:50]}...")

        
        # 7. LLM에 전달할 프롬프트 구성
        
        # 역할 한글 변환
        role_korean = "의뢰인(갑)" if state_manager.user_info.get("role") == "client" else "용역자(을)"
        
        # 공통 placeholders 구성
        collected_data_json = ""
        role_inputs_json = ""
        try:
            collected_data_json = orjson.dumps(state_manager.collected_data).decode()
            role_inputs_json = orjson.dumps(state_manager.role_inputs).decode()
        except Exception:
            collected_data_json = str(state_manager.collected_data)
            role_inputs_json = str(state_manager.role_inputs)
        
        ctx.log.info(f"[WS]        -- Collected data: {collected_data_json[:150]}")  # 디버깅용

        # 이전 단계 정보 (STEP_TRANSITION_PROMPT에서 사용)
        previous_step_value = state_manager.step_history[-2].value if len(state_manager.step_history) >= 2 else ChatStep.INTRODUCTION.value
        previous_step_prompt = state_manager.step_history[-2].prompt if len(state_manager.step_history) >= 2 else scenario.STEP_PROMPTS.get(ChatStep.INTRODUCTION.value, "")
        
        # collected_data에서 null이 아닌 항목만 추출 (이미 수집된 정보)
        collected_fields_summary = []
        for key, value in state_manager.collected_data.items():
            if value is not None and value != "":
                collected_fields_summary.append(f"- {key}: {value}")
        collected_fields_str = "\n".join(collected_fields_summary) if collected_fields_summary else "아직 수집된 정보가 없습니다."

        # 현재 단계의 주요 데이터가 이미 수집되었는지 확인하여 지침 생성
        step_key_mapping = {
            ChatStep.WORK_SCOPE: "work_scope",
            ChatStep.WORK_PERIOD: "work_period",
            ChatStep.BUDGET: "budget",
            ChatStep.REVISIONS: "revision_count",
            ChatStep.COPYRIGHT: "copyright_owner",
            ChatStep.CONFIDENTIALITY: "confidentiality_terms",
        }
        current_step_key = step_key_mapping.get(state_manager.current_step)
        step_specific_instruction = ""
        if current_step_key:
            val = state_manager.collected_data.get(current_step_key)
            if val:
                step_specific_instruction = scenario.STEP_SPECIFIC_INSTRUCTION_TEMPLATE.format(
                    current_step_key=current_step_key,
                    val=val
                )
        
        # Redis에서 session_info 로드 (참여자 이름 확인) - 위에서 이미 로드함
        
        # RAG 검색 (현재 단계 + 사용자 쿼리 기반)
        rag_context = ""
        try:
            rag_manager = RAGManager()
            # 검색 쿼리 구성: 현재 단계 키워드 + 사용자 입력
            search_query = f"{state_manager.current_step.value} {user_query}"
            rag_context = rag_manager.search(search_query, k=2)
            if rag_context:
                ctx.log.info(f"[WS]        -- RAG context retrieved: {len(rag_context)} chars")
        except Exception as e:
            ctx.log.warning(f"[WS]        -- RAG search failed: {e}")

        # 카테고리(계약명) 정규화: 작업 범위를 그대로 쓰지 않고 문장형 표현을 정리
        def _normalize_category(text: str) -> str:
            if not text:
                return "용역"
            candidate = re.split(r"(을 의뢰|를 의뢰|을 의뢰하고|를 의뢰하고|을 의뢰할|를 의뢰할)", text)[0]
            candidate = re.sub(r"[^0-9A-Za-z가-힣·\s]", " ", candidate)
            candidate = re.sub(r"\s+", " ", candidate).strip()
            return candidate if candidate else "용역"

        # 핵심 식별자/카테고리 기본값 보정 (이름이 없으면 템플릿이 '미기재'로 채워지는 문제 방지)
        resolved_client_name = state_manager.collected_data.get("client_name") or client_name_fixed or "미기재"
        resolved_provider_name = state_manager.collected_data.get("provider_name") or provider_name_fixed or "미기재"
        resolved_client_company = state_manager.collected_data.get("client_company") or resolved_client_name
        resolved_provider_company = state_manager.collected_data.get("provider_company") or resolved_provider_name
        resolved_category = state_manager.collected_data.get("category") or _normalize_category(
            state_manager.collected_data.get("work_scope") or ""
        )

        # 수집 데이터에 기본값을 반영 (없을 때만 세팅)
        if not state_manager.collected_data.get("client_name"):
            state_manager.update_data("client_name", resolved_client_name)
        if not state_manager.collected_data.get("provider_name"):
            state_manager.update_data("provider_name", resolved_provider_name)
        if not state_manager.collected_data.get("client_company"):
            state_manager.update_data("client_company", resolved_client_company)
        if not state_manager.collected_data.get("provider_company"):
            state_manager.update_data("provider_company", resolved_provider_company)
        if not state_manager.collected_data.get("category"):
            state_manager.update_data("category", resolved_category)

        # [수정] 항상 전체 템플릿을 제공하여 계약서 전문 생성을 유도
        template_to_use = CONTRACT_TEMPLATE
        
        # [Fix] 템플릿 내의 기본 정보(이름, 회사, 카테고리 등)를 미리 치환하여 LLM에 제공
        template_placeholders = {
            "client_name": resolved_client_name,
            "provider_name": resolved_provider_name,
            "client_company": resolved_client_company,
            "provider_company": resolved_provider_company,
            "category": resolved_category,
            "work_period": state_manager.collected_data.get("work_period") or "미기재",
            "start_date": state_manager.collected_data.get("start_date") or "미기재",
            "end_date": state_manager.collected_data.get("end_date") or "미기재",
            "budget": state_manager.collected_data.get("budget") or "미기재",
        }
        for k, v in template_placeholders.items():
            template_to_use = template_to_use.replace(f"{{{{{k}}}}}", str(v))

        # if previous_contract_draft and len(previous_contract_draft) > 50:
        #     template_to_use = "아래 '계약서 초안'만 기준으로 수정 및 보완하세요. 전체 템플릿은 생략됨."

        common_placeholders = {
            "client_name": resolved_client_name,
            "provider_name": resolved_provider_name,
            "user_name": state_manager.user_info.get("user_name") or asker or "사용자",
            "role": state_manager.user_info.get("role") or hd.get("role") or "client",
            "role_korean": role_korean,
            "contract_date": state_manager.user_info.get("contract_date") or hd.get("contract_date") or "",
            "current_step": state_manager.current_step.value,
            "previous_step": previous_step_value,
            "step_guide": current_step_prompt,
            "previous_step_guide": previous_step_prompt,
            "conversation_context": conversation_context,
            "collected_data_json": collected_data_json,
            "collected_fields_summary": collected_fields_str,  # 새로 추가: 가독성 좋은 요약
            "step_specific_instruction": step_specific_instruction, # 동적 지침 추가
            "role_inputs_json": role_inputs_json,
            "contract_template": template_to_use,
            "previous_contract_draft": previous_contract_draft or "없음",
            "rag_context": rag_context,
        }
        
        # 분류 결과가 있으면 clarification이 필요한지 체크
        if classification_result and classification_result.get("next_action") == "ask_clarification":
            # clarification이 필요한 경우에도 LLM이 전체 응답 생성 (USER_MESSAGE + CONTRACT_DRAFT 포함)
            ctx.log.info(f"[WS]        -- Clarification needed for step: {state_manager.current_step.value}")
            full_prompt = scenario.NORMAL_RESPONSE_PROMPT_TEMPLATE.replace("{system_prompt}", "\n".join(SYSTEM_PROMPTS))
            
            # clarification 요청 내용을 프롬프트에 추가
            response_placeholders = {
                **common_placeholders,
                "user_query": classification_result.get("clarification_needed", user_query),
            }
            
            response_text = await manager.generate(
                full_prompt,
                placeholders=response_placeholders,
                max_output_tokens=4000,
                temperature=0.7
            )
        elif confirmation_message_sent:
            # 확정 메시지를 보낸 후, 다음 step의 시작 프롬프트 생성
            full_prompt = scenario.STEP_TRANSITION_PROMPT_TEMPLATE.replace("{system_prompt}", "\n".join(SYSTEM_PROMPTS))
            
            response_text = await manager.generate(
                full_prompt,
                placeholders=common_placeholders,
                max_output_tokens=4000,
                temperature=0.7
            )
        else:
            # 정상적인 LLM 응답 생성
            full_prompt = scenario.NORMAL_RESPONSE_PROMPT_TEMPLATE.replace("{system_prompt}", "\n".join(SYSTEM_PROMPTS))
            
            # [NEW] 질문 답변 후 복귀 지침 추가
            if question_answered:
                full_prompt += "\n" + RAG_ANSWER_ALREADY_SENT_PROMPT

            # 정상 응답용 추가 placeholders
            response_placeholders = {
                **common_placeholders,
                "user_query": user_query,
            }
            
            # 8. LLM 호출
            response_text = await manager.generate(
                full_prompt,
                placeholders=response_placeholders,
                max_output_tokens=4000,
                temperature=0.7
            )
        
        # 응답이 비어있는 경우 체크
        if not response_text or response_text.strip() == "":
            ctx.log.warning(f"[WS]        -- Empty response from LLM for session {sid}")
            response_text = "죄송합니다. 응답을 생성할 수 없습니다. 다시 시도해주세요."
        
        # 에러 메시지인지 확인 (API 에러 응답)
        is_error_response = any(keyword in response_text for keyword in [
            "API 할당량 초과", "요청 형식에 오류", "API 인증에 실패", "오류가 발생"
        ])
        
        if is_error_response:
            ctx.log.warning(f"[WS]        -- LLM returned error message for session {sid}: {response_text[:100]}")
        
        # 9. 응답 저장 및 전송 (USER_MESSAGE / CONTRACT_DRAFT 분리)
        user_message = response_text or ""
        contract_draft = None

        # 1차: LangChain JsonOutputParser 시도 (가장 강력함)
        try:
            parser = JsonOutputParser()
            # LangChain 파서는 마크다운 제거 및 부분 JSON 파싱 등을 지원
            parsed = parser.parse(response_text)
            if isinstance(parsed, dict):
                if "USER_MESSAGE" in parsed:
                    user_message = str(parsed.get("USER_MESSAGE") or "").strip()
                if "CONTRACT_DRAFT" in parsed:
                    contract_draft = str(parsed.get("CONTRACT_DRAFT") or "").strip()
        except Exception as e_lc:
            # LangChain 파싱 실패 시, 기존 수동 로직으로 Fallback (strict=False 등 지원)
            ctx.log.debug(f"[WS]        -- LangChain parser failed, trying manual fallback: {e_lc}")
            
            try:
                txt = (response_text or "").strip()
                # 마크다운 코드블록 제거 (내용 전체 캡처)
                json_match = re.search(r"```(?:json)?\s*(.*?)```", txt, re.DOTALL)
                if json_match:
                    txt = json_match.group(1).strip()
                
                # 이제 JSON 파싱 시도
                if txt.startswith("{"):
                    try:
                        parsed = orjson.loads(txt)
                    except Exception:
                        # orjson 실패 시 표준 json 라이브러리로 재시도 (strict=False 허용)
                        parsed = json.loads(txt, strict=False)

                    if isinstance(parsed, dict):
                        if "USER_MESSAGE" in parsed:
                            user_message = str(parsed.get("USER_MESSAGE") or "").strip()
                        if "CONTRACT_DRAFT" in parsed:
                            contract_draft = str(parsed.get("CONTRACT_DRAFT") or "").strip()
            except Exception as e:
                ctx.log.warning(f"[WS]        -- Failed to parse JSON response: {e}. Text: {txt[:200]}...")

        # 2차: 프롬프트에서 안내한 섹션 형식 USER_MESSAGE: ... CONTRACT_DRAFT: ...
        if contract_draft is None:
            try:
                user_match = re.search(r"USER_MESSAGE:\s*(.*?)(?:\nCONTRACT_DRAFT:|$)", response_text, re.DOTALL)
                contract_match = re.search(r"CONTRACT_DRAFT:\s*(.*)$", response_text, re.DOTALL)
                if user_match:
                    user_message = user_match.group(1).strip()
                if contract_match:
                    contract_draft = contract_match.group(1).strip()
            except Exception as e:
                ctx.log.warning(f"[WS]        -- Failed to split response sections: {e}")

        # [수정] 계약서 초안이 생성되지 않았거나 비어있다면, 이전 버전을 유지하여 항상 보이도록 함
        if not contract_draft and previous_contract_draft:
            contract_draft = previous_contract_draft

        response = {
            "hd": {
                "sid": sid,
                "event": ChatEvent.LLM_RESPONSE.value,
                "role": "assistant",
                "asker": asker,
                "step": state_manager.current_step.value,
                "user_name": state_manager.user_info.get("user_name") or asker,
                "role_name": state_manager.user_info.get("role"),
                "contract_date": state_manager.user_info.get("contract_date"),
            },
            "bd": {
                "text": user_message,
                "contract_draft": contract_draft,
                "current_step": state_manager.current_step.value,
                "progress_percentage": round((list(ChatStep).index(state_manager.current_step) / len(ChatStep)) * 100, 1),
                "state": codes.ResponseStatus.SUCCESS if not is_error_response else codes.ResponseStatus.SERVER_ERROR,
                "meta": {
                    "step_advance": step_advance_meta,
                    "question_answered": question_answered
                }
            }
        }
        
        await store_chat_message(
            ctx, sid, "assistant",
            {"hd": response["hd"], "bd": response["bd"], "sid": sid}
        )
        
        ctx.log.info(f"[WS]        -- LLM response sent (step: {state_manager.current_step.value}, status: {'ERROR' if is_error_response else 'OK'})")
        await websocket.send_json(response)
        
        # 10. 상태 저장
        await SessionStateCache.save(state_manager, ctx)
        
    except Exception as e:
        ctx.log.error(f"[WS]        -- LLM invocation unexpected error: {e}")
        error_user_name = hd.get("user_name") or hd.get("asker") or "사용자"
        error_role = hd.get("role") or "client"
        error_contract_date = hd.get("contract_date")
        await websocket.send_json({
            "hd": {
                "sid": sid, 
                "event": ChatEvent.LLM_ERROR.value, 
                "role": "assistant",
                "user_name": error_user_name,
                "role_name": error_role,
                "contract_date": error_contract_date,
            },
            "bd": {"state": codes.ResponseStatus.SERVER_ERROR, "detail": str(e)}
        })