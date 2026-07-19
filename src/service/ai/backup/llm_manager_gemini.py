import json
import re
import time
import os  # 추가
import google.generativeai as genai  # Gemini 라이브러리 추가
from asyncio import to_thread
from typing import Any, Dict, List, Optional, Union
import orjson

from src.service.conf.gemini_api_key import GEMINI_API_KEY
from src.service.ai.asset.prompts.doq_prompts_injection import _INJECTION_PATTERNS


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


class LLMManager:
    def __init__(self, ctx, provider: str, model: str):
        self.ctx = ctx
        self.provider = provider
        self.model = model

        if self.provider == "gemini":
            api_key = GEMINI_API_KEY
            api_key = os.environ.get("GEMINI_API_KEY")
            # if not api_key:
            #     raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
            
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel(self.model)
        else:
            raise ValueError(f"Unsupported provider: {provider}. Supported provider is 'gemini'.")

    def _is_prompt_injection(self, text: str) -> bool:
        """
        프롬프트 인젝션 공격 패턴 탐지
        """
        text_lower = text.lower()
        for pattern in _INJECTION_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    async def retrieve(self, query: str, top_k: int = 3) -> list:
        """
        RAG용 문서 검색 (mock retrieval). 실제 구현시 벡터DB/검색엔진 연동.
        """
        # TODO: FAISS, Chroma, Elasticsearch 등과 연동하여 구현 가능
        # 아래는 예시용 mock retrieval
        return [
            f"[MockDoc1] '{query}'와 관련된 문서1 내용.",
            f"[MockDoc2] '{query}'와 관련된 문서2 내용.",
            f"[MockDoc3] '{query}'와 관련된 문서3 내용."
        ][:top_k]

    async def rag_generate(
        self,
        query: str,
        *,
        prompt_template: str = None,
        top_k: int = 3,
        placeholders: Optional[Dict[str, Any]] = None,
        **options
    ) -> str:
        """
        RAG: 검색된 문서와 쿼리를 합쳐 LLM에 전달하여 답변 생성
        """
        # 프롬프트 인젝션 탐지
        if self._is_prompt_injection(query):
            self.ctx.log.warning("LLM", f"-- Prompt injection detected: {query}")
            return "아직 없는 기능입니다"
        
        docs = await self.retrieve(query, top_k=top_k)
        context = "\n".join(docs)
        if not prompt_template:
            prompt_template = (
                "아래의 문서와 사용자의 질문을 참고하여 답변하세요.\n"
                "문서:\n{{context}}\n\n질문: {{query}}\n답변:"
            )
        
        return await self.generate(
            prompt_template,
            placeholders={
                "context": context,
                "query": query,
                **(placeholders or {})
            },
            **options
        )

    async def generate(
        self,
        prompt: Union[str, List[str]],
        *,
        placeholders: Optional[Dict[str, Any]] = None,
        **options
    ) -> str:
        # 프롬프트 인젝션 탐지 (placeholders 검사)
        if placeholders:
            for key, value in placeholders.items():
                if isinstance(value, str) and self._is_prompt_injection(value):
                    self.ctx.log.warning("LLM", f"-- Prompt injection detected in placeholder '{key}'")
                    return "아직 없는 기능입니다"

        final_prompt = self._compose_prompt(prompt, placeholders=placeholders)

        if self.provider == "gemini":
            generation_config = genai.types.GenerationConfig(**options)

            def _call_gemini():
                # 동기 함수인 generate_content를 비동기 컨텍스트에서 실행합니다.
                return self.gemini_model.generate_content(
                    final_prompt,
                    generation_config=generation_config
                )

            try:
                response = await to_thread(_call_gemini)
                if not response or not response.text:
                    self.ctx.log.warning(f"[LLM] Empty response from Gemini API")
                    return "죄송합니다. 응답을 생성할 수 없습니다."
                return response.text
            
            except Exception as e:
                error_msg = str(e)
                self.ctx.log.error(f"[LLM] Gemini API 호출 중 오류 발생: {error_msg}")
                import traceback
                self.ctx.log.error(f"[LLM] Traceback: {traceback.format_exc()}")
                
                # Rate limit 에러 처리
                if "429" in error_msg or "Resource exhausted" in error_msg:
                    error_response = "죄송합니다. 현재 AI 서비스 사용량이 많아 잠시 후 다시 시도해주세요. (API 할당량 초과)"
                    self.ctx.log.warning(f"[LLM] Rate limit error - returning user-friendly message")
                    return error_response
                elif "400" in error_msg or "Invalid" in error_msg:
                    return "죄송합니다. 요청 형식에 오류가 있습니다. 다시 시도해주세요."
                elif "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg:
                    return "죄송합니다. API 인증에 실패했습니다. 관리자에게 문의해주세요."
                else:
                    return f"죄송합니다. AI 응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        
        return "지원하지 않는 provider입니다."

    # ------------------------
    # 내부: 프롬프트 합성 + 치환 (변경 없음)
    # ------------------------
    def _compose_prompt(
        self,
        prompt: Union[str, List[str]],
        *,
        placeholders: Optional[Dict[str, Any]] = None,
    ) -> str:
        if isinstance(prompt, list):
            rendered = [self._render_placeholders(str(p), placeholders) for p in prompt if p]
            return "\n\n".join(rendered)
        return self._render_placeholders(str(prompt), placeholders)

    def _render_placeholders(self, text: str, placeholders: Optional[Dict[str, Any]]) -> str:
        if not placeholders:
            return text

        def _to_str(val: Any) -> str:
            if val is None:
                return ""
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False, indent=2)
            if isinstance(val, (str, int, float, bool)):
                return str(val)
            return repr(val)

        def repl(m: re.Match) -> str:
            key = m.group(1)
            if key in placeholders:
                return _to_str(placeholders[key])
            return m.group(0)

        return _PLACEHOLDER_RE.sub(repl, text)
    
    async def classify_response(
        self,
        user_response: str,
        current_step: str,
        **placeholders
    ) -> Dict[str, Any]:
        """
        사용자 응답을 분석하여 단계별로 필요한 데이터를 추출합니다.
        JSON 형식으로 structured output을 반환합니다.
        
        Args:
            user_response: 사용자의 입력 텍스트
            current_step: 현재 대화 단계 (예: "work_scope", "budget" 등)
            **placeholders: 추가 context 정보
        
        Returns:
            {
                "is_complete": bool,  # 충분한 답변인가?
                "extracted_data": dict,  # 추출된 정보
                "confidence": float,  # 신뢰도 (0.0~1.0)
                "next_action": str,  # "proceed" | "ask_clarification" | "conflict_detected"
                "clarification_needed": str | null,  # 추가 질문이 필요하면 그 내용
                "extracted_fields": dict,  # 수집된 데이터 필드
            }
        """
        from src.service.ai.asset.prompts.doq_prompts_chat_scenario import RESPONSE_CLASSIFICATION_PROMPT
        
        # 분류용 프롬프트 구성
        classification_prompt = self._compose_prompt(
            RESPONSE_CLASSIFICATION_PROMPT,
            placeholders=placeholders
        )
        
        # LLM 호출
        response_text = await self.generate(
            classification_prompt,
            max_output_tokens=1000,
            temperature=0.3  # 낮은 온도로 일관된 JSON 출력
        )
        
        # JSON 파싱
        try:
            # 응답에서 JSON 블록 추출 (```json ... ``` 형식일 수 있음)
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 직접 JSON인 경우
                json_str = response_text
            
            try:
                classification_result = orjson.loads(json_str)
            except Exception:
                classification_result = json.loads(json_str, strict=False)

            self.ctx.log.debug(f"[LLM] Response classification result: {classification_result}")
            return classification_result
            
        except Exception as e:
            self.ctx.log.error(f"[LLM] Failed to parse classification response: {e}")
            self.ctx.log.debug(f"[LLM] Raw response: {response_text}")
            
            # 파싱 실패 시 기본값 반환
            return {
                "is_complete": False,
                "extracted_data": {},
                "confidence": 0.0,
                "next_action": "ask_clarification",
                "clarification_needed": "응답을 정확히 이해하기 위해 다시 설명해주실 수 있을까요?",
                "extracted_fields": {}
            }
