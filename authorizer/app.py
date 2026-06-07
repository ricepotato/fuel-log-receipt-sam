import os
import time

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RATE_LIMIT_TABLE"])

USER_MAX_REQUESTS = 10
IP_MAX_REQUESTS = 5
WINDOW_SECONDS = 60


def check_rate_limit(key: str, max_requests: int) -> bool:
    """1분 윈도우 기준 호출 횟수를 확인하고 카운트를 +1한다. 허용이면 True, 초과면 False."""
    now = int(time.time())
    window_start = now - WINDOW_SECONDS

    try:
        # 현재 윈도우 내에서 카운트 증가 (윈도우 만료 또는 아이템 없으면 예외 발생)
        response = table.update_item(
            Key={"user_id": key},
            UpdateExpression="SET request_count = request_count + :one, ttl = :ttl",
            ConditionExpression=(
                "attribute_exists(user_id) AND window_start > :window_start"
            ),
            ExpressionAttributeValues={
                ":one": 1,
                ":ttl": now + WINDOW_SECONDS * 2,
                ":window_start": window_start,
            },
            ReturnValues="ALL_NEW",
        )
        return int(response["Attributes"]["request_count"]) <= max_requests

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        # 아이템이 없거나 윈도우가 만료된 경우 → 카운트 리셋
        table.put_item(Item={
            "user_id": key,
            "request_count": 1,
            "window_start": now,
            "ttl": now + WINDOW_SECONDS * 2,
        })
        return True


def lambda_handler(event, context):
    headers = event.get("headers") or {}
    user_id = headers.get("x-user-id")

    if not user_id:
        return _deny("anonymous", event)

    # IP 추출: API Gateway는 requestContext에서, 프록시 환경은 x-forwarded-for에서
    ip = (
        (event.get("requestContext") or {}).get("identity", {}).get("sourceIp")
        or headers.get("x-forwarded-for", "").split(",")[0].strip()
        or "unknown"
    )

    if not check_rate_limit(f"ip#{ip}", IP_MAX_REQUESTS):
        return _deny(user_id, event)

    if not check_rate_limit(f"user#{user_id}", USER_MAX_REQUESTS):
        return _deny(user_id, event)

    return _allow(user_id, event)


def _allow(user_id, event):
    return {
        "principalId": user_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": event.get("methodArn", "*"),
                }
            ],
        },
        "context": {"user_id": user_id},
    }


def _deny(user_id, event):
    return {
        "principalId": user_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": event.get("methodArn", "*"),
                }
            ],
        },
    }
