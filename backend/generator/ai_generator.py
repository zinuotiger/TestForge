"""AI/LLM 测试生成器 — DashScope API + LiteLLM 双通道"""

import json
import logging
import time
import aiohttp
from backend.config import settings
from backend.core.token_tracker import token_tracker
from backend.models import TestCase, TestStep, Assertion, AssertionType, StepType, TestType

try:
    import litellm
    _has_litellm = True
except ImportError:
    _has_litellm = False

logger = logging.getLogger("testforge")


async def generate_tests(source_code: str, language: str = "python", function_name: str = "") -> list[TestCase]:
    """使用 AI 为源码生成测试用例"""

    # 通道 1: DashScope API (直连，最快)
    if settings.llm_api_key and "dashscope" in settings.llm_provider.lower():
        try:
            return await _call_dashscope(source_code, language, function_name)
        except Exception as e:
            logger.warning("DashScope 调用失败，降级到 LiteLLM: %s", e)

    # 通道 2: LiteLLM (通用接口)
    try:
        return await _call_litellm(source_code, language, function_name)
    except Exception as e:
        logger.warning("LiteLLM 调用失败，降级到 Ollama: %s", e)

    # 通道 3: 本地 Ollama
    if settings.ollama_enabled:
        try:
            return await _call_ollama(source_code, language, function_name)
        except Exception as e:
            logger.warning("Ollama 调用失败，使用模板兜底: %s", e)

    # 全部失败 → 返回模板兜底
    return [TestCase(
        name=f"AI降级测试-{function_name or 'unknown'}",
        type=TestType.UNIT,
        created_by="ai_fallback",
        steps=[TestStep(
            id="step_fb", type=StepType.CODE_EXEC,
            description=f"验证 {function_name} 正常返回",
            assertions=[Assertion(type=AssertionType.EQUALS, expected="not None")],
        )],
    )]


async def _call_dashscope(source_code: str, language: str, function_name: str) -> list[TestCase]:
    """DashScope API 直连"""
    start = time.time()

    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": _build_prompt(source_code, language, function_name)}],
        "temperature": settings.llm_temperature_code,
        "max_tokens": settings.llm_max_tokens_code,
    }

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=body, headers=headers) as resp:
            text = await resp.text()
            data = json.loads(text)
            content = data["choices"][0]["message"]["content"]

            # 记录 token 用量
            usage = data.get("usage", {})
            token_tracker.record(
                provider="dashscope",
                model=settings.llm_model,
                scene="code_gen",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                latency_ms=int((time.time() - start) * 1000),
                success=True,
            )

            return _parse_response(content)


async def _call_litellm(source_code: str, language: str, function_name: str) -> list[TestCase]:
    """LiteLLM 通用接口"""
    start = time.time()
    response = await litellm.acompletion(
        model=f"{settings.llm_provider}/{settings.llm_model}",
        messages=[{"role": "user", "content": _build_prompt(source_code, language, function_name)}],
        temperature=settings.llm_temperature_code,
        max_tokens=settings.llm_max_tokens_code,
        api_key=settings.llm_api_key,
        api_base=settings.llm_api_base,
    )

    # 记录 token 用量
    usage = getattr(response, "usage", None)
    token_tracker.record(
        provider=settings.llm_provider,
        model=settings.llm_model,
        scene="code_gen",
        prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        latency_ms=int((time.time() - start) * 1000),
        success=True,
    )

    return _parse_response(response.choices[0].message.content)


async def _call_ollama(source_code: str, language: str, function_name: str) -> list[TestCase]:
    """Ollama 本地模型"""
    start = time.time()
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{settings.ollama_host}/api/generate",
            json={"model": settings.ollama_model, "prompt": _build_prompt(source_code, language, function_name), "stream": False},
        ) as resp:
            data = await resp.json()

            # 记录 token 用量（Ollama 返回 eval_count/prompt_eval_count）
            token_tracker.record(
                provider="ollama",
                model=settings.ollama_model,
                scene="code_gen",
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                latency_ms=int((time.time() - start) * 1000),
                success=True,
            )

            return _parse_response(data.get("response", ""))


def _build_prompt(source_code: str, language: str, function_name: str) -> str:
    return f"""你是资深测试工程师。为以下 {language} 代码生成单元测试用例，JSON格式。

源代码:
```{language}
{source_code}
```

{f"重点测试: {function_name}" if function_name else ""}

返回JSON数组，每个元素格式:
{{"name":"测试名称","type":"unit","steps":[{{"type":"code_exec","description":"步骤描述","assertions":[{{"type":"equals","expected":"期望值"}}]}}]}}

要求: 覆盖正常路径、边界值(null/0/-1)、异常路径。至少3个用例。只返回JSON。"""


def _parse_response(text: str) -> list[TestCase]:
    """解析AI响应"""
    import uuid

    # 提取 JSON 块
    json_str = text
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        json_str = text.split("```")[1].split("```")[0]
    elif "[" in text:
        json_str = text[text.index("["):text.rindex("]")+1]

    try:
        data = json.loads(json_str)
    except Exception:
        return [_fallback_test(text)]

    items = data if isinstance(data, list) else [data]
    cases = []
    for item in items:
        if not isinstance(item, dict):
            continue
        steps = []
        for s in item.get("steps", []):
            steps.append(TestStep(
                id=f"step_{uuid.uuid4().hex[:6]}",
                type=StepType(s.get("type", "code_exec")),
                description=s.get("description", ""),
                assertions=[Assertion(
                    type=AssertionType(a.get("type", "equals")),
                    expected=a.get("expected"),
                ) for a in s.get("assertions", [])],
            ))
        cases.append(TestCase(
            name=item.get("name", "AI生成测试"),
            type=TestType(item.get("type", "unit")),
            created_by="ai",
            steps=steps,
        ))
    return cases or [_fallback_test(text)]


def _fallback_test(text: str) -> TestCase:
    return TestCase(
        name="AI降级测试",
        type=TestType.UNIT,
        created_by="ai_fallback",
        steps=[TestStep(
            id="step_fb", type=StepType.CODE_EXEC,
            description=text[:200],
            assertions=[Assertion(type=AssertionType.EQUALS, expected="N/A")],
        )],
    )
