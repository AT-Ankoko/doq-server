"""
채팅 세션 관리 - 계층화된 대화 흐름 관리
"""
from typing import Optional, Dict, Any, Tuple
from src.service.ai.chat_state_manager import ChatStateManager, ChatStep, SessionStateCache
from src.service.ai.processors.question_answering_processor import QuestionAnsweringProcessor
from src.service.ai.processors.step_advance_processor import StepAdvanceProcessor
from src.service.ai.chat_response_builder import ChatResponseBuilder
from src.service.ai.asset.prompts import prompts_cfg as prompt
from datetime import datetime


class ChatSessionManager:
    """
    계층화된 채팅 세션 관리
    - 질문 답변
    - 단계 진행 판단
    - 응답 생성
    """
    
    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
        
        # 프로세서 초기화
        self.qa_processor = QuestionAnsweringProcessor(ctx)
        self.advance_processor = StepAdvanceProcessor(ctx)
        self.response_builder = ChatResponseBuilder(ctx)
    
    async def process_user_input(
        self,
        sid: str,
        user_query: str,
        role: str,
        hd: Dict[str, Any],
        manager,
        state_manager: ChatStateManager,
        chat_history: list,
        previous_contract_draft: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], bool]:
        """
        사용자 입력 처리 (통합)
        
        Returns:
            (llm_response, step_advance_response, question_answered)
        """
        try:
            # 1단계: 질문 탐지 및 답변
            question_answered = False
            qa_result = await self.qa_processor.process(
                user_query=user_query,
                current_step=state_manager.current_step.value,
                manager=manager
            )
            
            if qa_result.success and qa_result.data.get("is_question"):
                # 질문인 경우 답변 반환 (계약 진행 안 함)
                qa_response = self._build_qa_response(
                    sid, role, qa_result.data["answer"], state_manager, hd
                )
                question_answered = True
                self.log.info(f"[SESSION_MANAGER] 질문에 답변 전송")
                return qa_response, None, question_answered
            
            # 2단계: 단계 진행 여부 판단
            conversation_context = "\n".join(chat_history[-10:])
            advance_result = await self.advance_processor.process(
                user_query=user_query,
                current_step=state_manager.current_step,
                conversation_context=conversation_context,
                state_manager=state_manager,
                manager=manager
            )
            
            should_advance = advance_result.data.get("should_advance", False) if advance_result.success else False
            advance_source = advance_result.data.get("source", "") if advance_result.success else ""
            
            # 3단계: 단계 진행 또는 일반 응답
            step_advance_response = None
            
            if should_advance:
                # 단계 진행
                self.log.info(f"[SESSION_MANAGER] 단계 진행: {advance_source}")
                step_advance_response = await self._handle_step_advance(
                    sid, role, state_manager, hd, manager,
                    chat_history, previous_contract_draft
                )
            
            # 4단계: 현재 단계 응답 생성
            llm_response = await self._handle_normal_response(
                sid, role, state_manager, hd, manager,
                user_query, chat_history, previous_contract_draft,
                question_answered
            )
            
            return llm_response, step_advance_response, question_answered
            
        except Exception as e:
            self.log.error(f"[SESSION_MANAGER] 사용자 입력 처리 실패: {e}")
            # 에러 발생해도 응답 반환 (연결 유지)
            error_response = self.response_builder.build_error_response(
                sid=sid,
                error_msg="처리 중 오류가 발생했습니다. 다시 시도해주세요."
            )
            return error_response, None, False
    
    async def _handle_step_advance(
        self,
        sid: str,
        role: str,
        state_manager: ChatStateManager,
        hd: Dict[str, Any],
        manager,
        chat_history: list,
        previous_contract_draft: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """단계 진행 처리"""
        try:
            next_step = state_manager.move_to_next_step()
            
            # step_history 동기화
            if not isinstance(state_manager.current_step, ChatStep):
                state_manager.current_step = ChatStep(state_manager.current_step)
            
            # 상태 저장
            await SessionStateCache.save(state_manager, self.ctx)
            
            # 단계명 매핑
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
            
            prev_step = state_manager.step_history[-2] if len(state_manager.step_history) >= 2 else None
            prev_step_name = step_names_kr.get(prev_step, "이전") if prev_step else "소개"
            next_step_name = step_names_kr.get(next_step, next_step.value)
            
            # 단계 진행 응답 생성
            response = self.response_builder.build_step_advance_response(
                sid=sid,
                asker=role,
                next_step=next_step,
                state_manager=state_manager,
                prev_step_name=prev_step_name,
                next_step_name=next_step_name
            )
            
            self.log.info(f"[SESSION_MANAGER] 단계 진행: {state_manager.current_step.value}")
            
            return response
            
        except Exception as e:
            self.log.error(f"[SESSION_MANAGER] 단계 진행 처리 실패: {e}")
            return None
    
    async def _handle_normal_response(
        self,
        sid: str,
        role: str,
        state_manager: ChatStateManager,
        hd: Dict[str, Any],
        manager,
        user_query: str,
        chat_history: list,
        previous_contract_draft: Optional[str],
        question_answered: bool
    ) -> Dict[str, Any]:
        """일반 응답 생성"""
        try:
            # 프롬프트 구성
            full_prompt = prompt.NORMAL_RESPONSE_PROMPT_TEMPLATE.replace(
                "{system_prompt}",
                "\n".join(prompt.SYSTEM_PROMPTS)
            )
            
            # Placeholders 구성 (간략화)
            common_placeholders = {
                "user_query": user_query,
                "current_step": state_manager.current_step.value,
                "conversation_context": "\n".join(chat_history[-10:]),
            }
            
            # LLM 응답 생성
            user_message, contract_draft = await self.response_builder.build_llm_response(
                manager=manager,
                state_manager=state_manager,
                full_prompt=full_prompt,
                common_placeholders=common_placeholders,
                temperature=0.7,
                add_rag_instruction=question_answered
            )
            
            # 이전 계약서 유지
            if not contract_draft and previous_contract_draft:
                contract_draft = previous_contract_draft
            
            # 응답 구성
            response = {
                "hd": {
                    "sid": sid,
                    "event": "llm.response",
                    "role": "assistant",
                    "asker": role,
                    "step": state_manager.current_step.value,
                    "user_name": hd.get("user_name") or role,
                    "role_name": hd.get("role"),
                    "contract_date": hd.get("contract_date"),
                },
                "bd": {
                    "text": user_message,
                    "contract_draft": contract_draft,
                    "current_step": state_manager.current_step.value,
                    "progress_percentage": self.response_builder._calculate_progress(
                        state_manager.current_step
                    ),
                    "state": "success"
                }
            }
            
            return response
            
        except Exception as e:
            self.log.error(f"[SESSION_MANAGER] 응답 생성 실패: {e}")
            return self.response_builder.build_error_response(
                sid=sid,
                error_msg="응답을 생성할 수 없습니다. 잠시 후 다시 시도해주세요."
            )
    
    def _build_qa_response(
        self,
        sid: str,
        role: str,
        answer: str,
        state_manager: ChatStateManager,
        hd: Dict[str, Any]
    ) -> Dict[str, Any]:
        """질문 답변 응답 생성"""
        return {
            "hd": {
                "sid": sid,
                "event": "llm.response",
                "role": "assistant",
                "asker": role,
                "step": state_manager.current_step.value,
                "user_name": "DoQ",
                "role_name": "assistant",
                "type": "question_answer"
            },
            "bd": {
                "text": answer,
                "state": "success"
            }
        }
