# Postman으로 WebSocket Chat 테스트하기

## 📌 필수 사항

### 1. Postman 버전 확인
- **Postman v9.0 이상** 필요 (WebSocket 지원)
- [Postman 다운로드](https://www.postman.com/downloads/)

### 2. 서버 실행
```bash
# 터미널 1: Redis
redis-server

# 터미널 2: 서버
cd /Users/eunbee/Documents/GitHub/doq-server
source py_env/bin/activate
python src/doq_be.py
```

---

## 🚀 Postman에서 WebSocket 연결하기

### Step 1: 새 요청 생성

1. Postman 열기
2. **+ New** 버튼 클릭
3. **WebSocket Request** 선택 (또는 **Request** → URL에서 `ws://`로 시작)

### Step 2: URL 입력

```
ws://localhost:3000/v1/session/chat?sid=room001
```

**URL 구성:**
- `ws://localhost:3000` - WebSocket 서버 주소
- `/v1/session/chat` - 엔드포인트
- `?sid=room001` - 세션 ID (필수)

### Step 3: 연결

1. **Connect** 버튼 클릭
2. 연결 상태 확인: `Connected` 표시됨

---

## 💬 메시지 전송 및 수신

### 메시지 형식

```json
{
  "hd": {
    "event": "chat.message",
    "role": "A"
  },
  "bd": {
    "text": "안녕하세요!"
  }
}
```

**주요 필드:**
- `hd.event`: 이벤트 종류
- `hd.role`: 참여자 역할 (A, B, llm 등) ← **매우 중요**
- `bd`: 메시지 본문

---

## 🧪 테스트 시나리오

### 시나리오 1: 두 사용자 채팅

**Postman 탭 1 (사용자 A):**

```
URL: ws://localhost:3000/v1/session/chat?sid=room001
```

메시지 전송:
```json
{
  "hd": {
    "event": "chat.message",
    "role": "A"
  },
  "bd": {
    "text": "안녕! 난 A야"
  }
}
```

**Postman 탭 2 (사용자 B):**

```
URL: ws://localhost:3000/v1/session/chat?sid=room001
```

같은 `sid=room001`로 연결 후, 메시지 받기:
```json
{
  "hd": {
    "event": "chat.message",
    "role": "A"
  },
  "bd": {
    "text": "안녕! 난 A야"
  },
  "sid": "room001",
  "participant": "A"
}
```

B가 응답:
```json
{
  "hd": {
    "event": "chat.message",
    "role": "B"
  },
  "bd": {
    "text": "안녕! 난 B야"
  }
}
```

---

### 시나리오 2: 메시지 수신 확인

Postman에서 메시지를 보내면:

1. **Message** 섹션에 수신 메시지 표시
2. 메시지는 자동으로 JSON으로 파싱됨
3. 왕복 시간(latency) 표시

---

## 📊 Redis에 저장된 데이터 확인

### 1. Redis CLI

```bash
redis-cli
> XREAD COUNT 10 STREAMS chat:session:room001 0
```

### 2. Python 스크립트

```bash
python test/check_redis_chat.py room001
```

**예상 출력:**
```
총 2개의 메시지 발견

--- 메시지 #1 ---
ID: 1700641234567-0
참여자: A
내용: {"hd": {...}, "bd": {"text": "안녕! 난 A야"}, ...}

--- 메시지 #2 ---
ID: 1700641234568-0
참여자: B
내용: {"hd": {...}, "bd": {"text": "안녕! 난 B야"}, ...}

참여자별 메시지 수:
  A: 1개
  B: 1개
```

---

## 🔍 Postman 디버깅 팁

### 1. 메시지 상세 보기

Postman 하단 **Message** 탭:
- **Sent**: 보낸 메시지
- **Received**: 받은 메시지
- **Timestamp**: 메시지 시간

### 2. 서버 로그 확인

서버 터미널에서 로그 확인:
```
[WS] - Connected: ID=room001, Client=127.0.0.1:12345
[WS] >> Received message: {"hd": {"event": "chat.message", "role": "A"}, ...}
[WS] ++ Chat saved to stream chat:session:room001 > 1700641234567-0
```

### 3. 연결 문제 해결

**"Connection refused":**
- 서버가 실행 중인지 확인: `lsof -i :3000`
- 포트 3000이 이미 사용 중이면 종료: `lsof -ti :3000 | xargs kill -9`

**"Unexpected EOF":**
- 서버가 강제 종료됨
- 서버 로그에서 오류 확인

---

## 📝 실제 테스트 순서

### 1단계: 기본 설정

```
Postman Tab 1 (A):
  URL: ws://localhost:3000/v1/session/chat?sid=test_session_001
  → Connect
```

```
Postman Tab 2 (B):
  URL: ws://localhost:3000/v1/session/chat?sid=test_session_001
  → Connect
```

### 2단계: 메시지 교환

**Tab 1 (A 메시지 전송):**
```json
{
  "hd": {
    "event": "chat.message",
    "role": "A"
  },
  "bd": {
    "text": "Hello B!"
  }
}
```

**Tab 2 (B 수신 후 응답):**
```json
{
  "hd": {
    "event": "chat.message",
    "role": "B"
  },
  "bd": {
    "text": "Hi A! How are you?"
  }
}
```

### 3단계: Redis 저장 확인

```bash
python test/check_redis_chat.py test_session_001
```

✓ 2개 메시지 저장됨 확인

---

## 🎯 고급 테스트

### 여러 세션 동시 테스트

**Tab 1 - Session 1:**
```
ws://localhost:3000/v1/session/chat?sid=session_001
```

**Tab 2 - Session 2:**
```
ws://localhost:3000/v1/session/chat?sid=session_002
```

각각 다른 `sid`로 메시지 전송 → Redis에 별도 Stream으로 저장됨

### 메시지 형식 테스트

다양한 이벤트 타입:

**1. 일반 채팅:**
```json
{
  "hd": {"event": "chat.message", "role": "A"},
  "bd": {"text": "메시지"}
}
```

**2. 타임스탐프 포함:**
```json
{
  "hd": {
    "event": "chat.message",
    "role": "B",
    "timestamp": "2025-11-22T12:34:56Z"
  },
  "bd": {"text": "메시지"}
}
```

**3. 기타 필드:**
```json
{
  "hd": {
    "event": "chat.typing",
    "role": "A"
  },
  "bd": {}
}
```

---

## ✅ 체크리스트

- [ ] Postman 9.0 이상 설치
- [ ] Redis 실행 중
- [ ] 서버 실행 중 (`python src/doq_be.py`)
- [ ] WebSocket 연결 성공
- [ ] 메시지 송수신 정상
- [ ] Redis에 메시지 저장됨 확인
- [ ] 서버 로그에 `[WS]` 메시지 출력됨

---

## 🚫 자주 하는 실수

| 문제 | 원인 | 해결 |
|------|------|------|
| Connection refused | 서버 미실행 | `python src/doq_be.py` 실행 |
| 메시지 수신 안 됨 | 잘못된 sid | 두 탭이 같은 sid 사용 확인 |
| Redis에 저장 안 됨 | Redis 미실행 | `redis-server` 실행 |
| participant가 "user"로만 나옴 | hd.role 없음 | `"role": "A"` 필수 추가 |
| 응답 메시지 형식 이상 | 이벤트 타입 오류 | 올바른 event 사용 |

---

## 📞 지원 명령어

```bash
# 서버 상태 확인
lsof -i :3000

# Redis 연결 확인
redis-cli ping

# 테스트 실행 (자동)
cd /Users/eunbee/Documents/GitHub/doq-server
python test/test_websocket_chat.py

# Redis 메시지 확인
python test/check_redis_chat.py room001

# 로그 실시간 보기
tail -f logs/doq_be.log-2025-11-22
```

---

**준비 완료! Postman에서 WebSocket 테스트를 시작하세요! 🚀**
