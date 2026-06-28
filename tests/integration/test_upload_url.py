import json
import os
import re
import sys

# 모듈 레벨 S3 client 초기화 전에 환경변수 설정 필요
os.environ.setdefault("RECEIPT_BUCKET", "test-receipt-bucket")
os.environ.setdefault("CLOUDFRONT_DOMAIN", "test.cloudfront.net")
os.environ.setdefault("AWS_REGION", "ap-northeast-2")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../upload_url"))

from app import lambda_handler  # noqa: E402

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
CLOUDFRONT_DOMAIN = os.environ["CLOUDFRONT_DOMAIN"]


def make_event(body=None):
    return {"body": json.dumps(body) if body is not None else None}


def test_default_content_type():
    response = lambda_handler(make_event({}), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["content_type"] == "image/jpeg"
    assert body["key"].endswith(".jpg")


def test_jpeg_content_type():
    response = lambda_handler(make_event({"content_type": "image/jpeg"}), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["content_type"] == "image/jpeg"
    assert body["key"].endswith(".jpg")


def test_png_content_type():
    response = lambda_handler(make_event({"content_type": "image/png"}), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["content_type"] == "image/png"
    assert body["key"].endswith(".png")


def test_webp_content_type():
    response = lambda_handler(make_event({"content_type": "image/webp"}), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["content_type"] == "image/webp"
    assert body["key"].endswith(".webp")


def test_heic_content_type():
    response = lambda_handler(make_event({"content_type": "image/heic"}), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["content_type"] == "image/heic"
    assert body["key"].endswith(".heic")


def test_invalid_content_type():
    response = lambda_handler(make_event({"content_type": "image/gif"}), None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "allowed" in body


def test_none_body():
    response = lambda_handler({"body": None}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["key"].endswith(".jpg")


def test_key_format():
    response = lambda_handler(make_event({"content_type": "image/jpeg"}), None)

    body = json.loads(response["body"])
    key = body["key"]
    assert key.startswith("receipts/")
    assert UUID_RE.search(key), f"key에 UUID가 없음: {key}"
    assert key.endswith(".jpg")


def test_upload_url_is_presigned():
    response = lambda_handler(make_event({"content_type": "image/jpeg"}), None)

    body = json.loads(response["body"])
    upload_url = body["upload_url"]
    assert upload_url.startswith("https://")
    assert "X-Amz-Signature" in upload_url


def test_cloudfront_domain_in_url():
    response = lambda_handler(make_event({"content_type": "image/jpeg"}), None)

    body = json.loads(response["body"])
    upload_url = body["upload_url"]
    assert CLOUDFRONT_DOMAIN in upload_url, (
        f"URL에 CloudFront 도메인({CLOUDFRONT_DOMAIN})이 없음: {upload_url}"
    )


def test_cors_headers_in_response():
    response = lambda_handler(make_event({"content_type": "image/jpeg"}), None)

    headers = response.get("headers", {})
    assert headers.get("Access-Control-Allow-Origin") == "*"


def test_cors_headers_on_error():
    response = lambda_handler(make_event({"content_type": "image/gif"}), None)

    headers = response.get("headers", {})
    assert headers.get("Access-Control-Allow-Origin") == "*"
