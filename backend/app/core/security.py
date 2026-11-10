from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta

from app.core.errors import Unauthorised

PBKDF2_ITERATIONS = 50_000


def hash_secret(value: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), salt, PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_secret(value: str, salt_hex: str, digest_hex: str) -> bool:
    digest = hashlib.pbkdf2_hmac(
        "sha256", value.encode(), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def issue_token(customer_id: int, secret: str, ttl: timedelta) -> str:
    payload = {"sub": str(customer_id), "exp": int(time.time() + ttl.total_seconds())}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def parse_token(token: str, secret: str) -> dict:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise Unauthorised("Invalid token") from exc
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise Unauthorised("Invalid token")
    padded = body + "=" * (-len(body) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded))
    except (json.JSONDecodeError, ValueError) as exc:
        raise Unauthorised("Invalid token") from exc
    if int(data.get("exp", 0)) < time.time():
        raise Unauthorised("Token expired")
    return data


def redact_secret(message: str, secret: str | None) -> str:
    if secret and secret in message:
        return message.replace(secret, "****")
    return message
