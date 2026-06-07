# fuel-log-receipt-sam

## 프로젝트 개요

영수증 이미지를 분석하여 내용을 JSON으로 반환하는 AWS Serverless 백엔드 서비스.

**핵심 흐름:**
1. 클라이언트가 API를 호출하여 S3 Presigned URL을 발급받음
2. 클라이언트가 Presigned URL을 통해 S3에 영수증 이미지를 직접 업로드
3. Lambda가 S3에 업로드된 이미지를 읽어 AWS Bedrock으로 전달
4. Bedrock(Claude 모델)이 영수증 내용을 분석하여 JSON으로 반환
5. 클라이언트에게 파싱된 영수증 데이터를 응답

## 기술 스택

- **IaC / 배포**: AWS SAM (Serverless Application Model)
- **런타임**: Python 3.14
- **패키지 관리**: uv
- **주요 AWS 서비스**:
  - API Gateway — HTTP 엔드포인트
  - Lambda — 비즈니스 로직
  - S3 — 영수증 이미지 저장 및 Presigned URL 발급
  - AWS Bedrock — 이미지 분석 (Claude 모델)

## 프로젝트 구조

```
fuel-log-receipt-sam/
├── template.yaml          # SAM 인프라 정의
├── samconfig.toml         # SAM CLI 설정 (스택명: fuel-log-receipt-sam)
├── pyproject.toml         # Python 프로젝트 설정 (uv)
├── hello_world/           # Lambda 함수 코드
│   ├── app.py             # Lambda 핸들러
│   └── requirements.txt   # Lambda 의존성
├── tests/
│   ├── unit/              # 단위 테스트
│   └── integration/       # 통합 테스트
└── events/
    └── event.json         # 로컬 테스트용 이벤트 샘플
```

## API 설계 (목표)

**공통: 사용자 식별 및 호출 제한 방식 (모든 API 공통 적용)**

두 API 모두 동일한 Lambda Authorizer + DynamoDB 방식으로 호출 제한을 적용한다.

- 사용자는 모든 요청 헤더에 `x-user-id`(고유 식별값)를 포함하여 전송
- API Gateway가 메인 Lambda를 실행하기 전에 **Lambda Authorizer**를 먼저 호출
- Lambda Authorizer는 **IP 제한 → 사용자 제한** 순서로 두 가지 조건을 모두 확인
  - IP 제한 초과 또는 사용자 제한 초과 시: `Deny` 정책 반환 → API Gateway가 `429 Too Many Requests` 응답
  - 모두 통과 시: `Allow` 정책 반환 → 메인 Lambda 실행
- 메인 Lambda는 인증 통과 후에만 실행되므로 비용 절감 효과

**호출 제한 기준 (1분 윈도우):**

| 기준 | 최대 요청 수 |
|---|---|
| IP 단위 | 5회/분 |
| 사용자(`x-user-id`) 단위 | 10회/분 |

**DynamoDB 테이블 설계:**
- Partition Key: `user_id` (문자열) — IP는 `ip#<ip>`, 사용자는 `user#<user_id>` 형태로 구분
- 속성: `request_count` (호출 횟수), `window_start` (윈도우 시작 시각), `ttl` (자동 삭제용 TTL)
- 윈도우 만료 시 `ConditionalCheckFailedException`으로 감지 후 카운트 리셋
- TTL로 만료된 아이템 자동 삭제

---

### 1. Presigned URL 발급

```
POST /receipt/upload-url
Headers:
  x-user-id: <사용자 고유 식별값>
Response:
  200: { "upload_url": "<presigned_url>", "key": "<s3_key>" }
  429: Too Many Requests (호출 한도 초과)
```

**흐름:**
```
클라이언트 (x-user-id 헤더 포함)
  → API Gateway
  → Lambda Authorizer
      ├── IP 제한 확인 (5회/분) → 초과 시 429
      ├── 사용자 제한 확인 (10회/분) → 초과 시 429
      └── 허용 → 메인 Lambda (Presigned URL 생성 후 반환)
                  → S3 (클라이언트가 직접 이미지 업로드)
```

### 2. 영수증 분석

```
POST /receipt/analyze
Headers:
  x-user-id: <사용자 고유 식별값>
Body: { "key": "<s3_key>" }
Response:
  200: { "items": [...], "total": ..., "date": ..., ... }
  429: Too Many Requests (호출 한도 초과)
```

**흐름:**
```
클라이언트 (x-user-id 헤더 포함)
  → API Gateway
  → Lambda Authorizer
      ├── IP 제한 확인 (5회/분) → 초과 시 429
      ├── 사용자 제한 확인 (10회/분) → 초과 시 429
      └── 허용 → 메인 Lambda (S3 이미지 읽기 → Bedrock 분석 → JSON 반환)
```

## 개발 명령어

```bash
# 빌드 (Lambda 런타임이 python3.12이므로 uv로 설치한 3.12 경로를 PATH에 추가)
PATH="/Users/ricepotato/.local/share/uv/python/cpython-3.12.10-macos-aarch64-none/bin:$PATH" sam build

# 로컬 API 실행
sam local start-api

# 배포
sam deploy

# 테스트
uv run pytest tests/unit/
```

## 주요 설계 결정

- 이미지 업로드는 클라이언트가 S3에 직접 업로드(Presigned URL)하여 Lambda를 통한 대용량 파일 전송 부하를 줄임
- 사용자 식별 및 호출 제한은 Lambda Authorizer + DynamoDB 조합으로 처리 — 메인 Lambda(Bedrock 호출) 실행 전에 차단하여 비용 절감
- Bedrock 호출 시 S3 이미지를 직접 참조하거나 바이트로 읽어 전달
- 영수증 파싱 결과는 구조화된 JSON 스키마로 고정 반환
