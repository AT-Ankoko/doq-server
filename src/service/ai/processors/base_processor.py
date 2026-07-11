"""
기본 프로세서 추상 클래스
모든 로직 프로세서는 이를 상속받습니다.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProcessResult:
    """프로세서 실행 결과"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message
        }


class BaseProcessor(ABC):
    """모든 프로세서의 기본 클래스"""
    
    def __init__(self, ctx):
        self.ctx = ctx
        self.log = ctx.log
    
    @abstractmethod
    async def process(self, **kwargs) -> ProcessResult:
        """
        실제 로직 실행
        모든 하위 클래스에서 구현해야 함
        """
        pass
    
    def _handle_error(self, error: Exception, step_name: str) -> ProcessResult:
        """일반적인 에러 처리"""
        error_msg = f"{step_name} 처리 실패: {str(error)}"
        self.log.error(f"[PROCESSOR] {error_msg}")
        return ProcessResult(
            success=False,
            error=str(error),
            message=error_msg
        )
