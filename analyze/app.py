import json
import os

import boto3

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
BUCKET = os.environ["RECEIPT_BUCKET"]
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    key = body.get("key")
    if not key:
        return {"statusCode": 400, "body": json.dumps({"error": "key is required"})}

    image_bytes = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
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
                                "media_type": "image/jpeg",
                                "data": __import__("base64").b64encode(image_bytes).decode(),
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "이 영수증 이미지에서 다음 정보를 추출하여 JSON으로만 응답하세요. "
                                "다른 텍스트 없이 JSON만 반환하세요.\n"
                                '{"date": "YYYY-MM-DD", "store": "가게명", '
                                '"items": [{"name": "상품명", "quantity": 수량, "price": 단가}], '
                                '"total": 합계금액, "currency": "KRW"}'
                            ),
                        },
                    ],
                }
            ],
        }),
    )

    result_text = json.loads(response["body"].read())["content"][0]["text"]
    receipt_data = json.loads(result_text)

    return {"statusCode": 200, "body": json.dumps(receipt_data, ensure_ascii=False)}
