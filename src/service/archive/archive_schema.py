from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ArchivedSessionSummary(BaseModel):
    sid: str
    userId: Optional[str] = None
    client_name: Optional[str] = None
    provider_name: Optional[str] = None
    current_step: Optional[str] = None
    updated_at: Optional[str] = None
    progress: Optional[float] = None


class ArchivedChatMessage(BaseModel):
    id: str
    participant: Optional[str] = None
    timestamp: Optional[str] = None
    message: Dict[str, Any]


class ArchiveSessionDetail(BaseModel):
    state: Dict[str, Any] = Field(default_factory=dict)
    chat_history: List[ArchivedChatMessage] = Field(default_factory=list)
