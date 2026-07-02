"""LLM 连接测试 API — 支持多 Provider 实时检测"""

import time
from fastapi import APIRouter
from pydantic import BaseModel
from backend.config import settings

router = APIRouter()


class ProviderTestRequest(BaseModel):
    provider: str  # dashscope | deepseek | openai | ollama
    api_key: str = ""
    api_base: str = ""
    model: str = ""


class ProviderTestResult(BaseModel):
    provider: str
    status: str       # connected | failed | not_configured
    latency_ms: int
    model: str
    error: str = ""


@router.get("/providers")
async def list_providers():
    """列出所有支持的 LLM 提供商及当前配置状态"""
    return {
        "providers": [
            {
                "id": "dashscope",
                "name": "阿里云 DashScope (通义千问)",
                "icon": "☁️",
                "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen3-32b"],
                "configured": bool(settings.llm_provider == "dashscope" and settings.llm_api_key),
                "is_default": settings.llm_provider == "dashscope",
            },
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "icon": "🔍",
                "models": ["deepseek-chat", "deepseek-coder", "deepseek-v4"],
                "configured": bool("deepseek" in (settings.llm_provider or "").lower()),
                "is_default": "deepseek" in (settings.llm_provider or "").lower(),
            },
            {
                "id": "openai",
                "name": "OpenAI / Compatible",
                "icon": "🤖",
                "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
                "configured": bool("openai" in (settings.llm_provider or "").lower()),
                "is_default": "openai" in (settings.llm_provider or "").lower(),
            },
            {
                "id": "ollama",
                "name": "Ollama (本地)",
                "icon": "🏠",
                "models": ["qwen3-coder:7b", "codellama:7b", "llama3:8b"],
                "configured": settings.ollama_enabled,
                "is_default": False,
                "is_local": True,
            },
        ],
        "fallback_chain": settings.llm_fallback_chain.split(",") if settings.llm_fallback_chain else [],
        "current_mode": "api" if settings.llm_provider != "ollama" else "local",
    }


@router.post("/providers/test")
async def test_connection(req: ProviderTestRequest) -> ProviderTestResult:
    """测试 LLM 提供商连接"""
    key = req.api_key or settings.llm_api_key

    if req.provider == "ollama":
        return await _test_ollama(req.model or settings.ollama_model)

    if not key and req.provider != "ollama":
        return ProviderTestResult(
            provider=req.provider, status="not_configured",
            latency_ms=0, model=req.model or settings.llm_model,
            error="未配置 API Key",
        )

    base = req.api_base or settings.llm_api_base or _default_base(req.provider)
    model = req.model or settings.llm_model

    start = time.time()
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=10,
            ) as resp:
                latency = int((time.time() - start) * 1000)
                if resp.status == 200:
                    return ProviderTestResult(
                        provider=req.provider, status="connected",
                        latency_ms=latency, model=model,
                    )
                else:
                    text = await resp.text()
                    return ProviderTestResult(
                        provider=req.provider, status="failed",
                        latency_ms=latency, model=model,
                        error=f"HTTP {resp.status}: {text[:200]}",
                    )
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return ProviderTestResult(
            provider=req.provider, status="failed",
            latency_ms=latency, model=model,
            error=str(e)[:200],
        )


async def _test_ollama(model: str) -> ProviderTestResult:
    """测试 Ollama 本地连接"""
    start = time.time()
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.ollama_host}/api/generate",
                json={"model": model or settings.ollama_model, "prompt": "hi", "stream": False},
                timeout=10,
            ) as resp:
                latency = int((time.time() - start) * 1000)
                if resp.status == 200:
                    return ProviderTestResult(
                        provider="ollama", status="connected",
                        latency_ms=latency, model=model or settings.ollama_model,
                    )
                else:
                    return ProviderTestResult(
                        provider="ollama", status="failed",
                        latency_ms=latency, model=model or settings.ollama_model,
                        error=f"Ollama 未运行 ({resp.status})",
                    )
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return ProviderTestResult(
            provider="ollama", status="failed",
            latency_ms=latency, model=model or settings.ollama_model,
            error=f"Ollama 未运行: {str(e)[:100]}",
        )


def _default_base(provider: str) -> str:
    return {
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "openai": "https://api.openai.com/v1",
    }.get(provider, "https://api.openai.com/v1")


# ============ SMTP / Email Settings ============

import re
from pathlib import Path


class SmtpConfigRequest(BaseModel):
    host: str = ""
    port: int = 465
    use_tls: bool = True
    user: str = ""
    password: str = ""


@router.get("/email")
async def get_smtp_config():
    """Get current SMTP config (password masked)."""
    from backend.safety.notifier import is_email_configured
    return {
        "configured": is_email_configured(),
        "host": settings.smtp_host or "",
        "port": settings.smtp_port,
        "use_tls": settings.smtp_use_tls,
        "user": settings.smtp_user or "",
        "has_password": bool(settings.smtp_password),
    }


@router.post("/email")
async def save_smtp_config(req: SmtpConfigRequest):
    """Save SMTP configuration to .env file."""
    env_path = Path(settings.model_config.get("env_file", ".env"))
    if not env_path.exists():
        return {"success": False, "error": f".env file not found at {env_path}"}

    content = env_path.read_text(encoding="utf-8")

    updates = {
        "TESTFORGE_SMTP_HOST": req.host,
        "TESTFORGE_SMTP_PORT": str(req.port),
        "TESTFORGE_SMTP_USE_TLS": str(req.use_tls).lower(),
        "TESTFORGE_SMTP_USER": req.user,
    }

    if req.password:
        updates["TESTFORGE_SMTP_PASSWORD"] = req.password

    for key, value in updates.items():
        if re.search(rf"^{key}=", content, re.MULTILINE):
            content = re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)
        else:
            content += f"\n{key}={value}"

    env_path.write_text(content, encoding="utf-8")

    # Reload in-process settings
    settings.smtp_host = req.host or None
    settings.smtp_port = req.port
    settings.smtp_use_tls = req.use_tls
    settings.smtp_user = req.user or None
    if req.password:
        settings.smtp_password = req.password

    return {"success": True, "message": "SMTP config saved. Restart server for changes to take full effect."}


@router.post("/email/test")
async def test_smtp_connection(req: SmtpConfigRequest):
    """Test SMTP connection by sending a test email."""
    import smtplib
    from email.mime.text import MIMEText
    import time as _time

    host = req.host or settings.smtp_host
    port = req.port or settings.smtp_port
    user = req.user or settings.smtp_user
    password = req.password or settings.smtp_password
    use_tls = req.use_tls if req.host else settings.smtp_use_tls

    if not host or not user or not password:
        return {"success": False, "error": "Missing host, user, or password"}

    start = _time.time()
    try:
        if use_tls:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()

        server.login(user, password)

        msg = MIMEText("This is a test email from TestForge.", "plain", "utf-8")
        msg["From"] = user
        msg["To"] = user
        msg["Subject"] = "TestForge SMTP Test"

        server.sendmail(user, [user], msg.as_string())
        server.quit()

        latency = int((_time.time() - start) * 1000)
        return {"success": True, "latency_ms": latency, "message": f"Connection successful ({latency}ms)"}

    except Exception as e:
        latency = int((_time.time() - start) * 1000)
        return {"success": False, "latency_ms": latency, "error": str(e)[:300]}
