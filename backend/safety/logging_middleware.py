"""结构化日志 + trace_id 中间件"""

import logging
import uuid
import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class TraceIDMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 trace_id"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4())[:12])
        request.state.trace_id = trace_id

        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start

        response.headers["X-Trace-ID"] = trace_id
        _log_request(request, response.status_code, elapsed, trace_id)
        return response


def _log_request(request: Request, status: int, elapsed: float, trace_id: str):
    log_data = {
        "trace_id": trace_id,
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "elapsed_ms": round(elapsed * 1000),
        "client": request.client.host if request.client else "unknown",
    }
    logger.info(json.dumps(log_data, ensure_ascii=False))


def setup_logging(level: str = "INFO"):
    """配置结构化日志"""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","message":%(message)s}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


logger = logging.getLogger("testforge")


def log_stage(trace_id: str, stage: str, status: str, detail: str = ""):
    logger.info(json.dumps({
        "trace_id": trace_id, "event": "stage",
        "stage": stage, "status": status, "detail": detail,
    }, ensure_ascii=False))


def log_llm_call(trace_id: str, provider: str, model: str, tokens: int, latency_ms: int):
    logger.info(json.dumps({
        "trace_id": trace_id, "event": "llm_call",
        "provider": provider, "model": model,
        "tokens": tokens, "latency_ms": latency_ms,
    }, ensure_ascii=False))
