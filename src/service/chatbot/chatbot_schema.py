from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatMessageHeader(BaseModel):
    sid: Optional[str] = None
    event: str
    role: Optional[str] = None
    asker: Optional[str] = None
    step: Optional[str] = None
    user_name: Optional[str] = None
    role_name: Optional[str] = None
    contract_date: Optional[str] = None
    type: Optional[str] = None


class ChatMessageBody(BaseModel):
    text: str = ""
    contract_draft: Optional[str] = None
    current_step: Optional[str] = None
    progress_percentage: Optional[float] = None
    is_completed: Optional[bool] = None
    state: Optional[Any] = None
    detail: Optional[str] = None


class ChatMessage(BaseModel):
    hd: ChatMessageHeader
    bd: ChatMessageBody


class ChatbotPreviewRequest(BaseModel):
    sid: str = Field(..., description="세션 ID")
    user_query: str = Field(..., description="사용자 입력")
    role: str = Field("client", description="발화자 역할")
    user_name: Optional[str] = Field(None, description="사용자 이름")
    client_name: Optional[str] = Field(None, description="의뢰인 이름")
    provider_name: Optional[str] = Field(None, description="용역자 이름")
    contract_date: Optional[str] = Field(None, description="계약일")
    hd: Dict[str, Any] = Field(default_factory=dict, description="원본 헤더 데이터")


class ChatbotPreviewResponse(BaseModel):
    llm_response: Optional[ChatMessage] = None
    step_advance_response: Optional[ChatMessage] = None
    question_answered: bool = False
    state: Dict[str, Any] = Field(default_factory=dict)
