# 🚀 WebSocket 채팅 테스트 - 빠른 시작 (5분)

## 1단계: 준비 (1분)

### Redis 실행
```bash
redis-server
```

터미널을 열어서 위 명령 실행 후, 다른 터미널에서 진행하세요.

### 필요한 패키지 설치
```bash
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate

# websockets 패키지 확인
pip install websockets
```

---

## 2단계: 서버 시작 (1분)

**터미널 A (서버):**

```bash
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate
python src/doq_be.py
```

✓ 이 메시지가 나오면 성공:
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:3000
```

---

## 3단계: 자동 테스트 실행 (2분)

**터미널 B (테스트):**

```bash
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate
python test/test_websocket_chat.py
```

**예상 출력:**
```
============================================================
WebSocket Chat 테스트 시작
============================================================

=== 클라이언트 A 연결됨 ===
[A] 전송: chat.message - {"hd": {"event": "chat.message", "role": "A"}, "bd": {"text": "안녕하세요! 저는 A입니다."}}

=== 클라이언트 B 연결됨 ===
[B] 수신: {"hd": {"event": "chat.message", ...}, "sid": "test_room_001", "participant": "A", ...}
[B] 전송: chat.message - ...
[A] 수신: {"hd": {"event": "chat.message", ...}, "sid": "test_room_001", "participant": "B", ...}

[A] 전송: llm.invoke - {"hd": {"event": "llm.invoke", "role": "llm"}, ...}
[A] 수신: {"hd": {"event": "llm.log"}, ...}

============================================================
테스트 완료
============================================================
```

✓ 성공! A와 B가 채팅하고 LLM 호출이 기록되었습니다.

---

## 4단계: Redis 저장 확인 (1분)

**터미널 C (Redis 확인):**

```bash
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate
python test/check_redis_chat.py test_room_001
```

**예상 출력:**
```
================================================================================
Redis Stream 채팅 확인: chat:session:test_room_001
================================================================================

✓ 총 4개의 메시지 발견

--- 메시지 #1 ---
ID: 1700641234567-0
참여자: A
내용: 
{
  "hd": {
    "event": "chat.message",
    "role": "A",
    "timestamp": "2025-11-22T12:34:56.789Z"
  },
  "bd": {
    "text": "안녕하세요! 저는 A입니다."
  },
  "sid": "test_room_001",
  "participant": "A"
}

--- 메시지 #2 ---
ID: 1700641234568-0
참여자: B
...

참여자별 메시지 수:
  A: 2개
  B: 1개
  llm: 1개
================================================================================
```

✓ 모든 메시지가 Redis Stream에 저장되어 있습니다!

---

## 추가 테스트: 수동 WebSocket 연결

### wscat 설치
```bash
npm install -g wscat
```

### 수동 테스트

**터미널 D1 (클라이언트 A):**
```bash
wscat -c 'ws://localhost:3000/v1/session/chat?sid=room001'
```

**메시지 입력:**
```json
{"hd": {"event": "chat.message", "role": "A"}, "bd": {"text": "안녕!"}}
```

**터미널 D2 (클라이언트 B) - 별도 창 열기:**
```bash
wscat -c 'ws://localhost:3000/v1/session/chat?sid=room001'
```

그러면 A의 메시지를 받습니다. B도 메시지를 보낼 수 있습니다:
```json
{"hd": {"event": "chat.message", "role": "B"}, "bd": {"text": "안녕! 잘 지내?"}}
```

**LLM 호출 (D1 또는 D2에서):**
```json
{"hd": {"event": "llm.invoke", "role": "llm"}, "bd": {"prompt": "Python이란?"}}
```

✓ 응답이 나옵니다:
```json
{
  "hd": {"event": "llm.log"},
  "bd": {"text": "LLM invocation recorded (mock)."},
  "sid": "room001",
  "participant": "llm"
}
```

---

## 로그 확인

**서버 로그 보기:**
```bash
tail -f /Users/eunbee/Documents/GitHub/doq-server/logs/doq_be.log-2025-11-22
```

주요 로그 항목:
- `[WS] - Connected: ID=...` - WebSocket 연결
- `[WS] ++ Chat saved to stream` - 메시지 저장 완료
- `[WS] -- LLM invocation logged` - LLM 호출 감지

---

## 메시지 형식 참고

### 핵심 필드:
- **sid**: 세션 ID (쿼리 파라미터에서 자동 추가)
- **hd.event**: 이벤트 종류 (chat.message, llm.invoke 등)
- **hd.role**: 참여자 역할 (A, B, llm 등) ← 여기에서 participant 결정
- **bd**: 메시지 본문

### 자동 추가 필드:
- **participant**: hd.role에서 자동 추출, Redis에 태깅
- **timestamp**: 선택사항 (클라이언트가 추가 가능)

---

## 문제 해결

### "Connection refused" 오류
```bash
# 서버가 실행 중인지 확인
lsof -i :3000
ps aux | grep doq_be
```

### Redis 연결 오류
```bash
# Redis 실행 확인
redis-cli ping
# PONG이 나와야 함
```

### 메시지가 Redis에 안 나타남
```bash
# 로그 확인
tail -50 logs/doq_be.log-2025-11-22 | grep -i "redis\|error"
```

---

## 다음 단계

- [ ] LLM 실제 호출 구현 (Gemini API)
- [ ] 스트리밍 응답 (부분 응답 실시간 전송)
- [ ] 채팅 히스토리 조회 API
- [ ] 메시지 검증 및 보안

---

## 한 줄 요약

```bash
# 터미널 1: Redis
redis-server

# 터미널 2: 서버
source py_env/bin/activate && python src/doq_be.py

# 터미널 3: 테스트 (test 디렉토리에서 또는 경로 지정)
source py_env/bin/activate && python test/test_websocket_chat.py

# 터미널 4: 결과 확인
source py_env/bin/activate && python test/check_redis_chat.py test_room_001
```
