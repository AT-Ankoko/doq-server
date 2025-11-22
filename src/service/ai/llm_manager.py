import json
import re
import time
import os  # 추가
import google.generativeai as genai  # Gemini 라이브러리 추가
from asyncio import to_thread
from typing import Any, Dict, List, Optional, Union

from src.service.conf.gemini_api_key import GEMINI_API_KEY


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")

class LLMManager:
    def __init__(self, ctx, provider: str, model: str):
        self.ctx = ctx
        self.provider = provider
        self.model = model

        if self.provider == "gemini":
            api_key = GEMINI_API_KEY
            # api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
            
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel(self.model)
        else:
            raise ValueError(f"Unsupported provider: {provider}. Supported provider is 'gemini'.")

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
        docs = await self.retrieve(query, top_k=top_k)
        context = "\n".join(docs)
        if not prompt_template:
            prompt_template = (
                "아래의 문서와 사용자의 질문을 참고하여 답변하세요.\n"
                "문서:\n{{context}}\n\n질문: {{query}}\n답변:"
            )
        rag_prompt = self._render_placeholders(prompt_template, {
            "context": context,
            "query": query,
            **(placeholders or {})
        })
        return await self.generate(rag_prompt, **options)

    async def generate(
        self,
        prompt: Union[str, List[str]],
        *,
        placeholders: Optional[Dict[str, Any]] = None,
        **options
    ) -> str:
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
                return response.text
            except Exception as e:
                print(f"Gemini API 호출 중 오류 발생: {e}")
                return ""
        
        return ""

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
    

    
    def parse_reports(self, raw_text: str) -> dict:
        """
        Gemini 응답에서 첫 번째 JSON 블록만 뽑아 time과 함께 반환
        """
        # ```json ... ``` 안쪽 내용 먼저 찾기
        match = re.search(r"```json\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
        if match:
            raw_json = match.group(1).strip()
        else:
            # 없으면 그냥 { } 블록 찾아보기
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            raw_json = match.group(0).strip() if match else "{}"

        try:
            reports = json.loads(raw_json)
        except Exception:
            reports = {}

        return {
            "time": int(time.time()),
            "reports": reports
        }