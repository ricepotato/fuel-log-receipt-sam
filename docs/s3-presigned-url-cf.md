markdown_content = """# CloudFront + S3 Presigned URL 안전한 업로드(PUT) 아키텍처 설정 가이드

프론트엔드(클라이언트)에서 S3 버킷 이름 및 원본 엔드포인트를 노출하지 않고, CloudFront 도메인을 경유하여 안전하고 빠르게 파일을 업로드(PUT)하기 위한 전체 설정 가이드입니다.

---

## 1. 아키텍처 개요

- **기존 방식**: `프론트엔드 -> S3 Presigned URL 직접 업로드` (S3 버킷명 및 엔드포인트 노출 리스크, 글로벌 업로드 속도 저하)
- **개선 방식**: `프론트엔드 -> CloudFront 도메인 -> [CloudFront Functions (버킷명 주입)] -> S3 OAC 안전 업로드`

---

## 2. AWS 리소스 설정

### ① S3 버킷 설정
1. **버킷 생성 및 퍼블릭 액세스 차단**:
   - 버킷을 생성하고 **[퍼블릭 액세스 차단(Block all public access)]**을 모두 활성화하여 외부 직접 접근을 원천 차단합니다.
2. **CORS(Cross-Origin Resource Sharing) 설정**:
   - 프론트엔드 브라우저에서 CloudFront 도메인으로 `PUT` 요청을 보낼 때 발생하는 CORS 에러를 방지하기 위해 버킷 **[권한(Permissions)]** 탭 최하단에 아래 설정을 적용합니다.
   ```json
   [
       {
           "AllowedHeaders": ["*"],
           "AllowedMethods": ["PUT", "POST", "GET", "HEAD"],
           "AllowedOrigins": [
               "[https://your-frontend-domain.com](https://your-frontend-domain.com)",
               "http://localhost:3000"
           ],
           "ExposeHeaders": ["ETag"],
           "MaxAgeSeconds": 3000
       }
   ]