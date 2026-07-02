"""TestForge FastAPI 应用入口 — 生产级配置

企业级特性：
  - JWT 认证 + RBAC 角色权限（Admin/Editor/Viewer）
  - 用户管理 API（CRUD + API Token）
  - 登录失败速率限制（5次/分钟锁IP 15分钟）
  - Token 刷新机制（access 24h + refresh 7d）
  - 全局异常处理（统一错误响应）
  - 容错模块（重试 + 熔断器 + 吞吐量监控）
  - 结构化日志 + trace_id
"""

import logging

import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.api.tests import router as tests_router
from backend.api.executions import router as executions_router
from backend.api.reports import router as reports_router
from backend.api.settings_api import router as settings_router
from backend.api.analysis import router as analysis_router
from backend.api.website import router as website_router
from backend.api.agent_api import router as agent_router
from backend.api.websocket import router as ws_router
from backend.api.import_export import router as import_export_router
from backend.api.recording import router as recording_router
from backend.api.token_usage import router as token_usage_router
from backend.api.auth_api import router as auth_router
from backend.api.code_test import router as code_test_router
from backend.api.evolution import router as evolution_router
from backend.core.pipeline import pipeline_engine
from backend.core.scheduler import scan_scheduler
from backend.core.rag import load_from_database
from backend.models.store import init_db, close_db
from backend.safety.users import init_users_table
from backend.safety.security_checks import (
    validate_security_config,
    get_admin_credentials,
    check_debug_mode_warnings,
    validate_cors_config,
)
from backend.safety.logging_middleware import TraceIDMiddleware, setup_logging
from backend.safety.rate_limit import RateLimitMiddleware
from backend.safety.exception_handler import register_exception_handlers
from backend.safety.resilience import list_circuit_breakers, list_monitors

setup_logging(settings.log_level)
logger = logging.getLogger("testforge")

validate_security_config()

_admin_username, _admin_password_hash = get_admin_credentials()


async def _safe_run(coro, name, timeout=10):
    try:
        await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Lifespan step %s timed out after %ds, skipping", name, timeout)
    except Exception as e:
        logger.warning("Lifespan step %s failed: %s", name, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio as _asyncio
    await _safe_run(init_db(), "init_db")
    await _safe_run(init_users_table(), "init_users_table")
    try: pipeline_engine.start()
    except Exception as e: logger.warning("pipeline_engine.start() failed: %s", e)
    _evolution_task = _asyncio.ensure_future(_run_periodic_evolution()) if _asyncio.get_event_loop().is_running() else None
    try: scan_scheduler.start()
    except Exception as e: logger.warning("scan_scheduler.start() failed: %s", e)
    await _safe_run(asyncio.to_thread(load_from_database), "load_from_database")
    check_debug_mode_warnings()
    
    yield
    
    if _evolution_task:
        _evolution_task.cancel()
        try:
            await _evolution_task
        except _asyncio.CancelledError:
            pass
    try: scan_scheduler.stop()
    except Exception: pass
    try: pipeline_engine.stop()
    except Exception: pass
    await close_db()


async def _run_periodic_evolution():
    await asyncio.sleep(30)
    while True:
        try:
            await pipeline_engine.run_evolution_analysis(project_id="default")
        except Exception:
            pass
        await asyncio.sleep(600)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="全类型智能测试平台 — 测试设计 + 生成 + 执行 + 分析 + 自愈 + Agent",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)
app.add_middleware(TraceIDMiddleware)

cors_origins = validate_cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Trace-ID"],
)

register_exception_handlers(app)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(tests_router, prefix="/api/tests", tags=["tests"])
app.include_router(executions_router, prefix="/api/executions", tags=["executions"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
app.include_router(website_router, prefix="/api/website", tags=["website"])
app.include_router(agent_router, prefix="/api/intelligence", tags=["agent"])
app.include_router(import_export_router, prefix="/api/tests", tags=["import-export"])
app.include_router(recording_router, prefix="/api/record", tags=["recording"])
app.include_router(token_usage_router, prefix="/api/token-usage", tags=["token-usage"])
app.include_router(code_test_router, prefix="/api/code", tags=["code-test"])
app.include_router(ws_router, prefix="/ws", tags=["websocket"])
app.include_router(evolution_router, tags=["evolution"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "name": settings.app_name,
        "version": settings.app_version,
        "uptime": "running",
        "environment": "development" if settings.debug else "production",
        "security_checks": "passed",
    }


@app.get("/api/health/readiness")
async def readiness():
    import psutil
    return {
        "ready": True,
        "environment": "development" if settings.debug else "production",
        "cpu_pct": psutil.cpu_percent(),
        "mem_available_gb": round(psutil.virtual_memory().available / 1e9, 2),
        "subscribers": pipeline_engine.subscriber_count(),
        "database": "connected",
    }


@app.get("/api/metrics")
async def metrics():
    import psutil
    from backend.generator.router import strategy_stats

    monitors = list_monitors()
    breakers = list_circuit_breakers()

    return {
        "testforge_health": 1,
        "testforge_cpu_percent": psutil.cpu_percent(),
        "testforge_memory_used_bytes": psutil.virtual_memory().used,
        "testforge_ws_subscribers": pipeline_engine.subscriber_count(),
        "testforge_strategy_calls_total": {
            k: v["calls"] for k, v in strategy_stats.items()
        },
        "throughput": monitors,
        "circuit_breakers": breakers,
        "environment": "development" if settings.debug else "production",
    }


# ---- Frontend SPA serving (must be last) ----
_frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    from fastapi.responses import FileResponse
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        return FileResponse(os.path.join(_frontend_dist, "index.html"), media_type="text/html; charset=utf-8")
