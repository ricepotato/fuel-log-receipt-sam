import json
import os
import uuid
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.client import Config

_region = os.environ.get("AWS_REGION", "ap-northeast-2")
BUCKET = os.environ["RECEIPT_BUCKET"]
EXPIRES_IN = 300  # 5분
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN")

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}
DEFAULT_CONTENT_TYPE = "image/jpeg"

config = Config(s3={"addressing_style": "path"})
s3 = boto3.client(
    "s3",
    region_name=_region,
    endpoint_url=f"https://{CLOUDFRONT_DOMAIN}",
    config=config,
)


def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    content_type = body.get("content_type", DEFAULT_CONTENT_TYPE)

    if content_type not in ALLOWED_CONTENT_TYPES:
        return {
            "statusCode": 400,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, x-user-id",
            },
            "body": json.dumps(
                {
                    "error": "Unsupported content_type",
                    "allowed": list(ALLOWED_CONTENT_TYPES.keys()),
                }
            ),
        }

    ext = ALLOWED_CONTENT_TYPES[content_type]
    key = f"receipts/{uuid.uuid4()}.{ext}"
    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=EXPIRES_IN,
    )
    if CLOUDFRONT_DOMAIN:
        parsed = urlparse(upload_url)
        upload_url = urlunparse(parsed._replace(netloc=CLOUDFRONT_DOMAIN))
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, x-user-id",
        },
        "body": json.dumps(
            {"upload_url": upload_url, "key": key, "content_type": content_type}
        ),
    }
