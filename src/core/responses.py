import time
from enum import Enum
from fastapi import status as http_status # FastAPI 표준 코드 사용
from fastapi.encoders import jsonable_encoder

class ResponseStatus(Enum):
    # --- Success (2xx) ---
    SUCCESS            = (http_status.HTTP_200_OK,                  "S0000", "성공")
    CREATED            = (http_status.HTTP_201_CREATED,             "S0001", "리소스가 생성되었습니다")
    ACCEPTED           = (http_status.HTTP_202_ACCEPTED,            "S0002", "요청이 접수되었습니다")

    # --- Client Errors (4xx) ---
    BAD_REQUEST        = (http_status.HTTP_400_BAD_REQUEST,         "E0001", "잘못된 요청입니다")
    UNAUTHORIZED       = (http_status.HTTP_401_UNAUTHORIZED,        "E0002", "인증이 필요합니다")
    FORBIDDEN          = (http_status.HTTP_403_FORBIDDEN,           "E0003", "접근이 거부되었습니다")
    NOT_FOUND          = (http_status.HTTP_404_NOT_FOUND,           "E0004", "리소스를 찾을 수 없습니다")
    METHOD_NOT_ALLOWED = (http_status.HTTP_405_METHOD_NOT_ALLOWED,  "E0005", "허용되지 않은 메서드입니다")
    CONFLICT           = (http_status.HTTP_409_CONFLICT,            "E0006", "이미 존재하는 리소스입니다")
    GONE               = (http_status.HTTP_410_GONE,                "E0007", "삭제된 리소스입니다")
    PAYLOAD_TOO_LARGE  = (http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "E0008", "요청 데이터가 너무 큽니다")
    TIMEOUT            = (http_status.HTTP_408_REQUEST_TIMEOUT,     "E0009", "응답 시간이 초과되었습니다")
    UNPROCESSABLE      = (http_status.HTTP_422_UNPROCESSABLE_ENTITY, "E0010", "유효성 검사에 실패했습니다")
    TOO_MANY_REQUESTS  = (http_status.HTTP_429_TOO_MANY_REQUESTS,   "E0029", "너무 많은 요청이 발생했습니다")

    # --- Server Errors (5xx) ---
    SERVER_ERROR       = (http_status.HTTP_500_INTERNAL_SERVER_ERROR, "E0500", "서버 내부 오류가 발생했습니다")
    NOT_IMPLEMENTED    = (http_status.HTTP_501_NOT_IMPLEMENTED,      "E0501", "구현되지 않은 기능입니다")
    BAD_GATEWAY        = (http_status.HTTP_502_BAD_GATEWAY,          "E0502", "게이트웨이 오류가 발생했습니다")
    SERVICE_UNAVAILABLE = (http_status.HTTP_503_SERVICE_UNAVAILABLE, "E0503", "서비스를 일시적으로 사용할 수 없습니다")

    def __init__(self, http_code: int, code: str, msg: str):
        """생성 시점에 info 딕셔너리를 미리 캐싱 (성능 최적화)"""
        self.http_code = http_code
        self.info = {
            # "http_status": http_code,
            "code": code,
            "msg": msg
        }

    @classmethod
    def from_http_code(cls, http_code: int):
        """HTTP 상태 코드로 해당 Enum 멤버를 찾거나 기본 에러 반환"""
        return next((s for s in cls if s.http_code == http_code), cls.SERVER_ERROR)

def build_response_body(status: ResponseStatus, data=None):
    return {
        "tid": int(time.time() * 1000),
        "status": status.info, # 여기서 http_status, code, msg가 한 번에 나감
        "data": jsonable_encoder(data) if data is not None else {},
    }

def build_success_response(data):
    """성공 응답 전용 헬퍼"""
    return build_response_body(ResponseStatus.SUCCESS, data)

def build_error_response(http_code: int, data=None):
    """에러 응답 전용 헬퍼"""
    status_obj = ResponseStatus.from_http_code(http_code)
    return build_response_body(status_obj, data)
