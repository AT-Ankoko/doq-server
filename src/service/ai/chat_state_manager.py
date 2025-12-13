"""
대화 상태 및 Step 추적 관리 모듈
세션별 대화 진행 상태, 수집된 정보, 현재 step 등을 관리합니다.
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import re
import orjson
import src.utils.redis_basic_utils as ru
from src.service.ai.asset.prompts.doq_prompts_confirmation import _CONFIRM_PATTERNS
from src.service.ai.asset.prompts.doq_prompts_chat_scenario import STEP_PROMPTS

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
            "userId": user_info.get("userId") if user_info else None,
            "client_name": user_info.get("client_name") if user_info else None,
            "provider_name": user_info.get("provider_name") if user_info else None,
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
        
        # 진행률
        self.progress_percentage = 0.0
        self._update_progress()
        
    def _update_progress(self):
        """현재 단계에 따른 진행률 계산"""
        try:
            steps = list(ChatStep)
            if not isinstance(self.current_step, ChatStep):
                self.current_step = ChatStep(self.current_step)
            
            current_idx = steps.index(self.current_step)
            # 마지막 단계(completed)는 100%
            if self.current_step == ChatStep.COMPLETED:
                self.progress_percentage = 100.0
            else:
                self.progress_percentage = round((current_idx / len(steps)) * 100, 1)
        except Exception:
            self.progress_percentage = 0.0
    
    def check_confirm_pattern(self, user_text: str) -> bool:
        """
        사용자의 응답이 확정/진행 의사 패턴과 일치하는지 확인 (상태 변경 없음)
        """
        text = (user_text or "").strip()
        for pattern in _CONFIRM_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        return False

    def handle_user_confirm(self, user_text: str) -> bool:
        """
        사용자의 응답이 확정/진행 의사로 해석될 경우 다음 단계로 이동
        """
        if self.check_confirm_pattern(user_text):
            self.move_to_next_step()
            return True
        return False
    
    def move_to_next_step(self) -> ChatStep:
        """다음 단계로 이동 (Enum 일관성 보장)"""
        steps = list(ChatStep)
        # current_step이 string일 경우 Enum으로 변환
        if not isinstance(self.current_step, ChatStep):
            try:
                self.current_step = ChatStep(self.current_step)
            except Exception:
                self.current_step = ChatStep.INTRODUCTION
        current_idx = steps.index(self.current_step)
        if current_idx < len(steps) - 1:
            self.current_step = steps[current_idx + 1]
            # step_history에 Enum만 추가
            if not self.step_history or self.step_history[-1] != self.current_step:
                self.step_history.append(self.current_step)
            self.updated_at = datetime.now().isoformat()
            self._update_progress()
            return self.current_step
        return self.current_step
    
    def jump_to_step(self, step) -> ChatStep:
        """특정 단계로 이동 (Enum 일관성 보장)"""
        # step이 string이면 Enum으로 변환
        if not isinstance(step, ChatStep):
            try:
                step = ChatStep(step)
            except Exception:
                step = ChatStep.INTRODUCTION
        self.current_step = step
        if step not in self.step_history:
            self.step_history.append(step)
        self.updated_at = datetime.now().isoformat()
        self._update_progress()
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
            "progress_percentage": self.progress_percentage
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON 변환용 딕셔너리"""
        return self.get_status()
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ChatStateManager':
        """딕셔너리에서 복원 (Enum 일관성 보장)"""
        user_info = data.get("user_info", {})
        manager = ChatStateManager(data.get("sid", "unknown"), user_info=user_info)
        # current_step이 string이면 Enum으로 변환
        cur_step = data.get("current_step", "introduction")
        if not isinstance(cur_step, ChatStep):
            try:
                cur_step = ChatStep(cur_step)
            except Exception:
                cur_step = ChatStep.INTRODUCTION
        manager.current_step = cur_step
        # step_history도 Enum으로 변환
        step_hist = data.get("step_history", [])
        manager.step_history = []
        for s in step_hist:
            if isinstance(s, ChatStep):
                manager.step_history.append(s)
            else:
                try:
                    manager.step_history.append(ChatStep(s))
                except Exception:
                    continue
        # collected_data는 그대로
        manager.collected_data = data.get("collected_data", {})
        role_inputs_data = data.get("role_inputs", {"client": [], "provider": []})
        # 하위 호환: 기존 "갑"/"을" 키도 지원
        manager.role_inputs = {
            "client": role_inputs_data.get("client") or role_inputs_data.get("갑") or [],
            "provider": role_inputs_data.get("provider") or role_inputs_data.get("을") or [],
        }
        manager.conflicts = data.get("conflicts", [])
        manager.created_at = data.get("created_at", datetime.now().isoformat())
        manager.updated_at = data.get("updated_at", datetime.now().isoformat())
        
        # 진행률 복원
        if "progress_percentage" in data:
            manager.progress_percentage = data["progress_percentage"]
        else:
            manager._update_progress()
            
        return manager


class SessionStateCache:
    """세션 상태 캐시 (Redis + 메모리 캐싱)"""

    _cache: Dict[str, ChatStateManager] = {}
    _REDIS_PREFIX = "session:chat_state:"

    @classmethod
    def _redis_key(cls, sid: str) -> str:
        return f"{cls._REDIS_PREFIX}{sid}"

    @classmethod
    async def get(cls, sid: str, ctx=None) -> Optional[ChatStateManager]:
        """세션 상태 조회 (Redis 우선, 실패 시 메모리 캐시 사용)"""
        if sid in cls._cache:
            return cls._cache[sid]

        if ctx:
            manager = await cls._load_from_redis(ctx, sid)
            if manager:
                cls._cache[sid] = manager
                return manager

        return None

    @classmethod
    async def save(cls, manager: ChatStateManager, ctx=None):
        """세션 상태 저장 (Redis + 메모리)"""
        cls._cache[manager.sid] = manager

        if ctx:
            await cls._save_to_redis(ctx, manager)

    @classmethod
    async def delete(cls, sid: str, ctx=None):
        """세션 상태 삭제"""
        cls._cache.pop(sid, None)

        if ctx:
            await cls._delete_from_redis(ctx, sid)

    @classmethod
    async def exists(cls, sid: str, ctx=None) -> bool:
        """세션 존재 여부"""
        if sid in cls._cache:
            return True

        if ctx:
            try:
                return await ru.redis_exists(ctx, cls._redis_key(sid))
            except Exception as e:
                ctx.log.warning(f"[WS]        -- Redis check failed for session {sid}: {e}")
                return False

        return False

    @classmethod
    async def list_all(cls, ctx=None) -> Dict[str, Dict[str, Any]]:
        """모든 세션 상태 조회 (가능하면 Redis에서 불러와 메모리 동기화)"""
        if ctx:
            try:
                results = await ru.redis_search_by_prefix(ctx, cls._REDIS_PREFIX)
                for key, data in results.items():
                    if not data:
                        continue
                    try:
                        manager_dict = orjson.loads(data)
                        manager = ChatStateManager.from_dict(manager_dict)
                        cls._cache[manager.sid] = manager
                    except Exception as e:
                        ctx.log.warning(f"[WS]        -- Failed to load session state from Redis ({key}): {e}")
                        continue
            except Exception as e:
                ctx.log.warning(f"[WS]        -- Redis list_all failed: {e}")

        return {sid: manager.to_dict() for sid, manager in cls._cache.items()}

    @classmethod
    async def _load_from_redis(cls, ctx, sid: str) -> Optional[ChatStateManager]:
        try:
            data = await ru.redis_get(ctx, cls._redis_key(sid))
            if not data:
                return None
            manager_dict = orjson.loads(data)
            return ChatStateManager.from_dict(manager_dict)
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to load session state from Redis for {sid}: {e}")
            return None

    @classmethod
    async def _save_to_redis(cls, ctx, manager: ChatStateManager):
        try:
            await ru.redis_set(
                ctx,
                cls._redis_key(manager.sid),
                orjson.dumps(manager.to_dict()).decode(),
            )
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to save session state to Redis for {manager.sid}: {e}")

    @classmethod
    async def _delete_from_redis(cls, ctx, sid: str):
        try:
            await ru.redis_delete(ctx, cls._redis_key(sid))
        except Exception as e:
            ctx.log.warning(f"[WS]        -- Failed to delete session state from Redis for {sid}: {e}")
