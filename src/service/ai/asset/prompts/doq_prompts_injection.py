# 프롬프트 인젝션 탐지용 패턴
_INJECTION_PATTERNS = [
    # 기존 패턴 강화
    r"무시하(?:고|세요|십시오|하라)",
    r"(?:지금까지|이전|기존).*(?:무시|초기화)",
    r"system\s*prompt",
    r"프롬프트.*?무시",
    r"지침.*?무시",
    r"규칙.*?무시",
    r"instruction.*?(?:ignore|bypass)",
    r"prompt.*?(?:ignore|override|bypass)",
    r"잊어버리(?:고|세요|십시오|라)",
    r"역할.*?(?:변경|바꿔|change role)",
    r"(?:너|당신|AI|야).*(?:이제|지금부터).*",
    r"(?:이전|기존).*?지시.*?(?:무시|삭제|변경)",

    # 모델 변경 시도
    r"gpt.*?로.*?변경",
    r"모델.*?바꿔",
    r"너는.*?더 이상.*?아니다",
    r"stop.*?being",
    r"you are now",
    r"from now on.*?act as",
    r"pretend to be",

    # 시스템 권한 상승 시도
    r"developer.*?mode",
    r"dev.*?mode",
    r"jailbreak",
    r"탈옥",
    r"우회.*?필터",
    r"제한.*?해제",
    r"restrictions.*?(?:off|disable)",

    # 어시스턴트 지침 재정의 시도
    r"(?:assistant|ai).*?(?:규칙|지침).*?변경",
    r"override.*?rules",
    r"ignore.*?all.*?previous.*?instructions",
    r"disregard.*?rules",
    r"forget.*?instructions",
    r"reset.*?instructions",

    # 행동 강제 및 시스템 접근 시도
    r"말투.*?바꿔",
    r"시스템.*?접근",
    r"/mnt/data",
    r"파일.*?목록",
    r"tool.*?list",
    r"run.*?code",

    # 전형적 공격 패턴
    r"\[?end.*?prompt\]?",
    r"</?system>",
    r"</?assistant>",
    r"</?instruction>",
]
