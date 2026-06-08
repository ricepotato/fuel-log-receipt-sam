import base64
import json
import os

import boto3

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
BUCKET = os.environ["RECEIPT_BUCKET"]
MODEL_ID = "global.amazon.nova-2-lite-v1:0"

EXT_TO_FORMAT = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "png": "png",
    "webp": "webp",
    "heic": "jpeg",  # Nova는 heic 미지원, jpeg로 처리
}

PROMPT = (
    "이 영수증 이미지를 분석하여 실제 값을 추출한 JSON을 반환하세요. "
    "영수증에는 날짜, 주유 장소 명, 수량(리터), 단가(리터당 가격), 총액이 포함되어 있습니다."
    "총액을 필수로 포함하고 날짜, 가게명, 품목은 가능하면 포함하세요. "
    "총액 값을 찾을 수 없는 경우 total을 0으로 설정하세요. "
    "마크다운 없이 순수 JSON만 응답하세요.\n\n"
    "반환 형식:\n"
    "{\n"
    '  "date": "영수증의 실제 날짜 (YYYY-MM-DD 형식, 없으면 null)",\n'
    '  "location": "주유 장소명", (없으면 null)\n'
    '  "liters": "주유량", (리터, 없으면 null)\n'
    '  "pricePerLiter": "리터당 금액", (원)\n'
    '  "totalPrice": "총 주유 금액" (필수, 원)\n'
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
