import base64
import json
import os

import boto3

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
BUCKET = os.environ["RECEIPT_BUCKET"]
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

EXT_TO_MEDIA_TYPE = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/jpeg",
}

PROMPT = (
    "이 주유소 영수증 이미지를 분석하여 실제 값을 추출한 JSON을 반환하세요. "
    "마크다운 없이 순수 JSON만 응답하세요.\n\n"
    "【숫자 읽는 규칙】\n"
    "- 한국 영수증의 쉼표(,)는 천 단위 구분자입니다. 소수점이 아닙니다.\n"
    "  예: '1,795' → 1795 (정수), '56.825' → 56.825 (소수)\n\n"
    "【컬럼 구조】영수증 항목의 컬럼 순서: 단가 → 수량 → 금액\n"
    "- 단가(pricePerLiter): 1리터당 가격. 쉼표 제거 후 1000~2500 범위의 정수.\n"
    "- 수량(liters): 주유한 리터 수. 소수점을 포함하며 10~100 범위.\n"
    "- 단가 > 수량 조건이 반드시 성립합니다. 추출한 두 값이 이 조건을 만족하지 않으면 서로 바꾸세요.\n\n"
    "【기타】\n"
    "- location은 주소가 아닌 상호명만 추출하세요.\n"
    "- totalPrice를 찾을 수 없으면 0으로 설정하세요.\n\n"
    "반환 형식 (숫자 필드는 문자열이 아닌 숫자로 반환):\n"
    "{\n"
    '  "date": "YYYY-MM-DD (없으면 null)",\n'
    '  "location": "상호명 (없으면 null)",\n'
    '  "liters": 주유량(숫자, 없으면 null),\n'
    '  "pricePerLiter": 리터당금액(숫자, 없으면 null),\n'
    '  "totalPrice": 총금액(숫자, 필수)\n'
    "}"
)


def analyze_image(image_bytes: bytes, media_type: str) -> dict:
    image_data = base64.b64encode(image_bytes).decode()

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": PROMPT},
                        ],
                    }
                ],
            }
        ),
    )

    result_text = json.loads(response["body"].read())["content"][0]["text"]

    # 모델이 마크다운 코드블록으로 감싸서 반환하는 경우 제거
    text = result_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return json.loads(text)


def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    key = body.get("key")
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, x-user-id",
    }

    if not key:
        return {"statusCode": 400, "headers": cors_headers, "body": json.dumps({"error": "key is required"})}

    ext = key.rsplit(".", 1)[-1].lower() if "." in key else "jpg"
    media_type = EXT_TO_MEDIA_TYPE.get(ext, "image/jpeg")

    # cloudfront 를 통해 접근할 경우 path-style addressing를 사용해야 하므로, s3.get_object 호출 시 Bucket 이름을 포함한 Key를 사용한다.
    image_bytes = s3.get_object(Bucket=BUCKET, Key=f"{BUCKET}/{key}")["Body"].read()
    receipt_data = analyze_image(image_bytes, media_type)

    return {"statusCode": 200, "headers": cors_headers, "body": json.dumps(receipt_data, ensure_ascii=False)}
