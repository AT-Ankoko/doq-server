"""
대화 상태 및 Step 추적 관리 모듈
세션별 대화 진행 상태, 수집된 정보, 현재 step 등을 관리합니다.
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import json
import re
from src.service.ai.asset.prompts.doq_prompts_confirmation import _CONFIRM_PATTERNS
from src.service.ai.asset.prompts.doq_chat_scenario import STEP_PROMPTS

class ChatEvent(Enum):
    """WebSocket 이벤트 타입"""
    LLM_INVOKE = "llm.invoke"       # LLM 호출 요청
    LLM_RESPONSE = "llm.response"   # LLM 응답
    LLM_ERROR = "llm.error"         # LLM 오류
    CHAT_MESSAGE = "chat.message"   # 일반 채팅 메시지
    TYPING = "typing"               # 타이핑 중


class ChatStep(Enum):
    """대화 진행 단계"""
    INTRODUCTION = "introduction"          # 0: 소개 및 초기 인사
    WORK_SCOPE = "work_scope"              # 1: 작업 범위 확인
    WORK_PERIOD = "work_period"            # 2: 작업 기간 확인
    BUDGET = "budget"                      # 3: 대금 확인
    REVISIONS = "revisions"                # 4: 수정 횟수 확인
    COPYRIGHT = "copyright"                # 5: 저작권 귀속 확인
    CONFIDENTIALITY = "confidentiality"    # 6: 기타 특약
    CONFLICT_RESOLUTION = "conflict_resolution"  # 7: 갑/을 조건 충돌 해결
    FINALIZATION = "finalization"          # 8: 최종 확인 및 계약서 생성
    COMPLETED = "completed"                # 9: 완료
    
    @property
    def prompt(self) -> str:
        """단계별 프롬프트 가이드 반환"""
        return STEP_PROMPTS.get(self.value, "")


class ChatStateManager:
    """세션별 대화 상태 관리"""
    
    def __init__(self, sid: str, user_info: Optional[Dict[str, Any]] = None):
        self.sid = sid
        self.current_step = ChatStep.INTRODUCTION
        self.step_history = [ChatStep.INTRODUCTION]
        
        # 사용자 정보 (snake_case)
        self.user_info = {
            "user_name": user_info.get("user_name") if user_info else None,
            "user_role": user_info.get("user_role") if user_info else None,
            "contract_date": user_info.get("contract_date") if user_info else None,
        }
        
        # 수집된 정보
        self.collected_data = {
            "client_name": None,           # 의뢰인(클라이언트) 이름
            "client_company": None,        # 의뢰인 회사
            "provider_name": None,         # 서비스 제공자 이름
            "provider_company": None,      # 서비스 제공자 회사
            "category": None,              # 프로젝트 카테고리
            "work_scope": None,
            "work_period": None,
            "start_date": None,
            "end_date": None,
            "budget": None,
            "revision_count": None,
            "copyright_owner": None,
            "confidentiality_terms": None,
            "special_conditions": None,
        }
        
        # 역할별 입력 추적
        self.role_inputs = {
            "client": [],      # 의뢰인(클라이언트)의 입력
            "provider": [],    # 서비스 제공자의 입력
        }
        
        # 충돌 사항
        self.conflicts = []
        
        # 타임스탬프
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def handle_user_confirm(self, user_text: str) -> bool:
        """
        사용자의 응답이 확정/진행 의사로 해석될 경우 다음 단계로 이동
        """
        text = (user_text or "").strip()
        for pattern in _CONFIRM_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                self.move_to_next_step()
                return True
        return False
    
    def move_to_next_step(self) -> ChatStep:
        """다음 단계로 이동"""
        steps = list(ChatStep)
        current_idx = steps.index(self.current_step)
        
        if current_idx < len(steps) - 1:
            self.current_step = steps[current_idx + 1]
            self.step_history.append(self.current_step)
            self.updated_at = datetime.now().isoformat()
            return self.current_step
        return self.current_step
    
    def jump_to_step(self, step: ChatStep) -> ChatStep:
        """특정 단계로 이동"""
        self.current_step = step
        if step not in self.step_history:
            self.step_history.append(step)
        self.updated_at = datetime.now().isoformat()
        return step
    
    def update_data(self, key: str, value: Any):
        """수집된 데이터 업데이트"""
        if key in self.collected_data:
            self.collected_data[key] = value
            self.updated_at = datetime.now().isoformat()
    
    def add_role_input(self, role: str, text: str):
        """역할별 입력 기록"""
        if role in self.role_inputs:
            self.role_inputs[role].append({
                "text": text,
                "timestamp": datetime.now().isoformat(),
                "step": self.current_step.value
            })
            self.updated_at = datetime.now().isoformat()
    
    def add_conflict(self, description: str, client_position: str, designer_position: str):
        """충돌 사항 기록"""
        self.conflicts.append({
            "step": self.current_step.value,
            "description": description,
            "client_position": client_position,
            "designer_position": designer_position,
            "timestamp": datetime.now().isoformat(),
            "resolved": False
        })
        self.jump_to_step(ChatStep.CONFLICT_RESOLUTION)
        self.updated_at = datetime.now().isoformat()
    
    def resolve_conflict(self, conflict_idx: int):
        """충돌 해결 표시"""
        if 0 <= conflict_idx < len(self.conflicts):
            self.conflicts[conflict_idx]["resolved"] = True
            self.updated_at = datetime.now().isoformat()
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        return {
            "sid": self.sid,
            "user_info": self.user_info,
            "current_step": self.current_step.value,
            "step_history": [s.value for s in self.step_history],
            "collected_data": self.collected_data,
            "role_inputs": self.role_inputs,
            "conflicts": self.conflicts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress_percentage": round(
                (list(ChatStep).index(self.current_step) / len(ChatStep)) * 100, 1
            )
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON 변환용 딕셔너리"""
        return self.get_status()
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ChatStateManager':
        """딕셔너리에서 복원"""
        user_info = data.get("user_info", {})
        manager = ChatStateManager(data.get("sid", "unknown"), user_info=user_info)
        manager.current_step = ChatStep(data.get("current_step", "introduction"))
        manager.step_history = [ChatStep(s) for s in data.get("step_history", [])]
        manager.collected_data = data.get("collected_data", {})
        manager.role_inputs = data.get("role_inputs", {"갑": [], "을": []})
        manager.conflicts = data.get("conflicts", [])
        manager.created_at = data.get("created_at", datetime.now().isoformat())
        manager.updated_at = data.get("updated_at", datetime.now().isoformat())
        return manager


class SessionStateCache:
    """세션 상태 캐시 (메모리 기반, 실제로는 Redis 권장)"""
    
    _cache = {}
    
    @classmethod
    def get(cls, sid: str) -> Optional[ChatStateManager]:
        """세션 상태 조회"""
        return cls._cache.get(sid)
    
    @classmethod
    def save(cls, manager: ChatStateManager):
        """세션 상태 저장"""
        cls._cache[manager.sid] = manager
    
    @classmethod
    def delete(cls, sid: str):
        """세션 상태 삭제"""
        if sid in cls._cache:
            del cls._cache[sid]
    
    @classmethod
    def exists(cls, sid: str) -> bool:
        """세션 존재 여부"""
        return sid in cls._cache
    
    @classmethod
    def list_all(cls) -> Dict[str, Dict[str, Any]]:
        """모든 세션 상태 조회"""
        return {sid: manager.to_dict() for sid, manager in cls._cache.items()}
