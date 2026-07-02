"""全局异常处理 — 统一错误响应格式

所有 API 错误统一返回:
  {
    "error": {
      "code": "INTERNAL_ERROR",
      "message": "人类可读的错误描述",
      "trace_id": "xxx",
    }
  }
"""

import logging
import traceback
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger("testforge")


class AppError(Exception):
    """应用业务错误基类"""

    def __init__(self, code: str, message: str, status_code: int = 500, details: dict = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str, details: dict = None):
        super().__init__("NOT_FOUND", message, 404, details)


class ValidationError(AppError):
    def __init__(self, message: str, details: dict = None):
        super().__init__("VALIDATION_ERROR", message, 422, details)


class RateLimitError(AppError):
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__("RATE_LIMITED", message, 429, {"retry_after": retry_after})


class LLMUnavailableError(AppError):
    def __init__(self, message: str, details: dict = None):
        super().__init__("LLM_UNAVAILABLE", message, 503, details)


def _error_response(code: str, message: str, status_code: int, trace_id: str = "", details: dict = None):
    """构造统一错误响应"""
    body = {
        "error": {
            "code": code,
            "message": message,
            "trace_id": trace_id,
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        trace_id = getattr(request.state, "trace_id", "")
        if exc.status_code >= 500:
            logger.error("[trace=%s] %s: %s", trace_id, exc.code, exc.message)
        else:
            logger.warning("[trace=%s] %s: %s", trace_id, exc.code, exc.message)
        return _error_response(exc.code, exc.message, exc.status_code, trace_id, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", "")
        errors = []
        for err in exc.errors():
            errors.append({
                "field": ".".join(str(x) for x in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            })
        return _error_response("VALIDATION_ERROR", "请求参数验证失败", 422, trace_id, {"fields": errors})

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        trace_id = getattr(request.state, "trace_id", "")
        return _error_response("NOT_FOUND", f"路径不存在: {request.url.path}", 404, trace_id)

    @app.exception_handler(405)
    async def method_not_allowed_handler(request: Request, exc):
        trace_id = getattr(request.state, "trace_id", "")
        return _error_response("METHOD_NOT_ALLOWED", f"方法不允许: {request.method}", 405, trace_id)

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc):
        trace_id = getattr(request.state, "trace_id", "")
        logger.error("[trace=%s] 内部错误: %s\n%s", trace_id, exc, traceback.format_exc())
        return _error_response("INTERNAL_ERROR", "服务器内部错误", 500, trace_id)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        trace_id = getattr(request.state, "trace_id", "")
        logger.error("[trace=%s] 未处理异常: %s\n%s", trace_id, exc, traceback.format_exc())
        # 避免向客户端暴露内部错误细节
        safe_message = str(exc) if isinstance(exc, (ValueError, KeyError, TypeError)) else "服务器内部错误"
        return _error_response("INTERNAL_ERROR", safe_message, 500, trace_id)
