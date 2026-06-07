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

### 1. Presigned URL 발급
```
POST /receipt/upload-url
Response: { "upload_url": "<presigned_url>", "key": "<s3_key>" }
```

### 2. 영수증 분석
```
POST /receipt/analyze
Body: { "key": "<s3_key>" }
Response: { "items": [...], "total": ..., "date": ..., ... }
```

## 개발 명령어

```bash
# 빌드
sam build

# 로컬 API 실행
sam local start-api

# 배포
sam deploy

# 테스트
uv run pytest tests/unit/
```

## 주요 설계 결정

- 이미지 업로드는 클라이언트가 S3에 직접 업로드(Presigned URL)하여 Lambda를 통한 대용량 파일 전송 부하를 줄임
- Bedrock 호출 시 S3 이미지를 직접 참조하거나 바이트로 읽어 전달
- 영수증 파싱 결과는 구조화된 JSON 스키마로 고정 반환
