import time
from abc import ABC, abstractmethod
from langchain_community.llms import Ollama

def load_all_llm_managers():
    from .llm_node_manager import NodeLLMManager
    from .llm_ank_manager import AnkLLMManager

class BaseLLMManager(ABC):
    """
    BaseLLMManager

    - 최소한의 공통 기능만 제공하는 추상 부모 클래스입니다.
    - init/destroy와 모델 생성 로직만 담당하며,
    - 나머지 기능은 각 매니저에서 자유롭게 구현합니다.

    필수 속성 (자식 클래스에서 선언해야 함):
    - manager_key: ctx.llm_models[manager_key] 형태로 접근될 고유 식별자
    - model_key: cfg.llm.models[model_key]로 접근하여 사용할 LLM 구성 식별자
    """

    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
        self.model = None
        self.initialized = False

    @property
    @abstractmethod
    def manager_key(self) -> str:
        """Manager의 고유 식별자"""
        pass

    @property
    @abstractmethod
    def model_key(self) -> str:
        """사용할 LLM 모델 설정 키"""
        pass

    def init(self):
        """LLM 모델 초기화"""
        if not self.model:
            self.model = self._get_model()
        if not self.model:
            raise ValueError("No LLM model available")
        self.initialized = True
        self.log.info("LLM", f"- LLMManager '{self.manager_key}' initialized")

    def destroy(self):
        """LLM 모델 정리"""
        self.model = None
        self.initialized = False
        self.log.info("LLM", f"- LLMManager '{self.manager_key}' destroyed")

    def _get_model(self):
        """모델 설정을 기반으로 LLM 인스턴스 생성"""
        model_cfg = self.ctx.cfg.llm.models.get(self.model_key)
        if not model_cfg:
            raise ValueError(f"No config found for model_key '{self.model_key}'")

        if model_cfg.provider != "ollama":
            raise ValueError(f"Unsupported provider: {model_cfg.provider}")

        return Ollama(model=model_cfg.model)