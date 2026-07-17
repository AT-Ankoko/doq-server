# TryAngle 데이터베이스 설계 명세서 (v1.4.1)

본 문서는 TryAngle 서비스의 RDBMS(PostgreSQL/MySQL 등) 스키마를 정의합니다. 이미지 분석 결과와 시스템 로그 일부는 noneSQL DB 및 Cloudflare R2에 분산 저장되며, 본 DB는 사용자, 레퍼런스 이미지, 태그, 촬영 세션, 상품, 유저 스냅 메타데이터와 이들 간의 관계를 관리합니다.

## 1. 공통 설정

* **Timestamp:** 모든 일시 컬럼은 Unix Timestamp(`bigint`)를 사용합니다.
* **Character Set:** `utf8mb4`
* **Naming Convention:**
    * 기본 테이블: `tb_{name}`
    * 매핑 테이블: `mtb_{name}`
    * 생성일/수정일: `cDate` / `uDate`
* **Role Enum:** `SUPER_ADMIN`, `ADMIN`, `CLIENT`
* **Primary Key Strategy:** 기본 PK 전략은 `BIGINT AUTO_INCREMENT`입니다. 단, `tb_session.id`는 외부 로그 매핑 키로 사용되므로 예외적으로 `VARCHAR(32)` 수동 할당 PK(`generate_sid`)를 사용합니다.
* **Status Code Convention:** 상태값은 문자열 enum 대신 정수 코드(`int`)를 사용합니다.

---

## 2. 테이블 정의

### 2.1 사용자 정보 (`tb_user`)
사용자의 계정 정보, 프로필, 권한과 활성 상태를 관리합니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 사용자 고유 식별자 |
| **email** | varchar | Unique, Not Null | 로그인 이메일 |
| **password** | varchar | - | 암호화된 비밀번호 |
| **name** | varchar | - | 실명 |
| **nickname** | varchar | - | 서비스 내 별명 |
| **phone** | varchar | - | 연락처 |
| **emailConf** | varchar | Default: "2" | 이메일 인증 여부 (`1`: 인증, `2`: 미인증) |
| **desc** | text | - | 프로필 자기소개 |
| **fileId** | varchar | - | 프로필 이미지 경로 |
| **role** | enum(user_role) | Default: "CLIENT" | 권한 (`SUPER_ADMIN`, `ADMIN`, `CLIENT`) |
| **state** | int | Default: 1 | 계정 상태 (`0: INACTIVE`, `1: ACTIVE`) |
| **extra** | json | - | 기타 부가 정보 |
| **cDate** | bigint | - | 생성일 (Unix Timestamp) |
| **uDate** | bigint | - | 수정일 (Unix Timestamp) |

### 2.2 이미지 카테고리 (`tb_img_ctg`)
레퍼런스 이미지의 상품/주제 카테고리를 관리합니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 카테고리 고유 식별자 |
| **name** | varchar | Not Null | 카테고리 명칭 |
| **cDate** | bigint | - | 생성일 (Unix Timestamp) |
| **uDate** | bigint | - | 수정일 (Unix Timestamp) |

### 2.3 레퍼런스 이미지 (`tb_img`)
시스템 가이드 및 참조 촬영용 이미지 메타데이터를 관리합니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 이미지 고유 식별자 |
| **userId** | bigint | FK (`tb_user.id`) | 등록 관리자 ID |
| **ctgId** | bigint | FK (`tb_img_ctg.id`) | 카테고리 ID |
| **imgUrl** | varchar | Not Null | 레퍼런스 이미지 경로 |
| **title** | varchar | - | 이미지 제목 |
| **desc** | text | - | 이미지 설명 |
| **useCnt** | int | Default: 0 | 참조 촬영 횟수 |
| **kwd** | json | - | 키워드 코드 리스트 |
| **aiDoc** | varchar | - | AI json Document (가이드라인 정보) |
| **expWeight** | float | Default: 0 | 노출 가중치 |
| **pri** | int | Default: 0 | 우선순위 |
| **cDate** | bigint | - | 생성일 (Unix Timestamp) |
| **uDate** | bigint | - | 수정일 (Unix Timestamp) |

### 2.4 태그 관리 (`tb_tag`)
계층 구조를 가진 서비스 내 태그 시스템입니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 태그 고유 식별자 |
| **userId** | bigint | FK (`tb_user.id`) | 태그 생성자 ID |
| **parentCode** | varchar | - | 상위 태그 코드 |
| **code** | varchar | Unique | 태그 식별 코드 |
| **tagName** | varchar | Not Null | 태그 표시 명칭 |
| **cDate** | bigint | - | 생성일 (Unix Timestamp) |
| **uDate** | bigint | - | 수정일 (Unix Timestamp) |

### 2.5 북마크 (`mtb_bookmark`)
사용자와 레퍼런스 이미지 간의 북마크 관계를 관리합니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 매핑 고유 ID |
| **userId** | bigint | FK (`tb_user.id`) | 북마크한 사용자 ID |
| **imgId** | bigint | FK (`tb_img.id`) | 북마크한 레퍼런스 이미지 ID |
| **cDate** | bigint | - | 북마크 일시 (Unix Timestamp) |

### 2.6 이미지-태그 매핑 (`mtb_img_tag`)
레퍼런스 이미지와 태그의 다대다 관계를 관리합니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 매핑 고유 ID |
| **imgId** | bigint | FK (`tb_img.id`) | 대상 이미지 ID |
| **tagId** | bigint | FK (`tb_tag.id`) | 연결된 태그 ID |

* **Unique Index:** `(imgId, tagId)` 조합은 중복될 수 없습니다.

### 2.7 촬영 세션 (`tb_session`)
레퍼런스 촬영 과정의 세션 단위를 관리하며, 시스템 로그와 연결되는 핵심 테이블입니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | varchar(32) | PK | 세션 고유 식별자 (`UUIDv4 hex`, `generate_sid` 사용) |
| **userId** | bigint | FK (`tb_user.id`) | 세션 사용자 ID |
| **imgId** | bigint | FK (`tb_img.id`) | 참조한 레퍼런스 이미지 ID |
| **sDate** | bigint | - | 시작 시간 (Unix Timestamp) |
| **eDate** | bigint | - | 종료 시간 (Unix Timestamp) |
| **device** | json | - | 모델명, OS, 성능 정보 등 디바이스 메타데이터 |
| **sStat** | int | Default: 0 | 세션 상태 (`0: READY`, `1: COMPLETED`, `2: FAILED`) |
| **cDate** | bigint | - | 생성일 (Unix Timestamp) |
| **uDate** | bigint | - | 수정일 (Unix Timestamp) |

> `tb_session.id`는 Non-SQL 시스템 로그 데이터와 매핑되는 연결 키로 사용되며 `generate_sid()`가 반환하는 UUIDv4 hex 문자열 PK입니다.

### 2.8 상품 정보 (`tb_prod`)
스냅과 연결되는 상품 메타데이터를 관리합니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 상품 고유 식별자 |
| **userId** | bigint | FK (`tb_user.id`) | 상품 등록 사용자 ID |
| **name** | varchar | Not Null | 상품명 |
| **brand** | varchar | - | 상품 브랜드 |
| **price** | int | Default: 0 | 상품 가격 |
| **thumbUrl** | varchar | - | 상품 썸네일 경로 |
| **pStat** | int | Default: 1 | 상품 상태 (`0: INACTIVE`, `1: ACTIVE`, `2: SOLD_OUT`) |
| **cDate** | bigint | - | 생성일 (Unix Timestamp) |
| **uDate** | bigint | - | 수정일 (Unix Timestamp) |

### 2.10 실시간 로그 스냅샷 (`tb_rt_snapshot`)
실시간 스트림(게이트 대표값 로그)을 `secSeq` 단위로 마이크로배치 적재하는 시계열 파티션 테이블입니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 스냅샷 고유 식별자 |
| **sId** | varchar(32) | FK (`tb_session.id`) | 부모 세션 ID (1:N 시계열 매핑) |
| **secSeq** | int | Not Null | 세션 내 초 단위 순번 (`1,2,3...`) |
| **sDate** | bigint | Not Null | 해당 1초 구간 시작 시각 (Unix Timestamp) |
| **eDate** | bigint | Not Null | 해당 1초 구간 종료 시각 (Unix Timestamp) |
| **rawPayload** | json | Not Null | 1초 구간 대표값 레코드 배열 원문 |
| **cDate** | bigint | Not Null | 일 단위 파티션 키 (Unix Timestamp) |
| **userId** | bigint | Generated Stored | `rawPayload.meta.userId`에서 추출한 검색용 컬럼 |

* **Primary Key:** `(id, cDate)`
* **Index:** `idx_session_timeline (sId, secSeq, cDate)`
* **Index:** `idx_user_search (userId, cDate)`
* **Partitioning:** `PARTITION BY RANGE (cDate)` 권장

### 2.9 유저 촬영 스냅 (`tb_snap`)
유저가 촬영한 결과물과 후기, 신체 정보, 연결 상품 메타데이터를 아카이브합니다.

| 컬럼명 | 타입 | 제약사항 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | bigint | PK, Auto Increment | 스냅 고유 식별자 |
| **userId** | bigint | FK (`tb_user.id`) | 촬영 유저 ID |
| **prodId** | bigint | FK (`tb_prod.id`) | 연결된 상품 ID |
| **imgId** | bigint | FK (`tb_img.id`) | 참조한 레퍼런스 이미지 ID |
| **sId** | varchar(32) | FK (`tb_session.id`) | 연결된 촬영 세션 ID |
| **snapUrl** | varchar | Not Null | 촬영된 이미지 경로 |
| **comment** | text | - | 후기 내용 |
| **gender** | int | Default: 0 | 성별 (`0: UNKNOWN`, `1: MALE`, `2: FEMALE`) |
| **userH** | float | - | 촬영 시 입력한 키 |
| **userW** | float | - | 촬영 시 입력한 몸무게 |
| **viewCnt** | int | Default: 0 | 조회수 |
| **cDate** | bigint | - | 생성일 (Unix Timestamp) |
| **uDate** | bigint | - | 수정일 (Unix Timestamp) |

---

## 3. 관계 요약

* `tb_img.userId` -> `tb_user.id`
* `tb_img.ctgId` -> `tb_img_ctg.id`
* `tb_tag.userId` -> `tb_user.id`
* `mtb_bookmark.userId` -> `tb_user.id`
* `mtb_bookmark.imgId` -> `tb_img.id`
* `mtb_img_tag.imgId` -> `tb_img.id`
* `mtb_img_tag.tagId` -> `tb_tag.id`
* `tb_session.userId` -> `tb_user.id`
* `tb_session.imgId` -> `tb_img.id`
* `tb_prod.userId` -> `tb_user.id`
* `tb_snap.userId` -> `tb_user.id`
* `tb_snap.prodId` -> `tb_prod.id`
* `tb_snap.imgId` -> `tb_img.id`
* `tb_snap.sId` -> `tb_session.id`
* `tb_rt_snapshot.sId` -> `tb_session.id`

---

## 4. 특이사항 및 구현 가이드

1. **noneSQL DB 연동:** `tb_img.aiDocId`는 레퍼런스 이미지 분석/가이드 문서와 연결되고, `tb_session.id`는 시스템 로그 컬렉션과 매핑됩니다.
2. **저장소 분리:** 원본 및 결과 이미지 파일은 Cloudflare R2에 저장하고, RDBMS에는 경로와 메타데이터만 저장하는 구성을 전제로 합니다.
3. **계정 상태 관리:** `tb_user.state`로 계정 활성/비활성 여부를 관리하며, 물리 삭제 정책은 별도로 운영합니다.
4. **상태값 관리:** `tb_user.state`, `tb_session.sStat`, `tb_prod.pStat`, `tb_snap.gender`는 정수 코드 기반으로 관리합니다.
5. **데이터 무결성:** `tb_user`, `tb_img`, `tb_prod`, `tb_session` 삭제 시 `mtb_bookmark`, `mtb_img_tag`, `tb_snap`에 대한 Cascade 또는 비활성화 정책을 별도로 결정해야 합니다.
6. **성능 최적화:** `tb_user.state`, `tb_img`의 `useCnt`, `expWeight`, `pri`, `tb_prod`의 `pStat`, `tb_snap`의 `viewCnt`, `tb_session`의 `sStat`, `sDate`는 조회 패턴에 따라 보조 인덱스 검토가 필요합니다.
7. **전환 주의사항:** 현재 애플리케이션 API/서비스 레이어는 일부 문자열 ID 생성 로직과 기존 상태값 표현을 사용 중일 수 있으므로, 스키마 변경과 함께 서비스 레이어 호환성을 점검해야 합니다.
8. **실시간 로그 적재 전략:** `tb_rt_snapshot`은 Redis 버퍼(`session:buffer:{sId}:{secSeq}`)에서 `secSeq` 단위 완료 조건을 만족할 때 마이크로배치 적재하는 전략을 권장합니다.
9. **TTL 운영 권장:** Redis 완충 버퍼 TTL은 일반 촬영 길이와 재처리 여유를 고려해 `900초(15분)` 수준을 기본값으로 권장합니다.


## 5. Cloudflare R2 폴더 구조 정의서 (tryangle-images)
| 폴더명 | 용도 | DB 매핑 필드 | 파일명 예시 (Example) |
| :--- | :--- | :--- | :--- |
| `profiles/` | 사용자 프로필 이미지 | `tb_user.fileId` | `p_user123_1714730400.jpg` |
| `reference/` | 시스템 가이드용 레퍼런스 | `tb_img.imgUrl` | `ref_img99_1714730400.png` |
| `products/` | 상품 썸네일 이미지 | `tb_prod.thumbUrl` | `prod_123_1714730400.webp` |
| `snaps/` | 유저 촬영 결과물 (스냅) | `tb_snap.snapUrl` | `2026/05/snap_sId_1714730400.webp` |
| `temp/` | 업로드 중 임시 저장 | - | `tmp_upload_777888.jpg` |
| `legacy/` | 구버전 마이그레이션 데이터 | - | `old_profile_01.png` |