"""
채팅 응답 생성 빌더
다양한 상황에 맞는 응답을 생성합니다
"""
import re
import orjson
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from src.service.ai.asset.prompts import prompts_cfg as prompt
from src.service.ai.chat_state_manager import ChatStep


class ChatResponseBuilder:
    """채팅 응답 생성"""
    
    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
    
    async def build_llm_response(
        self,
        manager,
        state_manager,
        full_prompt: str,
        common_placeholders: Dict[str, Any],
        max_tokens: int = 4000,
        temperature: float = 0.7,
        add_rag_instruction: bool = False
    ) -> Tuple[str, Optional[str]]:
        """
        LLM 응답 생성
        
        Returns:
            (user_message, contract_draft)
        """
        try:
            # RAG 답변 후 복귀 지침 추가
            if add_rag_instruction:
                full_prompt += "\n" + prompt.RAG_ANSWER_ALREADY_SENT_PROMPT
            
            # LLM 호출
            response_text = await manager.generate(
                full_prompt,
                placeholders=common_placeholders,
                max_output_tokens=max_tokens,
                temperature=temperature
            )
            
            # 응답 분리 (USER_MESSAGE + CONTRACT_DRAFT)
            user_message, contract_draft = self._split_response(response_text)
            
            self.log.info(f"[RESPONSE_BUILDER] 응답 생성 완료")
            
            return user_message, contract_draft
            
        except Exception as e:
            self.log.error(f"[RESPONSE_BUILDER] 응답 생성 실패: {e}")
            raise
    
    def _split_response(
        self,
        response_text: str
    ) -> Tuple[str, Optional[str]]:
        """
        LLM 응답을 USER_MESSAGE와 CONTRACT_DRAFT로 분리
        """
        user_message = response_text
        contract_draft = None
        
        try:
            # 1차: LangChain JsonOutputParser 시도
            from langchain_core.output_parsers import JsonOutputParser
            parser = JsonOutputParser()
            parsed = parser.parse(response_text)
            
            if isinstance(parsed, dict):
                if "USER_MESSAGE" in parsed:
                    user_message = str(parsed.get("USER_MESSAGE") or "").strip()
                if "CONTRACT_DRAFT" in parsed:
                    contract_draft = str(parsed.get("CONTRACT_DRAFT") or "").strip()
                return user_message, contract_draft
                
        except Exception as e:
            self.log.debug(f"[RESPONSE_BUILDER] LangChain 파싱 실패: {e}")
        
        # 2차: 수동 JSON 파싱
        try:
            json_match = re.search(r"```(?:json)?\s*(.*?)```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_str = response_text
            
            if json_str.startswith("{"):
                try:
                    parsed = orjson.loads(json_str)
                except Exception:
                    parsed = json.loads(json_str, strict=False)
                
                if isinstance(parsed, dict):
                    if "USER_MESSAGE" in parsed:
                        user_message = str(parsed.get("USER_MESSAGE") or "").strip()
                    if "CONTRACT_DRAFT" in parsed:
                        contract_draft = str(parsed.get("CONTRACT_DRAFT") or "").strip()
                    return user_message, contract_draft
                    
        except Exception as e:
            self.log.debug(f"[RESPONSE_BUILDER] 수동 JSON 파싱 실패: {e}")
        
        # 3차: 섹션 형식 분리
        try:
            user_match = re.search(
                r"USER_MESSAGE:\s*(.*?)(?:\nCONTRACT_DRAFT:|$)",
                response_text,
                re.DOTALL
            )
            contract_match = re.search(
                r"CONTRACT_DRAFT:\s*(.*)$",
                response_text,
                re.DOTALL
            )
            
            if user_match:
                user_message = user_match.group(1).strip()
            if contract_match:
                contract_draft = contract_match.group(1).strip()
                
        except Exception as e:
            self.log.debug(f"[RESPONSE_BUILDER] 섹션 분리 실패: {e}")
        
        return user_message, contract_draft
    
    def build_step_advance_response(
        self,
        sid: str,
        asker: str,
        next_step: ChatStep,
        state_manager,
        prev_step_name: str,
        next_step_name: str
    ) -> Dict[str, Any]:
        """단계 진행 메시지 생성"""
        try:
            # 확정 메시지 생성
            template_key = "complete" if next_step == ChatStep.COMPLETED else "next"
            template = prompt.MESSAGE_TEMPLATES[template_key]
            response_text = template.format(
                step=prev_step_name,
                next_step=next_step_name
            )
            
            return {
                "hd": {
                    "sid": sid,
                    "event": "llm.response",
                    "role": "assistant",
                    "asker": asker,
                    "step": next_step.value,
                    "user_name": state_manager.user_info.get("user_name") or asker,
                    "role_name": state_manager.user_info.get("role"),
                    "contract_date": state_manager.user_info.get("contract_date"),
                },
                "bd": {
                    "text": response_text,
                    "contract_draft": None,
                    "current_step": next_step.value,
                    "progress_percentage": 100.0 if next_step == ChatStep.COMPLETED else self._calculate_progress(next_step),
                    "is_completed": next_step == ChatStep.COMPLETED,
                    "state": "success"
                }
            }
            
        except Exception as e:
            self.log.error(f"[RESPONSE_BUILDER] 단계 진행 응답 생성 실패: {e}")
            return {}
    
    def _calculate_progress(self, current_step: ChatStep) -> float:
        """진행률 계산"""
        try:
            steps = list(ChatStep)
            if current_step not in steps:
                return 0.0
            
            current_idx = steps.index(current_step)
            total_steps = len(steps)
            
            if current_step == ChatStep.COMPLETED:
                return 100.0
            else:
                return round((current_idx / (total_steps - 1)) * 100, 1)
                
        except Exception:
            return 0.0
    
    def build_error_response(
        self,
        sid: str,
        error_msg: str,
        current_step: Optional[ChatStep] = None
    ) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            "hd": {
                "sid": sid,
                "event": "llm.error",
                "role": "assistant",
            },
            "bd": {
                "text": error_msg,
                "state": "error"
            }
        }
