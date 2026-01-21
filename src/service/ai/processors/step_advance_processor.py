"""
사용자 응답 분류 및 단계 진행 판단 프로세서
"""
import re
import orjson
from typing import Optional, Dict, Any
from src.service.ai.processors.base_processor import BaseProcessor, ProcessResult
from src.service.ai.asset.prompts import prompts_cfg as prompt
from src.service.ai.chat_state_manager import ChatStep


class StepAdvanceProcessor(BaseProcessor):
    """
    사용자 응답을 분석하여 단계 진행 여부를 판단합니다
    """
    
    async def process(
        self,
        user_query: str,
        current_step: ChatStep,
        conversation_context: str,
        state_manager=None,
        manager=None,
        **kwargs
    ) -> ProcessResult:
        """
        Args:
            user_query: 사용자 입력
            current_step: 현재 단계
            conversation_context: 대화 이력
            state_manager: ChatStateManager
            manager: LLMManager
        
        Returns:
            ProcessResult with {
                "should_advance": bool,
                "reason": str,
                "source": "llm" | "keyword" | "mutual_agreement"
            }
        """
        try:
            if not manager or not state_manager:
                return ProcessResult(
                    success=False,
                    error="Manager not provided"
                )
            
            should_advance = False
            reason = ""
            source = ""
            
            # 1단계: LLM 기반 진행 판단
            llm_result = await self._llm_based_decision(
                user_query, current_step, conversation_context, manager
            )
            
            if llm_result["advance"]:
                should_advance = True
                reason = llm_result["reason"]
                source = "llm"
            
            # 2단계: 명시적 키워드 확인 (LLM 결과 무시하고 진행)
            if not should_advance and state_manager.check_confirm_pattern(user_query):
                should_advance = True
                reason = f"진행 의사 패턴 매칭: {user_query[:30]}"
                source = "keyword"
            
            # 3단계: 양측 합의 확인
            if not should_advance:
                mutual_agreement = self._check_mutual_agreement(
                    user_query, conversation_context, state_manager
                )
                if mutual_agreement:
                    should_advance = True
                    reason = "양측 합의 확인"
                    source = "mutual_agreement"
            
            # 4단계: 초기 단계에서는 입력만으로도 진행
            if not should_advance and current_step == ChatStep.INTRODUCTION and user_query.strip():
                should_advance = True
                reason = "초기 단계 자동 진행"
                source = "auto_intro"
            
            return ProcessResult(
                success=True,
                data={
                    "should_advance": should_advance,
                    "reason": reason,
                    "source": source
                }
            )
            
        except Exception as e:
            # 예외 발생 시에도 성공/실패 반환 (연결 끊지 않음)
            self.log.warning(f"[STEP_ADVANCE_PROCESSOR] {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                data={
                    "should_advance": False,
                    "reason": "LLM 판단 실패, 수동 검증 필요",
                    "source": "fallback"
                }
            )
    
    async def _llm_based_decision(
        self,
        user_query: str,
        current_step: ChatStep,
        conversation_context: str,
        manager
    ) -> Dict[str, Any]:
        """LLM을 이용한 단계 진행 판단"""
        try:
            decision_text = await manager.generate(
                prompt.STEP_ROUTER_PROMPT,
                placeholders={
                    "conversation_context": conversation_context,
                    "current_step": current_step.value,
                    "user_query": user_query,
                },
                max_output_tokens=800,
                temperature=0.0
            )
            
            # JSON 파싱
            parsed = self._parse_json_response(decision_text)
            
            if parsed and "advance" in parsed:
                return {
                    "advance": bool(parsed.get("advance")),
                    "reason": parsed.get("reason", "")
                }
            
            # 파싱 실패해도 기본값 반환
            return {"advance": False, "reason": "파싱 실패"}
            
        except Exception as e:
            self.log.warning(f"[STEP_ADVANCE_PROCESSOR] LLM 호출 실패: {e}")
            return {"advance": False, "reason": str(e)}
    
    def _check_mutual_agreement(
        self,
        user_query: str,
        conversation_context: str,
        state_manager
    ) -> bool:
        """양측 합의 여부 확인"""
        try:
            # 최근 대화에서 양측 참여 확인
            has_client = any("client" in line or "의뢰인" in line 
                           for line in conversation_context.split('\n')[-10:])
            has_provider = any("provider" in line or "용역자" in line 
                             for line in conversation_context.split('\n')[-10:])
            
            if not (has_client and has_provider):
                return False
            
            # 확정 키워드 확인
            has_confirm = any(kw in user_query 
                            for kw in prompt.CONFIRM_KEYWORDS)
            
            # 제안 키워드는 없어야 함
            has_proposal = any(kw in user_query 
                             for kw in prompt.PROPOSAL_KEYWORDS)
            
            return has_confirm and not has_proposal
            
        except Exception as e:
            self.log.warning(f"[STEP_ADVANCE_PROCESSOR] 양측 합의 확인 실패: {e}")
            return False
    
    def _parse_json_response(self, response: str) -> dict:
        """JSON 응답 파싱"""
        try:
            # 마크다운 코드블록 제거
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
            
            return orjson.loads(json_str)
        except Exception:
            return {}
