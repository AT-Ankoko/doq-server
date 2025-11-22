# 🎯 WebSocket 채팅 아키텍처 완성 가이드

## 📌 프로젝트 현황

### ✅ 완료된 작업

1. **WebSocket 엔드포인트 구현**
   - `/v1/session/chat?sid=SESSION_ID` 실제 작동
   - 다중 클라이언트 동시 연결 지원
   - 세션별 메시지 격리

2. **3-참여자 채팅 아키텍처**
   - User A, User B, LLM 역할 구분
   - 메시지 헤더에서 `hd.role` 필드로 참여자 식별
   - Redis Stream에 participant 태깅으로 저장

3. **깨끗한 관심사 분리**
   - **websocket_handler.py**: 순수 메시지 중계 + 역할 추출 + Redis 저장
   - **chat_ws.py**: LLM 로직 담당 (현재 placeholder)
   - **ws_processor.py**: 이벤트 디스패치
   - **chat_stream_utils.py**: Redis Stream 지속성

4. **메시지 형식 표준화**
   ```json
   {
     "hd": {"event": "chat.message", "role": "A"},
     "bd": {"text": "..."}
   }
   ```

5. **테스트 체계 완성**
   - Python 자동 테스트 (`test_websocket_chat.py`)
   - Redis 메시지 검증 (`check_redis_chat.py`)
   - Postman 수동 테스트 가이드
   - 다양한 메시지 예제

---

## 🚀 빠른 시작

### 1단계: 환경 준비 (1분)

```bash
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate
pip install websockets redis  # 만약 없으면
```

### 2단계: 3개 터미널 열기 (3분)

**터미널 1 - Redis:**
```bash
redis-server
# Expected: "Ready to accept connections"
```

**터미널 2 - 서버:**
```bash
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate
python src/doq_be.py
# Expected: "[INFO] Uvicorn running on http://localhost:3000"
```

**터미널 3 - 테스트:**
```bash
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate
python test/test_websocket_chat.py
# Expected: "Chat test completed successfully"
```

### 3단계: 결과 확인 (1분)

**터미널 4:**
```bash
cd /Users/eunbee/Documents/GitHub/doq-server
python test/check_redis_chat.py test_room_001
```

**예상 출력:**
```
총 4개의 메시지 발견

--- 메시지 #1 ---
ID: 1700641234567-0
참여자: A
내용: {"hd": {...}, "bd": {"text": "..."}}

--- 메시지 #2 ---
ID: 1700641234568-0
참여자: B
내용: ...

참여자별 메시지 수:
  A: 2개
  B: 2개
```

---

## 🧪 테스트 방법 선택

| 방법 | 난이도 | 속도 | 추천 상황 |
|------|--------|------|---------|
| Python 자동 테스트 | ⭐⭐ | ⚡ 빠름 | CI/CD, 자동화 |
| Postman 수동 테스트 | ⭐⭐⭐ | 보통 | 수동 검증, 디버깅 |
| cURL/websocat | ⭐⭐⭐⭐ | 느림 | 고급 테스트 |

### Python 테스트 (권장)

```bash
# 5개의 자동 메시지 교환
python test/test_websocket_chat.py
```

**특징:**
- ✓ 재현 가능
- ✓ 빠른 실행
- ✓ CI/CD 통합 가능
- ✓ 타임아웃 처리됨

---

### Postman 테스트 (상세 디버깅)

**설정:**
1. Postman 9.0+ 다운로드
2. WebSocket 요청 생성
3. URL: `ws://localhost:3000/v1/session/chat?sid=room001`
4. Connect 버튼 클릭

**메시지 전송:**
```json
{
  "hd": {"event": "chat.message", "role": "A"},
  "bd": {"text": "안녕하세요!"}
}
```

**장점:**
- ✓ 시각적 UI
- ✓ 상세 디버깅 정보
- ✓ 복잡한 시나리오 테스트
- ✓ 실시간 메시지 검사

**자세한 가이드:**
- `test/POSTMAN_GUIDE.md` (단계별 설명)
- `test/POSTMAN_EXAMPLES.md` (10개 예제)

---

## 📋 메시지 포맷 레퍼런스

### 기본 채팅

```json
{
  "hd": {
    "event": "chat.message",
    "role": "A"
  },
  "bd": {
    "text": "메시지 내용"
  }
}
```

### 타임스탐프 포함

```json
{
  "hd": {
    "event": "chat.message",
    "role": "B",
    "timestamp": "2025-11-22T15:30:00Z"
  },
  "bd": {
    "text": "메시지"
  }
}
```

### 참여자 역할 (role 값)

| 역할 | 설명 | 예제 |
|------|------|------|
| `A` | 사용자 A | `"role": "A"` |
| `B` | 사용자 B | `"role": "B"` |
| `llm` | LLM 모델 | `"role": "llm"` |
| `user` | 기본값 (role 없을 때) | |

---

## 🏗️ 아키텍처 다이어그램

### 메시지 흐름

```
┌──────────┐
│ Client A │ ("role": "A")
└─────┬────┘
      │ WebSocket msg
      │
┌─────▼──────────────────────────────────┐
│ websocket_handler.receive_and_respond() │
├──────────────────────────────────────────┤
│ 1. JSON 파싱                            │
│ 2. role 추출: msg["hd"]["role"] → "A"  │
│ 3. Redis 저장: participant="A"         │
│ 4. Processor 호출 (이벤트 디스패치)    │
└─────┬──────────────────────┬────────────┘
      │                      │
      │                      └─→ Redis Stream
      │                          key: chat:session:room001
      │                          val: {participant:"A", body:...}
      │
┌─────▼────────────────────┐
│ ws_processor             │
├────────────────────────────┤
│ 이벤트 맵 조회             │
│ event == "chat.message"?  │
│ → 연결된 모든 클라이언트에 │
│   메시지 브로드캐스트      │
└─────┬────────────────────┘
      │
      ├──────────────────┬──────────────┐
      │                  │              │
┌─────▼─────┐   ┌───────▼────┐   ┌────▼─────┐
│ Client A  │   │ Client B   │   │ Others   │
│(수신)     │   │(수신)      │   │(수신)    │
└───────────┘   └────────────┘   └──────────┘
```

### Redis Stream 데이터

```
Key: chat:session:room001

Message 1: ID=1700641234567-0
{
  "participant": "A",
  "body": "{\"hd\": {...}, \"bd\": {\"text\": \"...\"}}"
}

Message 2: ID=1700641234568-0
{
  "participant": "B",
  "body": "{\"hd\": {...}, \"bd\": {\"text\": \"...\"}}"
}
```

---

## 🔧 코드 위치 맵

| 기능 | 파일 | 함수 |
|------|------|------|
| WebSocket 연결 처리 | `src/handler/websocket_handler.py` | `connect()` |
| 메시지 수신 및 중계 | `src/handler/websocket_handler.py` | `receive_and_respond()` |
| 엔드포인트 | `src/service/ai/chat_ws.py` | `websocket_chat()` |
| LLM 호출 (placeholder) | `src/service/ai/chat_ws.py` | `handle_llm_invocation()` |
| 이벤트 디스패치 | `src/service/messaging/ws_processor.py` | `processor()` |
| Redis 저장 | `src/utils/chat_stream_utils.py` | `store_chat_message()` |
| 자동 테스트 | `test/test_websocket_chat.py` | `main()` |
| Redis 검증 | `test/check_redis_chat.py` | `check_chat_stream()` |

---

## 🎓 학습 경로

### 초급 (5분)

1. `TEST_README.md` 읽기
2. Python 테스트 실행
3. Redis 메시지 확인

### 중급 (15분)

1. `POSTMAN_GUIDE.md` 읽기
2. Postman으로 메시지 전송
3. 메시지 포맷 변경해보기
4. 서버 로그 확인

### 고급 (30분)

1. `websocket_handler.py` 코드 분석
2. `chat_ws.py`의 LLM 구현 계획
3. 다양한 세션 ID로 테스트
4. Redis Stream 직접 쿼리

---

## 🚧 다음 단계

### Phase 1: LLM 실제 연동 (예정)

```python
# src/service/ai/chat_ws.py의 handle_llm_invocation() 구현
async def handle_llm_invocation(ctx, sid, participant, msg):
    # 1. Gemini API 호출
    response = await ctx.llm_manager['default'].generate(
        prompt=msg["bd"]["prompt"]
    )
    
    # 2. Redis에 LLM 응답 저장
    llm_response = {
        "hd": {"event": "llm.response", "role": "llm"},
        "bd": {"text": response}
    }
    await store_chat_message(ctx, sid, "llm", llm_response)
    
    # 3. WebSocket으로 전송
    return llm_response
```

### Phase 2: 스트리밍 응답

- LLM 부분 결과 실시간 전송 (토큰 단위)
- WebSocket으로 `llm.streaming` 이벤트 전송

### Phase 3: 채팅 히스토리 API

```python
@router.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    # Redis Stream에서 모든 메시지 조회
    # 참여자별로 정렬
    # 클라이언트에 반환
```

### Phase 4: 메시지 검증 & 보안

- 메시지 형식 검증 (Pydantic)
- 인증/인가
- 메시지 필터링
- Rate limiting

---

## 📞 문제 해결

### Q1: "Connection refused" 에러

```bash
# 서버 실행 확인
lsof -i :3000

# 포트 사용 중인 프로세스 종료
lsof -ti :3000 | xargs kill -9

# 서버 다시 시작
python src/doq_be.py
```

### Q2: "Redis connection error"

```bash
# Redis 실행 확인
redis-cli ping
# Expected: PONG

# Redis 없으면 시작
redis-server
```

### Q3: "No messages in stream"

1. 테스트 실행 확인: `python test/test_websocket_chat.py`
2. 세션 ID 일치 확인: `test_room_001`
3. Redis 전체 키 확인: `redis-cli KEYS "*"`

### Q4: 메시지 수신 안 됨

```json
// ✅ 올바른 형식
{
  "hd": {"event": "chat.message", "role": "A"},
  "bd": {"text": "메시지"}
}

// ❌ 틀린 형식 (role 없음)
{
  "hd": {"event": "chat.message"},
  "bd": {"text": "메시지"}
}
```

### Q5: 특수문자 깨짐

```json
// ✅ UTF-8 사용
{"text": "한글, 日本語, 中文"}

// ✅ 이모지도 지원
{"text": "반갑습니다! 😊"}
```

---

## 📚 참고 문서

| 문서 | 용도 |
|------|------|
| `TEST_README.md` | 이 문서 (전체 개요) |
| `test/QUICK_START.md` | 5분 빠른 시작 |
| `test/TEST_GUIDE.md` | 상세 테스트 가이드 |
| `test/POSTMAN_GUIDE.md` | Postman UI 단계별 설명 |
| `test/POSTMAN_EXAMPLES.md` | 10개 메시지 예제 |
| `src/handler/websocket_handler.py` | WebSocket 구현 |
| `src/service/ai/chat_ws.py` | 엔드포인트 구현 |

---

## ✨ 완성도 체크리스트

- [x] WebSocket 엔드포인트 구현
- [x] 다중 참여자 채팅
- [x] Redis Stream 저장
- [x] 깨끗한 아키텍처
- [x] Python 자동 테스트
- [x] Postman 수동 테스트 가이드
- [x] 메시지 예제
- [x] 문제 해결 가이드
- [ ] LLM 실제 연동 (다음 Phase)
- [ ] 스트리밍 응답 (다음 Phase)
- [ ] 채팅 히스토리 API (다음 Phase)

---

## 🎉 축하합니다!

WebSocket 기반 3-참여자 채팅 시스템이 완성되었습니다.

**현재 상태:** ✅ 프로덕션 테스트 준비 완료

**다음 단계:** LLM 실제 연동 (Phase 1)

**시작하기:**
```bash
# Python 테스트 (권장)
python test/test_websocket_chat.py

# 또는 Postman으로 수동 테스트
# test/POSTMAN_GUIDE.md 참고
```

---

**작성일:** 2025-11-22  
**버전:** 1.0  
**상태:** ✅ 완성
