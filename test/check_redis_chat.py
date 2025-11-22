#!/usr/bin/env python3
"""
Redis Stream 채팅 메시지 확인 스크립트

사용법:
    python test/check_redis_chat.py <SESSION_ID>
    python check_redis_chat.py test_room_001
    또는 test 디렉토리에서: python check_redis_chat.py test_room_001
"""

import asyncio
import redis.asyncio as redis
import json
import sys
from datetime import datetime

async def check_chat_stream(session_id: str, redis_host: str = "localhost", redis_port: int = 6379):
    """Redis Stream에 저장된 채팅 메시지 조회"""
    
    client = await redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
    
    try:
        stream_key = f"chat:session:{session_id}"
        
        print("=" * 80)
        print(f"Redis Stream 채팅 확인: {stream_key}")
        print("=" * 80)
        print()
        
        # 모든 메시지 읽기
        entries = await client.xread({stream_key: "0"})
        
        if not entries:
            print(f"❌ 스트림이 비어있거나 존재하지 않습니다: {stream_key}")
            return
        
        key, messages = entries[0]
        print(f"✓ 총 {len(messages)}개의 메시지 발견\n")
        
        for idx, (msg_id, data) in enumerate(messages, 1):
            print(f"--- 메시지 #{idx} ---")
            print(f"ID: {msg_id}")
            
            # participant와 body 추출
            participant = data.get("participant", "unknown")
            body_str = data.get("body", "{}")
            
            print(f"참여자: {participant}")
            
            # body JSON 파싱
            try:
                body = json.loads(body_str)
                print(f"내용: {json.dumps(body, ensure_ascii=False, indent=2)}")
            except json.JSONDecodeError:
                print(f"내용 (원본): {body_str}")
            
            print()
        
        # 요약
        print("=" * 80)
        print("참여자별 메시지 수:")
        participant_count = {}
        for msg_id, data in messages:
            participant = data.get("participant", "unknown")
            participant_count[participant] = participant_count.get(participant, 0) + 1
        
        for participant, count in sorted(participant_count.items()):
            print(f"  {participant}: {count}개")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

def main():
    if len(sys.argv) < 2:
        print("사용법: python check_redis_chat.py <SESSION_ID>")
        print("예제: python check_redis_chat.py test_room_001")
        sys.exit(1)
    
    session_id = sys.argv[1]
    asyncio.run(check_chat_stream(session_id))

if __name__ == "__main__":
    main()
