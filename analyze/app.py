import base64
import json
import os

import boto3

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
BUCKET = os.environ["RECEIPT_BUCKET"]
MODEL_ID = "apac.amazon.nova-lite-v1:0"

EXT_TO_FORMAT = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "png": "png",
    "webp": "webp",
    "heic": "jpeg",  # Nova는 heic 미지원, jpeg로 처리
}

PROMPT = (
    "이 영수증 이미지를 분석하여 실제 값을 추출한 JSON을 반환하세요. "
    "마크다운 없이 순수 JSON만 응답하세요.\n\n"
    "반환 형식:\n"
    "{\n"
    '  "date": "영수증의 실제 날짜 (YYYY-MM-DD 형식, 없으면 null)",\n'
    '  "store": "영수증의 실제 가게/업체명",\n'
    '  "items": [\n'
    '    {"name": "실제 상품명", "quantity": 실제수량(숫자), "price": 실제단가(숫자)}\n'
    "  ],\n"
    '  "total": 실제합계금액(숫자),\n'
    '  "currency": "KRW"\n'
    "}"
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

    # 모델이 마크다운 코드블록으로 감싸서 반환하는 경우 제거
    text = result_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    receipt_data = json.loads(text)
    return {"statusCode": 200, "body": json.dumps(receipt_data, ensure_ascii=False)}
