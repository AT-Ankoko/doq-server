"""
질문 탐지 및 RAG 기반 답변 프로세서
"""
import re
import orjson
from typing import Optional
from src.service.ai.processors.base_processor import BaseProcessor, ProcessResult
from src.service.ai.asset.prompts import prompts_cfg as prompt
from src.service.ai.rag_manager import RAGManager


class QuestionAnsweringProcessor(BaseProcessor):
    """사용자 질문을 탐지하고 RAG로 답변을 생성합니다"""
    
    async def process(
        self,
        user_query: str,
        current_step: str,
        manager=None
    ) -> ProcessResult:
        """
        Args:
            user_query: 사용자 입력
            current_step: 현재 단계
            manager: LLMManager 인스턴스
        
        Returns:
            ProcessResult with {
                "is_question": bool,
                "answer": str (질문인 경우),
                "search_query": str
            }
        """
        try:
            if not user_query.strip() or not manager:
                return ProcessResult(
                    success=True,
                    data={"is_question": False}
                )
            
            # 1단계: 질문 탐지
            is_question, search_query = await self._detect_question(
                user_query, current_step, manager
            )
            
            if not is_question:
                return ProcessResult(
                    success=True,
                    data={"is_question": False}
                )
            
            # 2단계: RAG 검색 및 답변 생성
            answer = await self._generate_answer(
                user_query, search_query, manager
            )
            
            return ProcessResult(
                success=True,
                data={
                    "is_question": True,
                    "answer": answer,
                    "search_query": search_query
                }
            )
            
        except Exception as e:
            return self._handle_error(e, "질문 답변")
    
    async def _detect_question(
        self,
        user_query: str,
        current_step: str,
        manager
    ) -> tuple[bool, str]:
        """질문 탐지"""
        try:
            detection_prompt = prompt.QUESTION_DETECTION_PROMPT.format(
                user_query=user_query,
                current_step=current_step
            )
            
            detection_res = await manager.generate(
                detection_prompt,
                temperature=0.1
            )
            
            # JSON 파싱
            det_parsed = self._parse_json_response(detection_res)
            
            if det_parsed and det_parsed.get("is_question"):
                search_query = det_parsed.get("search_query") or user_query
                return True, search_query
            
            return False, ""
            
        except Exception as e:
            self.log.warning(f"[QUESTION_PROCESSOR] 질문 탐지 실패: {e}")
            return False, ""
    
    async def _generate_answer(
        self,
        user_query: str,
        search_query: str,
        manager
    ) -> str:
        """RAG 기반 답변 생성"""
        try:
            # RAG 검색
            rag_manager = RAGManager()
            rag_results = rag_manager.search(search_query, k=2)
            
            if not rag_results:
                return "죄송하지만 관련 정보를 찾을 수 없습니다."
            
            # 답변 생성
            ans_prompt = prompt.RAG_ANSWER_PROMPT.format(
                user_query=user_query,
                rag_context=rag_results
            )
            
            answer = await manager.generate(
                ans_prompt,
                temperature=0.7
            )
            
            return answer.strip()
            
        except Exception as e:
            self.log.warning(f"[QUESTION_PROCESSOR] 답변 생성 실패: {e}")
            return "죄송합니다. 답변을 생성할 수 없습니다."
    
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
