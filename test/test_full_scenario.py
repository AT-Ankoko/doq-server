import asyncio
import websockets
import json
from datetime import datetime
import random
import string

SERVER_URL = "ws://localhost:9571"
CHAT_ENDPOINT = "/api/session/chat"

SESSION_PREFIX = "full_scenario_test"

# Participants
CLIENT_NAME = "정우성"
PROVIDER_NAME = "백지오"

# 서버 스키마에 맞춘 시나리오 정의
SCENARIOS = [
    {
        "name": "SCENARIO 1 — 로고 디자인 계약",
        "steps": [
            {
                "role": "client",
                "input": "로고 디자인을 의뢰하고 싶습니다.",
                "expected_step": "work_scope",
                "expected_fields": ["category", "work_scope"],
            },
            {
                "role": "provider",
                "input": "네, 가능합니다. 혹시 원하시는 로고 스타일이나 레퍼런스가 있으신가요?",
                "expected_step": "work_scope",
                "expected_fields": [],
            },
            {
                "role": "client",
                "input": "미니멀하고 모던한 스타일을 선호합니다. 작업 기간은 2주 정도로 생각하고 있습니다.",
                "expected_step": "work_period",
                "expected_fields": ["work_period"],
            },
            {
                "role": "provider",
                "input": "2주면 충분합니다. 시작일은 계약 체결 직후로 할까요?",
                "expected_step": "work_period",
                "expected_fields": ["start_date"],
            },
            {
                "role": "client",
                "input": "네, 동의합니다. 예산은 100만원입니다.",
                "expected_step": "budget",
                "expected_fields": ["budget"],
            },
            {
                "role": "provider",
                "input": "보통 이 정도 퀄리티의 작업이면 150만원은 받아야 합니다.",
                "expected_step": "budget",
                "expected_fields": [],
            },
            {
                "role": "client",
                "input": "예산이 좀 빠듯하네요. 그럼 130만원으로 합의하시죠.",
                "expected_step": "budget",
                "expected_fields": ["budget"],
            },
            {
                "role": "client",
                "input": "감사합니다. 수정은 무제한으로 해주세요.",
                "expected_step": "revisions",
                "expected_fields": ["revision_count"],
            },
            {
                "role": "provider",
                "input": "무제한은 어렵고, 3회까지 무료로 해드리겠습니다.",
                "expected_step": "revisions",
                "expected_fields": [],
            },
            {
                "role": "client",
                "input": "네, 4회로 합의합니다. 그리고 저작권은 제가 가집니다.",
                "expected_step": "copyright",
                "expected_fields": ["revision_count", "copyright_owner"],
            },
            {
                "role": "provider",
                "input": "네 동의합니다. 대신 포트폴리오 사용은 가능하게 해주세요.",
                "expected_step": "copyright",
                "expected_fields": ["special_conditions"],
            },
            {
                "role": "client",
                "input": "네, 가능합니다. 그리고 비밀 유지 서약도 필요합니다.",
                "expected_step": "confidentiality",
                "expected_fields": ["confidentiality_terms"],
            },
            {
                "role": "provider",
                "input": "네 알겠습니다. 포함하겠습니다.",
                "expected_step": "confidentiality",
                "expected_fields": [],
            },
            {
                "role": "client",
                "input": "최종 결과물은 AI 파일과 PNG로 받고 싶습니다.",
                "expected_step": "confidentiality",
                "expected_fields": ["special_conditions"],
            },
            {
                "role": "client",
                "input": "완벽합니다. 이제 계약서 작성해주세요.",
                "expected_step": "finalization",
                "expected_fields": [],
            },
        ],
    },
    {
        "name": "SCENARIO 2 — 웹사이트 디자인 계약",
        "steps": [
            {
                "role": "client",
                "input": "기업용 웹사이트 디자인을 의뢰합니다. 총 10페이지 정도입니다.",
                "expected_step": "work_scope",
                "expected_fields": ["category", "work_scope"],
            },
            {
                "role": "provider",
                "input": "페이지 수를 확인했습니다. 작업 기간은 최소 6주는 필요합니다.",
                "expected_step": "work_period",
                "expected_fields": ["work_period"],
            },
            {
                "role": "client",
                "input": "알겠습니다. 6주로 합의하고 예산은 700만원으로 진행합시다.",
                "expected_step": "budget",
                "expected_fields": ["budget"],
            },
            {
                "role": "provider",
                "input": "네, 700만원에 진행하겠습니다. 완료 후 5개월은 무상 수정 지원해드립니다.",
                "expected_step": "revisions",
                "expected_fields": ["special_conditions"], # 무상 보수 기간 등 특약
            },
            {
                "role": "client",
                "input": "저작권은 모두 저희에게 귀속되며 비밀유지 조항도 포함해주세요.",
                "expected_step": "copyright",  # 혹은 confidentiality
                "expected_fields": ["copyright_owner", "confidentiality_terms"],
            },
            {
                "role": "client",
                "input": "그럼 계약서 작성 부탁드립니다.",
                "expected_step": "finalization",
                "expected_fields": [],
            },
        ],
    }
]

random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

async def send_message(websocket, role: str, text: str, display_name_map):
    user_name = display_name_map.get(role, role) if display_name_map else role
    
    msg = {
        "hd": {
            "event": "chat.message",
            "role": role,
            "user_name": user_name,
            "timestamp": int(datetime.now().timestamp())
        },
        "bd": {"text": text}
    }
    await websocket.send(json.dumps(msg, ensure_ascii=False))
    actor = display_name_map.get(role, role)
    print(f"\n[{actor}]: {text}")
    await asyncio.sleep(0.5)

async def trigger_llm(websocket, role="client", display_name_map=None):
    user_name = display_name_map.get(role, role) if display_name_map else role
    
    msg = {
        "hd": {
            "event": "llm.invoke",  # ChatEvent.LLM_INVOKE 반영
            "role": role,
            "asker": role,
            "user_name": user_name,
            "timestamp": int(datetime.now().timestamp())
        },
        "bd": {"text": ""}
    }
    await websocket.send(json.dumps(msg, ensure_ascii=False))
    
    actor = display_name_map.get(role, role) if display_name_map else role
    print(f"(System): {actor} → DoQ(LLM) 응답 요청")

async def receive_response(websocket):
    print("(System): Waiting for DoQ...")
    while True:
        try:
            msg = await asyncio.wait_for(websocket.recv(), timeout=60.0)
            data = json.loads(msg)
            
            event = data.get("hd", {}).get("event")
            
            if event == "llm.response": # ChatEvent.LLM_RESPONSE 반영
                bd = data.get("bd", {})
                text = bd.get("text", "")
                print(f"\n[DoQ]: \n{text}\n")
                
                return bd
                
            elif event == "chat.message":
                pass
            elif event == "typing":
                pass
                
        except asyncio.TimeoutError:
            print("(System): Timeout waiting for response.")
            return None

def build_session_id(idx: int) -> str:
    return f"{SESSION_PREFIX}_{idx+1}_{random_suffix}"

async def run_scenario(idx: int, scenario: dict):
    session_id = build_session_id(idx)
    display_name_map = {"client": CLIENT_NAME, "provider": PROVIDER_NAME}
    
    # URL 쿼리 파라미터는 실제 서버 라우터 설정에 맞게 조정하세요
    uri = f"{SERVER_URL}{CHAT_ENDPOINT}?sid={session_id}&client_name={CLIENT_NAME}&provider_name={PROVIDER_NAME}"

    print(f"\n{'='*50}")
    print(f"🚀 Running {scenario['name']} (session: {session_id})")
    print(f"{'='*50}")

    async with websockets.connect(uri) as ws:
        # 최초 연결 후 초기 메시지가 있다면 수신 (서버 구현에 따라 스킵 가능)
        # await receive_response(ws) 

        for step_idx, step_data in enumerate(scenario.get("steps", []), start=1):
            role = step_data["role"]
            text = step_data["input"]
            expected_step = step_data.get("expected_step")
            expected_fields = step_data.get("expected_fields", [])
            
            print(f"\n--- Step {step_idx} ---")
            
            display_text = text.replace("{CLIENT_NAME}", CLIENT_NAME).replace("{PROVIDER_NAME}", PROVIDER_NAME)
            await send_message(ws, role, display_text, display_name_map)
            await trigger_llm(ws, role, display_name_map)
            
            bd_data = await receive_response(ws)
            
            if bd_data:
                # 서버에서 내려주는 실제 키값에 맞춰 아래 변수들을 매핑하세요
                actual_step = bd_data.get("current_step", "UNKNOWN")
                
                # 수집된 데이터 전체 딕셔너리에서 값이 null(None)이 아닌 키만 추출
                collected_data_dict = bd_data.get("collected_data", {})
                actual_fields = [k for k, v in collected_data_dict.items() if v is not None]
                
                print(f"[Verification] Step {step_idx}")
                
                # 1. State 검증
                if expected_step:
                    step_match = (actual_step == expected_step)
                    mark = "✅" if step_match else "❌"
                    print(f" {mark} State: Expected='{expected_step}' | Actual='{actual_step}'")

                # 2. 추출 필드 검증
                if expected_fields:
                    missing_fields = set(expected_fields) - set(actual_fields)
                    mark = "✅" if not missing_fields else "❌"
                    print(f" {mark} Fields: Expected to be filled={expected_fields}")
                    if missing_fields:
                        print(f"    -> ⚠️ Missing (still None): {list(missing_fields)}")
                    # CI 파이프라인에서 실패를 강제하려면 assert 사용
                    # assert not missing_fields, f"Failed to extract fields: {missing_fields}"

    print(f"\n===== {scenario['name']} completed =====\n")

async def main():
    for idx, scenario in enumerate(SCENARIOS):
        try:
            await run_scenario(idx, scenario)
        except Exception as exc:
            print(f"[Error] Scenario '{scenario['name']}' failed: {exc}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")