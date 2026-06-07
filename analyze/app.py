import base64
import json
import os

import boto3

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
BUCKET = os.environ["RECEIPT_BUCKET"]
MODEL_ID = "amazon.nova-lite-v2:0"

EXT_TO_FORMAT = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "png": "png",
    "webp": "webp",
    "heic": "jpeg",  # Nova는 heic 미지원, jpeg로 처리
}

PROMPT = (
    "이 영수증 이미지에서 다음 정보를 추출하여 JSON으로만 응답하세요. "
    "다른 텍스트 없이 JSON만 반환하세요.\n"
    '{"date": "YYYY-MM-DD", "store": "가게명", '
    '"items": [{"name": "상품명", "quantity": 수량, "price": 단가}], '
    '"total": 합계금액, "currency": "KRW"}'
)


def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    key = body.get("key")
    if not key:
        return {"statusCode": 400, "body": json.dumps({"error": "key is required"})}

    ext = key.rsplit(".", 1)[-1].lower() if "." in key else "jpg"
    image_format = EXT_TO_FORMAT.get(ext, "jpeg")

    image_bytes = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": image_format,
                                "source": {
                                    "bytes": base64.b64encode(image_bytes).decode(),
                                },
                            }
                        },
                        {"text": PROMPT},
                    ],
                }
            ],
            "inferenceConfig": {"maxTokens": 1024},
        }),
    )

    result_text = json.loads(response["body"].read())["output"]["message"]["content"][0]["text"]
    receipt_data = json.loads(result_text)

    return {"statusCode": 200, "body": json.dumps(receipt_data, ensure_ascii=False)}
