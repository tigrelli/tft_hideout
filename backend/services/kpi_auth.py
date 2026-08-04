import hashlib
import hmac
import os
import time

# policies.md 13번: /kpi는 이용자 대상이 아닌 PM 전용 내부 화면 — 단일 공유 비밀번호 +
# 서명 토큰 방식으로 게이트한다(회원가입/로그인 시스템이 아님).
TOKEN_TTL_SECONDS = 60 * 60 * 12


def _secret() -> bytes:
    return os.environ["KPI_DASHBOARD_PASSWORD"].encode()


def verify_password(password: str) -> bool:
    return hmac.compare_digest(password, os.environ["KPI_DASHBOARD_PASSWORD"])


def issue_token(*, now: float | None = None) -> str:
    issued_at = now if now is not None else time.time()
    expires_at = int(issued_at) + TOKEN_TTL_SECONDS
    payload = str(expires_at)
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, *, now: float | None = None) -> bool:
    checked_at = now if now is not None else time.time()
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return False

    expected_signature = hmac.new(
        _secret(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return False

    try:
        expires_at = int(payload)
    except ValueError:
        return False
    return checked_at < expires_at
