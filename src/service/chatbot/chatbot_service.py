from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import orjson
from fastapi import WebSocket

import src.core.common_codes as codes
from src.core.responses import ResponseStatus as ApiResponseStatus
from src.core.responses import build_response_body, build_success_response
from src.service.ai.asset.prompts import prompts_cfg as prompt
from src.service.ai.chat_response_builder import ChatResponseBuilder
from src.service.ai.chat_session_manager import ChatSessionManager
from src.service.ai.chat_state_manager import ChatEvent, ChatStateManager, ChatStep, SessionStateCache
from src.service.chatbot.chatbot_schema import ChatbotPreviewRequest
from src.service.messaging.ws_processor import processor
from src.utils.chat_stream_utils import store_chat_message


class ChatbotService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
        self.response_builder = ChatResponseBuilder(ctx)

    def build_api_success(self, data: Any) -> Dict[str, Any]:
        return build_success_response(data)

    def build_api_response(self, http_code: int, data: Any = None) -> Dict[str, Any]:
        return build_response_body(ApiResponseStatus.from_http_code(http_code), data)

    async def handle_websocket_connection(self, websocket: WebSocket) -> None:
        sid = websocket.query_params.get("sid")
        self.log.info(f"[WS] Connection request: sid={sid}, query_params={websocket.query_params}")

        if not sid:
            await websocket.close(code=4001)
            return

        is_first_connection = len(self.ctx.ws_handler.session_map.get(sid, [])) == 0
        await self.ctx.ws_handler.connect(websocket, id=sid)

        if is_first_connection:
            try:
                greeting_response = await self._build_initial_greeting(websocket, sid)
                if greeting_response:
                    await store_chat_message(
                        self.ctx,
                        sid,
                        "assistant",
                        {"hd": greeting_response["hd"], "bd": greeting_response["bd"], "sid": sid},
                    )
                    await self.ctx.ws_handler.broadcast_to_session(sid, greeting_response)
            except Exception as e:
                self.log.warning(f"[WS]        -- Failed to send initial greeting: {e}")
        else:
            await self._send_chat_history(websocket, sid)

        await self.ctx.ws_handler.receive_and_respond(websocket, processor=processor)

    async def handle_llm_invocation(self, websocket: WebSocket, msg: dict):
        sid = msg.get("sid")
        hd = msg.get("hd", {})
        bd = msg.get("bd", {})
        asker = hd.get("asker") or hd.get("role")
        user_query = bd.get("text") or ""
        role = hd.get("role", "user")

        async def send_json_safe(payload):
            try:
                await self.ctx.ws_handler.broadcast_to_session(sid, payload)
            except Exception as send_err:
                self.log.warning(f"[WS] Broadcast failed: {send_err}")

        try:
            self.log.info(f"[WS] LLM invocation (asker={asker}) in session {sid}")

            manager = self.ctx.llm_manager
            if manager._is_prompt_injection(user_query):
                self.log.warning(f"[WS] Prompt injection detected: {user_query[:50]}")
                injection_response = {
                    "hd": {
                        "sid": sid,
                        "event": ChatEvent.LLM_RESPONSE.value,
                        "role": "assistant",
                        "asker": asker,
                    },
                    "bd": {
                        "text": "아직 없는 기능입니다",
                        "state": codes.ResponseStatus.SUCCESS,
                    },
                }
                await store_chat_message(self.ctx, sid, "assistant", {"hd": injection_response["hd"], "bd": injection_response["bd"]})
                await send_json_safe(injection_response)
                return None

            state_manager = await SessionStateCache.get(sid, self.ctx)
            if not state_manager:
                user_info = {
                    "userId": hd.get("userId"),
                    "client_name": hd.get("client_name"),
                    "provider_name": hd.get("provider_name"),
                }
                state_manager = ChatStateManager(sid, user_info)
                await SessionStateCache.save(state_manager, self.ctx)
                self.log.info(f"[WS] New session state created for {sid}")

            state_manager.add_role_input(role, user_query)

            user_message_data = {
                "hd": {"sid": sid, "event": ChatEvent.CHAT_MESSAGE.value, "role": role},
                "bd": {"text": user_query},
            }
            await store_chat_message(self.ctx, sid, role, user_message_data)

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
                    "state": codes.ResponseStatus.SUCCESS,
                },
            }
            await self.ctx.ws_handler.broadcast_to_session(sid, user_broadcast, exclude_sender=websocket)

            chat_history, previous_contract_draft = await self._load_chat_history(sid)
            session_manager = ChatSessionManager(self.ctx)

            llm_response, step_advance_response, question_answered = await session_manager.process_user_input(
                sid=sid,
                user_query=user_query,
                role=role,
                hd=hd,
                manager=manager,
                state_manager=state_manager,
                chat_history=chat_history,
                previous_contract_draft=previous_contract_draft,
            )

            if llm_response:
                await store_chat_message(self.ctx, sid, "assistant", {"hd": llm_response["hd"], "bd": llm_response["bd"]})
                await send_json_safe(llm_response)
                self.log.info("[WS] LLM response sent")

            if step_advance_response:
                await store_chat_message(self.ctx, sid, "assistant", {"hd": step_advance_response["hd"], "bd": step_advance_response["bd"]})
                await send_json_safe(step_advance_response)
                self.log.info("[WS] Step advance response sent")

            await SessionStateCache.save(state_manager, self.ctx)
            return None

        except Exception as e:
            self.log.error(f"[WS] LLM invocation unexpected error: {e}")
            import traceback

            self.log.error(f"[WS] Traceback: {traceback.format_exc()}")

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
                    "detail": str(e),
                },
            }
            await send_json_safe(error_response)
            return None

    async def build_preview_response(self, request: ChatbotPreviewRequest) -> Dict[str, Any]:
        sid = request.sid
        hd = request.hd or {}
        user_query = request.user_query
        role = request.role

        manager = self.ctx.llm_manager
        state_manager = await SessionStateCache.get(sid, self.ctx)
        if not state_manager:
            state_manager = ChatStateManager(
                sid,
                user_info={
                    "userId": hd.get("userId"),
                    "client_name": request.client_name,
                    "provider_name": request.provider_name,
                },
            )

        chat_history, previous_contract_draft = await self._load_chat_history(sid)
        session_manager = ChatSessionManager(self.ctx)

        llm_response, step_advance_response, question_answered = await session_manager.process_user_input(
            sid=sid,
            user_query=user_query,
            role=role,
            hd={
                **hd,
                "user_name": request.user_name or hd.get("user_name"),
                "client_name": request.client_name,
                "provider_name": request.provider_name,
                "contract_date": request.contract_date,
            },
            manager=manager,
            state_manager=state_manager,
            chat_history=chat_history,
            previous_contract_draft=previous_contract_draft,
        )

        response_payload = {
            "llm_response": llm_response,
            "step_advance_response": step_advance_response,
            "question_answered": question_answered,
            "state": state_manager.to_dict(),
        }
        return self.build_api_success(response_payload)

    async def _build_initial_greeting(self, websocket: WebSocket, sid: str) -> Optional[Dict[str, Any]]:
        session_key = f"session:info:{sid}"
        client_name = "의뢰인"
        provider_name = "용역자"
        contract_date = None

        try:
            redis_client = self.ctx.redis_handler.get_client()
            session_info_json = await redis_client.get(session_key)
            if session_info_json:
                session_info = orjson.loads(session_info_json)
                client_name = session_info.get("client_name") or "의뢰인"
                provider_name = session_info.get("provider_name") or "용역자"
                contract_date = session_info.get("contract_date")
            else:
                client_name = websocket.query_params.get("client_name") or "의뢰인"
                provider_name = websocket.query_params.get("provider_name") or "용역자"
                contract_date = websocket.query_params.get("contract_date")

                new_info = {
                    "client_name": client_name,
                    "provider_name": provider_name,
                    "contract_date": contract_date,
                }
                await redis_client.set(session_key, orjson.dumps(new_info))
        except Exception as e:
            self.log.warning(f"[WS]        -- Failed to load session info from Redis: {e}")
            client_name = websocket.query_params.get("client_name") or "의뢰인"
            provider_name = websocket.query_params.get("provider_name") or "용역자"
            contract_date = websocket.query_params.get("contract_date")

        greeting_text = prompt.START_MESSAGE_PROMPT
        greeting_text = greeting_text.replace("{{client_name}}", client_name)
        greeting_text = greeting_text.replace("{{service_provider_name}}", provider_name)

        return {
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

    async def _send_chat_history(self, websocket: WebSocket, sid: str) -> None:
        try:
            redis_client = self.ctx.redis_handler.get_client()
            stream_key = f"session:chat:{sid}"
            messages = await redis_client.xrange(stream_key, count=50)

            self.log.info(f"[WS]        -- Loading chat history for late-joined user: {len(messages)} messages")

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

                    history_msg = {
                        "hd": body_data.get("hd", {
                            "sid": sid,
                            "event": ChatEvent.CHAT_MESSAGE.value,
                            "role": participant,
                        }),
                        "bd": body_data.get("bd", {"text": "", "state": codes.ResponseStatus.SUCCESS}),
                    }

                    if "sid" not in history_msg["hd"]:
                        history_msg["hd"]["sid"] = sid
                    if "event" not in history_msg["hd"]:
                        history_msg["hd"]["event"] = ChatEvent.CHAT_MESSAGE.value
                    if "role" not in history_msg["hd"]:
                        history_msg["hd"]["role"] = participant

                    await websocket.send_json(history_msg)
                except Exception as hist_err:
                    self.log.warning(f"[WS]        -- Failed to send history message: {hist_err}")
                    continue

            self.log.info(f"[WS]        -- Chat history loaded and sent to late-joined user")
        except Exception as e:
            self.log.warning(f"[WS]        -- Failed to load chat history: {e}")

    async def _load_chat_history(self, sid: str) -> Tuple[list[str], Optional[str]]:
        chat_history: list[str] = []
        previous_contract_draft = None
        stream_key = f"session:chat:{sid}"

        try:
            redis_client = self.ctx.redis_handler.get_client()
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

                if previous_contract_draft is None:
                    contract_draft_from_msg = body_data.get("bd", {}).get("contract_draft") if isinstance(body_data.get("bd"), dict) else None
                    if contract_draft_from_msg:
                        previous_contract_draft = contract_draft_from_msg

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
            self.log.warning(f"[WS] Failed to load chat history: {e}")
            chat_history = []

        self.log.info(f"[WS] Chat history loaded: {len(chat_history)} messages")
        chat_history.reverse()
        return chat_history, previous_contract_draft


async def handle_llm_invocation(ctx, websocket, msg: dict):
    service = ChatbotService(ctx)
    return await service.handle_llm_invocation(websocket, msg)
