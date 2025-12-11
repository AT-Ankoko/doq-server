# Frontend Quick Start Guide

이 문서는 프론트엔드 개발자가 백엔드 API와 연동하기 위한 필수 정보를 요약합니다.

## 1. 서버 정보

- **Local**: `http://localhost:9571`
- **Production**: (TBD)

## 2. API 엔드포인트 요약

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/v1/basic/ping` | 서버 상태 확인 (Health Check) |
| `POST` | `/v1/session/connect` | 세션 생성 및 SID 발급 |
| `WS` | `/v1/session/chat` | 실시간 채팅 (WebSocket) |
| `GET` | `/v1/archive/sessions` | 전체 세션 목록 조회 |
| `GET` | `/v1/archive/session/{sid}` | 특정 세션 상세 및 채팅 이력 조회 |

---

## 3. 상세 가이드

### 3.1. 세션 생성 (로그인/입장)

채팅을 시작하기 전에 먼저 세션 ID(`sid`)를 발급받아야 합니다.

- **URL**: `POST /v1/session/connect`
- **Request Body**:
  ```json
  {
    "userId": "user123",          // (필수) 사용자 고유 ID
    "client_name": "홍길동",      // (선택) 의뢰인 이름
    "provider_name": "김철수",    // (선택) 용역자 이름
    "contract_date": "2025-12-11" // (선택) 계약 날짜
  }
  ```
- **Response**:
  ```json
  {
    "sid": "s0dc6e3dc88" // 발급된 세션 ID
  }
  ```

### 3.2. 채팅 연결 (WebSocket)

발급받은 `sid`를 사용하여 WebSocket을 연결합니다.

- **URL**: `ws://localhost:9571/v1/session/chat?sid={sid}`
- **Query Params**:
  - `sid`: (필수) 세션 ID

#### 메시지 전송 포맷 (Client -> Server)

```json
{
  "hd": {
    "sid": "s0dc6e3dc88",
    "event": "llm.invoke",    // 고정
    "role": "client",         // "client"(의뢰인) 또는 "provider"(용역자)
    "user_name": "홍길동",    // 현재 발화자 이름
    "contract_date": "..."    // (선택)
  },
  "bd": {
    "text": "안녕하세요, 계약서 작성을 시작하고 싶습니다."
  }
}
```

#### 메시지 수신 포맷 (Server -> Client)

**1. AI 응답 (LLM Response)**
```json
{
  "hd": {
    "sid": "s0dc6e3dc88",
    "event": "llm.response",
    "role": "assistant",
    "step": "introduction" // 현재 진행 단계
  },
  "bd": {
    "text": "네, 반갑습니다. 어떤 계약을 진행하시나요?",
    "contract_draft": "...", // (선택) 생성된 계약서 초안
    "current_step": "introduction",
    "progress_percentage": 10.0,
    "state": "SUCCESS"
  }
}
```

**2. 상대방 메시지 (Broadcast)**
```json
{
  "hd": {
    "sid": "s0dc6e3dc88",
    "event": "chat.message",
    "role": "provider",
    "user_name": "김철수"
  },
  "bd": {
    "text": "안녕하세요."
  }
}
```

### 3.3. 아카이브 (이력 조회)

**세션 목록 조회**
- **URL**: `GET /v1/archive/sessions`
- **Response**:
  ```json
  {
    "state": "SUCCESS",
    "data": [
      {
        "sid": "s0dc6e3dc88",
        "current_step": "work_scope",
        "updated_at": "2025-12-11T10:00:00",
        "progress": 20.0
      }
    ]
  }
  ```

**세션 상세 조회**
- **URL**: `GET /v1/archive/session/{sid}`
- **Response**:
  ```json
  {
    "state": "SUCCESS",
    "data": {
      "state": { ... },       // 세션 상태 정보 (수집된 데이터 등)
      "chat_history": [ ... ] // 채팅 메시지 이력
    }
  }
  ```
