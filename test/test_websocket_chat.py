#!/usr/bin/env python3
"""
WebSocket Chat 테스트 스크립트
3명의 참여자(A, B, llm)가 채팅하는 시뮬레이션

사용법:
    python test/test_websocket_chat.py
    또는 test 디렉토리에서: python test_websocket_chat.py
"""

import asyncio
import websockets
import json
import time
from datetime import datetime

# 서버 설정
SERVER_URL = "ws://localhost:9751"
CHAT_ENDPOINT = "/v1/session/chat"
SESSION_ID = "test_room_001"

async def send_message(websocket, role: str, event: str, text: str = None, prompt: str = None):
    """메시지를 WebSocket으로 전송"""
    msg = {
        "hd": {
            "event": event,
            "role": role,
            "timestamp": datetime.now().isoformat()
        },
        "bd": {}
    }
    
    if text:
        msg["bd"]["text"] = text
    if prompt:
        msg["bd"]["prompt"] = prompt
    
    msg_json = json.dumps(msg, ensure_ascii=False)
    await websocket.send(msg_json)
    print(f"[{role}] 전송: {event} - {msg_json[:100]}")
    return msg

async def receive_message(websocket, role: str):
    """WebSocket에서 메시지 수신"""
    try:
        msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(msg)
        print(f"[{role}] 수신: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return data
    except asyncio.TimeoutError:
        print(f"[{role}] 타임아웃 (응답 없음)")
        return None
    except Exception as e:
        print(f"[{role}] 수신 오류: {e}")
        return None

async def client_A():
    """클라이언트 A: 사용자"""
    uri = f"{SERVER_URL}{CHAT_ENDPOINT}?sid={SESSION_ID}"
    async with websockets.connect(uri) as ws:
        print("\n=== 클라이언트 A 연결됨 ===\n")
        
        # 1. 인사말 전송 (participant = A)
        await send_message(ws, "A", "chat.message", text="안녕하세요! 저는 A입니다.")
        await asyncio.sleep(0.5)
        
        # 2. 응답 수신
        print("\n[A] 응답 수신 중...\n")
        resp = await receive_message(ws, "A")
        await asyncio.sleep(0.5)

async def client_B():
    """클라이언트 B: 다른 사용자"""
    await asyncio.sleep(0.5)  # A가 먼저 시작하도록
    
    uri = f"{SERVER_URL}{CHAT_ENDPOINT}?sid={SESSION_ID}"
    async with websockets.connect(uri) as ws:
        print("\n=== 클라이언트 B 연결됨 ===\n")
        
        # 1. A의 메시지 받기
        resp = await receive_message(ws, "B")
        await asyncio.sleep(0.5)
        
        # 2. 응답 전송 (participant = B)
        await send_message(ws, "B", "chat.message", text="안녕하세요! 저는 B입니다.")
        await asyncio.sleep(0.5)

async def main():
    """메인 테스트 실행"""
    print("=" * 70)
    print("WebSocket Chat 테스트 시작")
    print("=" * 70)
    print(f"\n서버: {SERVER_URL}")
    print(f"세션: {SESSION_ID}")
    print(f"시간: {datetime.now()}\n")
    
    try:
        # A와 B를 동시에 실행
        await asyncio.gather(
            client_A(),
            client_B()
        )
        
        print("\n" + "=" * 70)
        print("✓ 테스트 완료")
        print("=" * 70)
        print("\n✓ Redis 저장 확인:")
        print(f"  python test/check_redis_chat.py {SESSION_ID}")
        print()
        
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
