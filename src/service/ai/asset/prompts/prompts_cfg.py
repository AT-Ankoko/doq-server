"""
중앙 집중식 프롬프트 관리 모듈
모든 프롬프트 관련 import/export를 이 파일에서 관리합니다.
"""

# ==================== 기본 시스템 프롬프트 ====================
from src.service.ai.asset.prompts import doq_prompts

SYSTEM_PROMPTS = [
    doq_prompts.INITIAL_PROMPT,   
    doq_prompts.USER_CONTEXT_PROMPT,   
]

# ==================== 초기 프롬프트 ====================
INITIAL_PROMPT = doq_prompts.INITIAL_PROMPT
USER_CONTEXT_PROMPT = doq_prompts.USER_CONTEXT_PROMPT
JSON_OUTPUT_PROMPT = doq_prompts.JSON_OUTPUT_PROMPT

# ==================== RAG 관련 프롬프트 ====================
from src.service.ai.asset.prompts.doq_prompts_rag import (
    QUESTION_DETECTION_PROMPT,
    RAG_ANSWER_PROMPT,
    RAG_ANSWER_ALREADY_SENT_PROMPT,
)

# ==================== 프롬프트 인젝션 탐지 ====================
from src.service.ai.asset.prompts.doq_prompts_injection import _INJECTION_PATTERNS

INJECTION_PATTERNS = _INJECTION_PATTERNS

# ==================== 확정/진행 의사 키워드 및 패턴 ====================
from src.service.ai.asset.prompts.doq_prompts_confirmation import (
    _CONFIRM_PATTERNS,
    _CONTRACT_COMPLETION_PATTERNS,
    CONFIRM_KEYWORDS,
    PROPOSAL_KEYWORDS,
)

CONFIRM_PATTERNS = _CONFIRM_PATTERNS
CONTRACT_COMPLETION_PATTERNS = _CONTRACT_COMPLETION_PATTERNS

# ==================== 채팅 시나리오 (단계별 프롬프트 및 템플릿) ====================
from src.service.ai.asset.prompts.doq_prompts_chat_scenario import (
    STEP_PROMPTS,
    MESSAGE_TEMPLATES,
    START_MESSAGE_PROMPT,
    CONFLICT_RESOLUTION_PROMPT,
    STEP_ROUTER_PROMPT,
    RESPONSE_CLASSIFICATION_PROMPT,
    NORMAL_RESPONSE_PROMPT_TEMPLATE,
    STEP_TRANSITION_PROMPT_TEMPLATE,
    STEP_ADVANCE_CLASSIFICATION_PROMPT,
    STEP_SPECIFIC_INSTRUCTION_TEMPLATE,
    FINAL_CONTRACT_GENERATION_PROMPT,
    COMPLETION_MESSAGE,
    STEP_SUMMARY_PROMPT,
)

# ==================== 계약서 템플릿 ====================
from src.service.ai.asset.prompts.doq_contract_template import CONTRACT_TEMPLATE

__all__ = [
    # 시스템 프롬프트
    "SYSTEM_PROMPTS",
    "INITIAL_PROMPT",
    "USER_CONTEXT_PROMPT",
    "JSON_OUTPUT_PROMPT",
    
    # RAG 프롬프트
    "QUESTION_DETECTION_PROMPT",
    "RAG_ANSWER_PROMPT",
    "RAG_ANSWER_ALREADY_SENT_PROMPT",
    
    # 프롬프트 인젝션
    "INJECTION_PATTERNS",
    
    # 확정/진행 의사
    "CONFIRM_PATTERNS",
    "CONTRACT_COMPLETION_PATTERNS",
    "CONFIRM_KEYWORDS",
    "PROPOSAL_KEYWORDS",
    
    # 채팅 시나리오
    "STEP_PROMPTS",
    "MESSAGE_TEMPLATES",
    "START_MESSAGE_PROMPT",
    "CONFLICT_RESOLUTION_PROMPT",
    "STEP_ROUTER_PROMPT",
    "RESPONSE_CLASSIFICATION_PROMPT",
    "NORMAL_RESPONSE_PROMPT_TEMPLATE",
    "STEP_TRANSITION_PROMPT_TEMPLATE",
    "STEP_ADVANCE_CLASSIFICATION_PROMPT",
    "STEP_SPECIFIC_INSTRUCTION_TEMPLATE",
    "FINAL_CONTRACT_GENERATION_PROMPT",
    "COMPLETION_MESSAGE",
    "STEP_SUMMARY_PROMPT",
    
    # 계약서 템플릿
    "CONTRACT_TEMPLATE",
]