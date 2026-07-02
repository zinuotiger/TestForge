"""限流中间件 — 滑动窗口算法"""

import time
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流"""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        now = time.time()

        # 定期清理过期桶（每 5 分钟执行一次）
        if now - self._last_cleanup > 300:
            self._buckets = defaultdict(
                list,
                {k: v for k, v in self._buckets.items() if v},
            )
            self._last_cleanup = now

        # 清理过期记录
        bucket = self._buckets[client]
        self._buckets[client] = [t for t in bucket if now - t < self.window]

        if len(self._buckets[client]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": f"请求过于频繁，请 {self.window} 秒后重试"},
                headers={"Retry-After": str(self.window)},
            )

        self._buckets[client].append(now)
        return await call_next(request)
