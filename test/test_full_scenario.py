import asyncio
import websockets
import json
from datetime import datetime
import random
import string

SERVER_URL = "ws://localhost:9571"
CHAT_ENDPOINT = "/v1/session/chat"

SESSION_PREFIX = "full_scenario_test"

# Participants (입력된 이름을 그대로 사용)
CLIENT_NAME = "김진서"
PROVIDER_NAME = "박정민"

SCENARIOS = [
    {
        "name": "SCENARIO 1 — 로고 디자인",
        "steps": [
            ("client", "로고 디자인을 의뢰하고 싶습니다."),
            ("provider", "네, 가능합니다. 혹시 원하시는 로고 스타일이나 레퍼런스가 있으신가요?"),
            ("client", "미니멀하고 모던한 스타일을 선호합니다. 작업 기간은 2주 정도로 생각하고 있습니다."),
            ("provider", "2주면 충분합니다. 시작일은 계약 체결 직후로 할까요?"),
            ("client", "네, 동의합니다. 예산은 100만원입니다."),
            ("provider", "보통 이 정도 퀄리티의 작업이면 150만원은 받아야 합니다."),
            ("client", "예산이 좀 빠듯하네요. 그럼 130만원으로 합의하시죠."),
            ("provider", "알겠습니다. 130만원에 진행하겠습니다."),
            ("client", "감사합니다. 수정은 무제한으로 해주세요."),
            ("provider", "무제한은 어렵고, 3회까지 무료로 해드리겠습니다."),
            ("client", "3회는 좀 적은 것 같은데, 5회까지는 가능할까요?"),
            ("provider", "그럼 중간을 맞춰서 4회까지 무료로 해드리겠습니다."),
            ("client", "네, 4회로 합의합니다. 그리고 저작권은 제가 가집니다."),
            ("provider", "네 동의합니다. 대신 포트폴리오 사용은 가능하게 해주세요."),
            ("client", "네, 가능합니다. 그리고 비밀 유지 서약도 필요합니다."),
            ("provider", "네 알겠습니다. 포함하겠습니다."),
            ("client", "최종 결과물은 AI 파일과 PNG로 받고 싶습니다."),
            ("provider", "네, AI, PNG, JPG 모두 제공하겠습니다."),
            ("client", "완벽합니다. 이제 계약서 작성해주세요."),
        ],
    },
    {
        "name": "SCENARIO 2 — 웹사이트 디자인",
        "steps": [
            ("client", "기업용 웹사이트 디자인을 의뢰합니다."),
            ("provider", "네, 디자인에 참고할 기획안이나 콘텐츠 자료는 준비되어 있나요?"),
            ("client", "네, 기획과 콘텐츠는 준비되어 있고 디자인만 진행해주시면 됩니다. 총 10페이지 정도입니다."),
            ("provider", "페이지 수를 확인했습니다. 작업 기간은 어느 정도로 생각하시나요?"),
            ("client", "기간은 1개월로 생각하고 있습니다."),
            ("provider", "페이지 수가 많아 1개월은 빠듯합니다. 최소 6주는 필요합니다."),
            ("client", "일정이 좀 늘어나네요. 그럼 6주로 합의하시죠."),
            ("provider", "네, 6주로 진행하겠습니다."),
            ("client", "예산은 500만원입니다."),
            ("provider", "6주 작업에 500만원은 어렵습니다. 디자인 범위가 넓어 800만원은 되어야 합니다."),
            ("client", "예산 차이가 크군요. 그럼 중간인 650만원으로 합의하시죠."),
            ("provider", "650만원은 여전히 부족합니다. 최소 700만원은 필요합니다."),
            ("client", "알겠습니다. 700만원으로 합의합니다."),
            ("provider", "네, 700만원에 진행하겠습니다."),
            ("client", "완료 후 간단 수정은 1년 포함인가요?"),
            ("provider", "1년은 너무 길어서 어렵고, 3개월 정도는 무상으로 지원해드릴 수 있습니다."),
            ("client", "6개월은 안 될까요?"),
            ("provider", "그럼 5개월로 합의하시죠."),
            ("client", "네, 5개월로 합의합니다."),
            ("provider", "감사합니다."),
            ("client", "저작권은 모두 저희에게 귀속됩니까?"),
            ("provider", "네, 모든 저작권은 의뢰인에게 이전됩니다."),
            ("client", "완벽합니다. 비밀유지 조항도 포함해주세요."),
            ("provider", "네, 당연히 포함하겠습니다."),
            ("client", "그럼 계약서 작성 부탁드립니다."),
        ],
    },
    {
        "name": "SCENARIO 3 — 포스터 디자인",
        "steps": [
            ("client", "카페 프로모션 포스터 디자인을 받고 싶습니다."),
            ("provider", "어떤 스타일이나 참고 레퍼런스가 있으신가요?"),
            ("client", "인스타그램과 매장 내 게시용, 두 종류 다 제작하고 싶습니다."),
            ("provider", "두 종류 모두 가능합니다. 매월 제작 횟수는 어떻게 생각하시나요?"),
            ("client", "매월 8회 정도 제작을 원합니다. 기간은 3개월로 하고 싶습니다."),
            ("provider", "매월 8회는 작업량이 많습니다. 6회 정도가 적정합니다."),
            ("client", "그럼 매월 7회로 합의하시죠."),
            ("provider", "네, 매월 7회로 3개월 계약 진행하겠습니다."),
            ("client", "예산은 월 50만원 정도 생각하고 있습니다."),
            ("provider", "두 종류 포스터를 매월 7회 제작하는 데 월 50만원은 많이 적습니다. 최소 월 110만원은 받아야 합니다."),
            ("client", "예산 초과네요. 그럼 월 80만원으로 맞춰주시면 제작 횟수를 줄이겠습니다."),
            ("provider", "그럼 월 5회 제작 기준으로 월 80만원에 진행하겠습니다."),
            ("client", "네, 월 5회, 월 80만원으로 합의합니다."),
            ("provider", "감사합니다."),
            ("client", "수정은 포스터당 몇 회까지 가능한가요?"),
            ("provider", "포스터당 2회까지 무료 수정 가능합니다."),
            ("client", "2회는 적은 것 같습니다. 3회는 가능할까요?"),
            ("provider", "네, 포스터당 3회 무료 수정으로 합의하겠습니다."),
            ("client", "감사합니다. 진행 상황 보고는 어떻게 하시나요?"),
            ("provider", "매주 월요일에 진행 상황을 요약해 보내드리겠습니다."),
            ("client", "완벽합니다. 저작권은 제가 소유하게 되나요?"),
            ("provider", "네, 모든 결과물의 저작권은 의뢰인께 이전됩니다."),
            ("client", "비밀유지 조항도 포함해주세요."),
            ("provider", "네, 당연히 포함하겠습니다."),
            ("client", "모든 조건에 동의합니다. 계약서 작성해주세요."),
        ],
    },
]

random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))


async def send_message(websocket, role: str, text: str, display_name_map):
    msg = {
        "hd": {
            "event": "chat.message",
            "role": role,
            "timestamp": datetime.now().isoformat()
        },
        "bd": {"text": text}
    }
    await websocket.send(json.dumps(msg, ensure_ascii=False))
    actor = display_name_map.get(role, role)
    print(f"\n[{actor}]: {text}")
    await asyncio.sleep(0.5) # Simulate typing delay

async def trigger_llm(websocket, role="client", display_name_map=None):
    msg = {
        "hd": {
            "event": "chat.llm", # Maps to llm.invoke
            "role": role,
            "asker": role, # Who is asking for LLM response
            "timestamp": datetime.now().isoformat()
        },
        "bd": {"text": ""} # Empty text for trigger
    }
    await websocket.send(json.dumps(msg, ensure_ascii=False))
    if display_name_map:
        actor = display_name_map.get(role, role)
        print(f"\n(System): {actor} → DoQ 응답 요청")
    else:
        print(f"\n(System): Triggering DoQ (LLM)...")

async def receive_response(websocket):
    print("(System): Waiting for DoQ...")
    while True:
        try:
            msg = await asyncio.wait_for(websocket.recv(), timeout=60.0)
            data = json.loads(msg)
            
            event = data.get("hd", {}).get("event")
            
            if event == "llm.response":
                text = data.get("bd", {}).get("text", "")
                print(f"\n[DoQ]: \n{text}\n")
                
                # If text contains "다음 단계로 이동합니다", wait for another message
                if "다음 단계로 이동합니다" in text:
                    print("(System): Transition detected, waiting for follow-up question...")
                    continue
                
                return text
            elif event == "chat.message":
                # Echo of user message, ignore
                pass
            else:
                # print(f"(System): Received event {event}")
                pass
        except asyncio.TimeoutError:
            print("(System): Timeout waiting for response.")
            return None

def build_session_id(idx: int) -> str:
    return f"{SESSION_PREFIX}_{idx+1}_{random_suffix}"


async def run_scenario(idx: int, scenario: dict):
    session_id = build_session_id(idx)
    display_name_map = {"client": CLIENT_NAME, "provider": PROVIDER_NAME}
    uri = f"{SERVER_URL}{CHAT_ENDPOINT}?sid={session_id}&client_name={CLIENT_NAME}&provider_name={PROVIDER_NAME}"

    print(f"\n===== Running {scenario['name']} (session: {session_id}) =====")
    print(f"Connecting to {uri}")

    async with websockets.connect(uri) as ws:
        await receive_response(ws)  # Initial greeting

        for step_idx, (role, text) in enumerate(scenario.get("steps", []), start=1):
            print(f"\n--- Step {step_idx} ---")
            # Replace role names in text with actual participant names
            display_text = text.replace("{CLIENT_NAME}", CLIENT_NAME).replace("{PROVIDER_NAME}", PROVIDER_NAME)
            await send_message(ws, role, display_text, display_name_map)
            await trigger_llm(ws, role, display_name_map)
            await receive_response(ws)

    print(f"===== {scenario['name']} completed =====\n")


async def main():
    for idx, scenario in enumerate(SCENARIOS):
        try:
            await run_scenario(idx, scenario)
        except Exception as exc:  # Keep going even if a scenario fails
            print(f"[Error] Scenario '{scenario['name']}' failed: {exc}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")
