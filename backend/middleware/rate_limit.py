import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 정책(docs/reference/policies.md 6번): IP 기준, 인증 없음
# {prefix: (limit, window_seconds)}
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/catalog": (60, 60),
    "/api/v1/chat": (10, 60),
}

_buckets: dict[tuple[str, str], tuple[float, int]] = {}


def reset_buckets() -> None:
    """테스트 간 상태 격리용. 프로덕션에서는 호출하지 않는다."""
    _buckets.clear()


def _match_prefix(path: str) -> str | None:
    for prefix in RATE_LIMITS:
        if path.startswith(prefix):
            return prefix
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, clock: Callable[[], float] = time.time) -> None:
        super().__init__(app)
        self._clock = clock

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        prefix = _match_prefix(request.url.path)
        if prefix is None:
            return await call_next(request)

        limit, window_seconds = RATE_LIMITS[prefix]
        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, prefix)
        now = self._clock()

        window_start, count = _buckets.get(key, (now, 0))
        if now - window_start >= window_seconds:
            window_start, count = now, 0

        count += 1
        _buckets[key] = (window_start, count)

        if count > limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": f"{prefix} 분당 {limit}회 한도를 초과했습니다",
                    }
                },
            )

        return await call_next(request)
