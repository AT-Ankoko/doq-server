import asyncio
import websockets
import json
from datetime import datetime
import random
import string

SERVER_URL = "ws://localhost:9571"
CHAT_ENDPOINT = "/v1/session/chat"

# Generate a random session ID to ensure fresh state
random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
SESSION_ID = f"full_scenario_test_{random_suffix}"

# Participants
CLIENT_NAME = "고예경"
PROVIDER_NAME = "김영지"

async def send_message(websocket, role: str, text: str):
    msg = {
        "hd": {
            "event": "chat.message",
            "role": role,
            "timestamp": datetime.now().isoformat()
        },
        "bd": {"text": text}
    }
    await websocket.send(json.dumps(msg, ensure_ascii=False))
    print(f"\n[{role}]: {text}")
    await asyncio.sleep(0.5) # Simulate typing delay

async def trigger_llm(websocket, role="client"):
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

async def main():
    # Connect with query params for names
    uri = f"{SERVER_URL}{CHAT_ENDPOINT}?sid={SESSION_ID}&client_name={CLIENT_NAME}&provider_name={PROVIDER_NAME}"
    print(f"Connecting to {uri}")
    
    async with websockets.connect(uri) as ws:
        # 1. Initial Greeting (Automatic)
        await receive_response(ws)
        
        # 2. Work Scope
        print("\n=== Step 1: Work Scope ===")
        await send_message(ws, "client", "로고 디자인을 의뢰하고 싶습니다.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        await send_message(ws, "provider", "네, 가능합니다. 로고 스타일이나 레퍼런스가 있으신가요?")
        await trigger_llm(ws, "provider")
        await receive_response(ws)

        # 3. Work Period
        print("\n=== Step 2: Work Period ===")
        await send_message(ws, "client", "작업 기간은 2주 정도로 생각하고 있습니다.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        await send_message(ws, "provider", "2주면 충분합니다. 시작일은 계약 체결 직후로 할까요?")
        await trigger_llm(ws, "provider")
        await receive_response(ws)

        # 4. Budget (Conflict)
        print("\n=== Step 3: Budget (Conflict) ===")
        await send_message(ws, "client", "예산은 100만원입니다.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        await send_message(ws, "provider", "보통 이 정도 작업이면 150만원은 받아야 합니다.")
        await trigger_llm(ws, "provider")
        await receive_response(ws)
        
        # Mediator should intervene here
        
        await send_message(ws, "client", "그럼 130만원으로 하시죠.")
        await send_message(ws, "provider", "알겠습니다. 130만원에 진행하겠습니다.")
        await trigger_llm(ws, "provider")
        await receive_response(ws)

        # 5. Revisions
        print("\n=== Step 4: Revisions ===")
        await send_message(ws, "client", "수정은 무제한으로 해주세요.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        await send_message(ws, "provider", "무제한은 어렵고, 3회까지 무료로 해드리겠습니다.")
        await trigger_llm(ws, "provider")
        await receive_response(ws)

        await send_message(ws, "client", "네 알겠습니다. 3회로 하죠.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        # 6. Copyright
        print("\n=== Step 5: Copyright ===")
        await send_message(ws, "client", "저작권은 제가 가집니다.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        await send_message(ws, "provider", "네 동의합니다. 포트폴리오 사용은 가능하게 해주세요.")
        await trigger_llm(ws, "provider")
        await receive_response(ws)

        # 7. Confidentiality
        print("\n=== Step 6: Confidentiality ===")
        await send_message(ws, "client", "비밀 유지 서약도 필요합니다.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        await send_message(ws, "provider", "네 알겠습니다.")
        await trigger_llm(ws, "provider")
        await receive_response(ws)

        # 8. Finalization
        print("\n=== Step 7: Finalization ===")
        await send_message(ws, "client", "이제 계약서 작성해주세요.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

        await send_message(ws, "client", "특별한 내용은 없습니다. 표준 조항으로 해주세요.")
        await trigger_llm(ws, "client")
        await receive_response(ws)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")
