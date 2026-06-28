"""
E2E test: presigned URL 발급 → S3 업로드 → 영수증 분석 전체 흐름 검증.
실제 배포된 API Gateway를 호출하므로 네트워크 및 AWS 리소스가 필요합니다.

실행:
    uv run pytest tests/e2e/ -v

환경변수 (선택):
    API_URL  — 기본값: CLAUDE.md의 배포 URL
    E2E_USER_ID — x-user-id 헤더값, 기본값: e2e-test-user
"""
import os

import pytest
import requests

API_URL = os.environ.get(
    "API_URL",
    "https://91p5i7lvpj.execute-api.ap-northeast-2.amazonaws.com/Prod",
)
USER_ID = os.environ.get("E2E_USER_ID", "e2e-test-user")
TEST_IMAGE_PATH = os.path.join(
    os.path.dirname(__file__), "../../.test_data/image2.jpg"
)
CONTENT_TYPE = "image/jpeg"


@pytest.fixture(scope="module")
def uploaded_key():
    """Presigned URL 발급 후 S3에 이미지를 업로드하고 S3 key를 반환한다."""
    # 1단계: presigned URL 발급
    resp = requests.post(
        f"{API_URL}/receipt/upload-url",
        headers={"x-user-id": USER_ID, "Content-Type": "application/json"},
        json={"content_type": CONTENT_TYPE},
        timeout=10,
    )
    assert resp.status_code == 200, f"upload-url 실패: {resp.status_code} {resp.text}"

    body = resp.json()
    assert "upload_url" in body, "응답에 upload_url 없음"
    assert "key" in body, "응답에 key 없음"

    upload_url = body["upload_url"]
    key = body["key"]

    # 2단계: S3에 이미지 직접 업로드
    with open(TEST_IMAGE_PATH, "rb") as f:
        image_data = f.read()

    put_resp = requests.put(
        upload_url,
        data=image_data,
        headers={"Content-Type": CONTENT_TYPE},
        timeout=30,
    )
    assert put_resp.status_code in (200, 204), (
        f"S3 업로드 실패: {put_resp.status_code} {put_resp.text}"
    )

    return key


class TestReceiptFlow:

    def test_upload_url_returns_cloudfront_domain(self):
        """발급된 presigned URL이 CloudFront 도메인을 사용하는지 확인한다."""
        resp = requests.post(
            f"{API_URL}/receipt/upload-url",
            headers={"x-user-id": USER_ID, "Content-Type": "application/json"},
            json={"content_type": CONTENT_TYPE},
            timeout=10,
        )
        assert resp.status_code == 200
        upload_url = resp.json()["upload_url"]
        assert "cloudfront.net" in upload_url, (
            f"upload_url이 CloudFront 도메인이 아님: {upload_url}"
        )

    def test_analyze(self, uploaded_key):
        """영수증 분석 결과의 구조 및 모든 필드값을 검증한다."""
        resp = requests.post(
            f"{API_URL}/receipt/analyze",
            headers={"x-user-id": USER_ID, "Content-Type": "application/json"},
            json={"key": uploaded_key},
            timeout=60,
        )
        assert resp.status_code == 200, f"analyze 실패: {resp.status_code} {resp.text}"

        result = resp.json()
        for field in ("date", "location", "liters", "pricePerLiter", "totalPrice"):
            assert field in result, f"필드 누락: {field}"

        assert result["date"] == "2026-03-26"
        assert result["location"] == "태성주유소"
        assert result["totalPrice"] == 102000
        assert result["liters"] == pytest.approx(56.825, rel=0.01)
        assert result["pricePerLiter"] == pytest.approx(1795, abs=5)
