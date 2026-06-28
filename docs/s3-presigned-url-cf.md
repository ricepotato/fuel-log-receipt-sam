# CloudFront + S3 Presigned URL 안전한 업로드(PUT) 아키텍처 설정 가이드

프론트엔드(클라이언트)에서 S3 버킷 이름 및 원본 엔드포인트를 노출하지 않고, CloudFront 도메인을 경유하여 안전하고 빠르게 파일을 업로드(PUT)하기 위한 전체 설정 가이드입니다.

---

## 1. 아키텍처 개요

- **기존 방식**: `프론트엔드 → S3 Presigned URL 직접 업로드` (S3 버킷명 및 엔드포인트 노출 리스크, 글로벌 업로드 속도 저하)
- **개선 방식**: `프론트엔드 → CloudFront 도메인 → S3 OAC 안전 업로드`

```
브라우저
  ├─ OPTIONS preflight ──→ CloudFront ──→ S3 (CORS-S3Origin policy로 Origin 헤더 전달)
  └─ PUT (presigned URL) → CloudFront ──→ S3
```

---

## 2. AWS 리소스 설정

### ① S3 버킷 설정

**버킷 생성 및 퍼블릭 액세스 차단**
- 버킷을 생성하고 **[퍼블릭 액세스 차단(Block all public access)]** 을 모두 활성화하여 외부 직접 접근을 차단합니다.

**CORS 설정**

브라우저가 CloudFront 도메인으로 `PUT` 요청을 보낼 때 발생하는 CORS 에러를 방지하기 위해 S3 버킷에 아래 CORS 규칙을 적용합니다.
S3는 CORS 설정이 존재하면 OPTIONS preflight 요청을 자동으로 처리하므로 `AllowedMethods`에 `OPTIONS`를 명시할 필요가 없습니다.

콘솔에서 직접 설정할 경우:
```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["PUT", "POST", "GET", "HEAD"],
        "AllowedOrigins": ["*"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000
    }
]
```

SAM/CloudFormation으로 관리할 경우 (`template.yaml`):
```yaml
ReceiptBucket:
  Type: AWS::S3::Bucket
  Properties:
    CorsConfiguration:
      CorsRules:
        - AllowedHeaders:
            - "*"
          AllowedMethods:
            - PUT
            - POST
            - GET
            - HEAD
          AllowedOrigins:
            - "*"
          ExposedHeaders:
            - ETag
          MaxAge: 3000
```

> **주의**: CloudFormation의 `AllowedMethods`에는 `OPTIONS`가 유효하지 않은 값입니다. S3가 자동으로 처리하므로 생략합니다.

---

### ② CloudFront 설정

#### Origin Request Policy — CORS-S3Origin 적용 (핵심)

CloudFront는 기본적으로 `Origin` 헤더를 S3에 전달하지 않습니다. 이 때문에 S3가 CORS 응답 헤더(`Access-Control-Allow-Origin` 등)를 반환하지 않아 브라우저의 preflight가 실패합니다.

AWS 관리형 정책 **`CORS-S3Origin`** 을 DefaultCacheBehavior에 적용하면 다음 헤더가 S3로 전달됩니다:
- `Origin`
- `Access-Control-Request-Headers`
- `Access-Control-Request-Method`

AWS CLI로 적용하는 방법:
```bash
# 현재 배포 설정 조회 (ETag 포함)
aws cloudfront get-distribution-config --id <DISTRIBUTION_ID> > cf-config.json

# DistributionConfig.DefaultCacheBehavior에 OriginRequestPolicyId 추가
# CORS-S3Origin 관리형 정책 ID: 88a5eaf4-2fd4-4709-b370-b4c650ea3fcf
python3 - <<'EOF'
import json
with open('cf-config.json') as f:
    data = json.load(f)
data['DistributionConfig']['DefaultCacheBehavior']['OriginRequestPolicyId'] = \
    '88a5eaf4-2fd4-4709-b370-b4c650ea3fcf'
with open('cf-config-updated.json', 'w') as f:
    json.dump(data['DistributionConfig'], f)
EOF

aws cloudfront update-distribution \
  --id <DISTRIBUTION_ID> \
  --if-match <ETAG> \
  --distribution-config file://cf-config-updated.json
```

#### AllowedMethods 설정

CloudFront 배포의 DefaultCacheBehavior에 `OPTIONS`, `PUT` 등 필요한 메서드가 모두 허용되어 있어야 합니다:

```
AllowedMethods: HEAD, DELETE, POST, GET, OPTIONS, PUT, PATCH
CachedMethods:  HEAD, GET, OPTIONS
```

---

## 3. API Gateway CORS 설정

Lambda Authorizer가 설정된 API Gateway에서는 브라우저의 OPTIONS preflight 요청도 Authorizer를 거치게 되어 `x-user-id` 헤더가 없으면 403이 반환됩니다.

**`template.yaml` 수정:**
```yaml
ReceiptApi:
  Type: AWS::Serverless::Api
  Properties:
    StageName: Prod
    Cors:
      AllowMethods: "'POST, OPTIONS'"
      AllowHeaders: "'Content-Type, x-user-id'"
      AllowOrigin: "'*'"
    Auth:
      DefaultAuthorizer: LambdaAuthorizer
      AddDefaultAuthorizerToCorsPreflight: false  # OPTIONS는 Authorizer 제외
      Authorizers:
        LambdaAuthorizer:
          ...
```

- `Cors` 블록: API Gateway가 OPTIONS 메서드에 자동으로 CORS 헤더 포함 응답을 생성
- `AddDefaultAuthorizerToCorsPreflight: false`: preflight OPTIONS 요청을 Authorizer 없이 통과

**Lambda 응답에 CORS 헤더 추가:**

API Gateway의 CORS 설정은 OPTIONS 응답만 처리합니다. 실제 POST 응답도 브라우저가 수락하려면 Lambda 함수 응답에 CORS 헤더를 포함해야 합니다.

```python
return {
    "statusCode": 200,
    "headers": {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, x-user-id",
    },
    "body": json.dumps({...}),
}
```

---

## 4. CORS 오류 원인별 체크리스트

| 증상 | 원인 | 해결 |
|---|---|---|
| API Gateway preflight 403 | Lambda Authorizer가 OPTIONS 차단 | `AddDefaultAuthorizerToCorsPreflight: false` + `Cors` 블록 추가 |
| API Gateway 실제 응답 CORS 오류 | Lambda 응답에 CORS 헤더 없음 | Lambda 응답에 `Access-Control-Allow-Origin` 헤더 추가 |
| CloudFront presigned URL preflight 403/오류 | CloudFront가 `Origin` 헤더를 S3에 미전달 | `CORS-S3Origin` Origin Request Policy 적용 |
| S3 CORS 응답 헤더 없음 | S3 CORS 미설정 | S3 버킷에 CorsConfiguration 추가 |
