"""HTTP 执行器 — 真实发送 HTTP 请求并验证断言"""

import asyncio
import logging
import time
from typing import Any

import aiohttp

logger = logging.getLogger("testforge")


async def execute_http_test(step: dict, timeout: int = 10) -> dict:
    """执行单个 HTTP 请求测试步骤

    Args:
        step: 包含 request 和 assertions 的步骤定义
        timeout: 请求超时（秒）

    Returns:
        {
            "passed": bool,
            "method": str,
            "url": str,
            "status": int,
            "response_body": str,
            "response_headers": dict,
            "duration_ms": int,
            "assertions": [{type, expected, actual, passed}],
            "error": str,
        }
    """
    request = step.get("request", {})
    assertions = step.get("assertions", [])
    method = request.get("method", "GET").upper()
    url = request.get("url", "")
    headers = request.get("headers", {})
    body = request.get("body")

    result = {
        "passed": False,
        "method": method,
        "url": url,
        "status": 0,
        "response_body": "",
        "response_headers": {},
        "duration_ms": 0,
        "assertions": [],
        "error": "",
    }

    if not url:
        result["error"] = "URL 为空"
        return result

    # 准备请求体
    json_body = None
    str_body = None
    if body is not None and body != "":
        if isinstance(body, (dict, list)):
            json_body = body
        else:
            str_body = str(body)

    start = time.time()

    try:
        timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body,
                data=str_body if str_body else None,
            ) as resp:
                result["status"] = resp.status
                result["response_headers"] = dict(resp.headers)
                text = await resp.text()
                result["response_body"] = text[:2000]  # 截断
    except asyncio.TimeoutError:
        result["error"] = f"请求超时 ({timeout}s)"
        result["duration_ms"] = int((time.time() - start) * 1000)
        return result
    except aiohttp.ClientError as e:
        result["error"] = f"请求失败: {e}"
        result["duration_ms"] = int((time.time() - start) * 1000)
        return result
    except Exception as e:
        result["error"] = f"未知错误: {e}"
        result["duration_ms"] = int((time.time() - start) * 1000)
        return result

    result["duration_ms"] = int((time.time() - start) * 1000)

    # 验证断言
    all_passed = True
    for a in assertions:
        a_result = _check_assertion(a, result)
        result["assertions"].append(a_result)
        if not a_result["passed"]:
            all_passed = False

    result["passed"] = all_passed
    return result


def _check_assertion(assertion: dict, response: dict) -> dict:
    """检查单个断言"""
    a_type = assertion.get("type", "status")
    expected = assertion.get("expected")
    actual = None
    passed = False

    if a_type == "status":
        actual = response["status"]
        if isinstance(expected, list):
            passed = actual in expected
        else:
            passed = actual == expected

    elif a_type == "json_path":
        path = assertion.get("path", "")
        actual = _extract_json_path(response["response_body"], path)
        if isinstance(expected, str) and expected == "not_null":
            passed = actual is not None
        else:
            passed = actual == expected

    elif a_type == "contains":
        actual = response["response_body"]
        passed = str(expected) in actual

    elif a_type == "equals":
        actual = response["response_body"]
        passed = str(expected) == actual

    return {
        "type": a_type,
        "expected": expected,
        "actual": actual,
        "passed": passed,
    }


def _extract_json_path(body: str, path: str) -> Any:
    """简易 JSON path 提取 ($.field.subfield)"""
    import json
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None

    if not path.startswith("$"):
        return None

    parts = path.lstrip("$").lstrip(".").split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


async def execute_api_tests(test_cases: list[dict], base_url: str = "", max_tests: int = 0) -> dict:
    """批量执行 API 测试用例（并发，限制数量）

    Returns:
        {
            "total": int,
            "passed": int,
            "failed": int,
            "duration_ms": int,
            "results": [执行结果],
        }
    """
    import time
    from backend.core.dependencies import get_execution_config

    # 从配置读取并发参数
    exec_config = get_execution_config()
    if max_tests <= 0:
        max_tests = exec_config.get("http_test_max_tests", 30)
    max_concurrency = exec_config.get("http_test_max_concurrency", 10)
    request_timeout = exec_config.get("http_test_timeout", 8)

    # 收集所有步骤
    all_steps = []
    for tc in test_cases:
        for step in tc.get("steps", []):
            request = step.get("request", {})
            url = request.get("url", "")
            if base_url and url and not url.startswith("http"):
                request["url"] = base_url.rstrip("/") + "/" + url.lstrip("/")
                step = {**step, "request": request}
            all_steps.append((step, tc.get("name", "")))

    # 限制测试数量避免超时
    all_steps = all_steps[:max_tests]

    start = time.time()
    # 并发执行
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run_one(step, name):
        async with semaphore:
            result = await execute_http_test(step, timeout=request_timeout)
            result["test_name"] = name
            return result

    tasks = [_run_one(step, name) for step, name in all_steps]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "duration_ms": int((time.time() - start) * 1000),
        "results": results,
    }
