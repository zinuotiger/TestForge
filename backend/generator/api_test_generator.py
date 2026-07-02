"""API 测试生成器 — 根据 OpenAPI 端点自动生成测试用例"""

import json
from typing import Any

from backend.models import (
    TestCase, TestStep, Assertion, AssertionType, StepType, TestType,
)
from backend.generator.openapi_parser import Endpoint, ApiSpec


def generate_api_tests(spec: ApiSpec, base_url: str = "") -> list[TestCase]:
    """根据 API 规范自动生成测试用例

    为每个端点生成:
      1. 正常请求（200/201）
      2. 边界值（空 body / 非法 ID）
      3. 方法不允许（405）— 仅对 GET/POST
    """
    base = base_url or spec.base_url
    cases: list[TestCase] = []

    for ep in spec.endpoints:
        # 1. 正常请求
        cases.append(_make_happy_path(base, ep))

        # 2. 边界测试
        if ep.method in ("POST", "PUT", "PATCH"):
            cases.append(_make_empty_body_test(base, ep))
        if "{id}" in ep.path or any(p.get("in") == "path" for p in ep.parameters):
            cases.append(_make_invalid_id_test(base, ep))

        # 3. 404 测试
        cases.append(_make_not_found_test(base, ep))

    return cases


def _make_happy_path(base_url: str, ep: Endpoint) -> TestCase:
    """正常请求测试"""
    url = _build_url(base_url, ep.path)
    request = {
        "method": ep.method,
        "url": url,
        "headers": {"Content-Type": "application/json"},
    }
    if ep.request_body:
        request["body"] = _generate_sample_body(ep.request_body)
    elif ep.method in ("POST", "PUT", "PATCH"):
        request["body"] = {}

    # 预期状态码
    expected_status = _infer_success_status(ep)

    return TestCase(
        name=f"[{ep.method}] {ep.path} — 正常请求",
        type=TestType.API,
        tags=["api", "happy_path"] + ep.tags,
        created_by="openapi",
        steps=[TestStep(
            id="step_1",
            type=StepType.HTTP_REQUEST,
            description=ep.summary or f"{ep.method} {ep.path}",
            request=request,
            assertions=[
                Assertion(type=AssertionType.STATUS, expected=expected_status),
            ],
        )],
    )


def _make_empty_body_test(base_url: str, ep: Endpoint) -> TestCase:
    """空 body 边界测试"""
    url = _build_url(base_url, ep.path)
    return TestCase(
        name=f"[{ep.method}] {ep.path} — 空请求体",
        type=TestType.API,
        tags=["api", "boundary", "empty_body"],
        created_by="openapi",
        steps=[TestStep(
            id="step_1",
            type=StepType.HTTP_REQUEST,
            description=f"空 body 测试: {ep.method} {ep.path}",
            request={
                "method": ep.method,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": "",
            },
            assertions=[
                Assertion(type=AssertionType.STATUS, expected=[400, 422]),
            ],
        )],
    )


def _make_invalid_id_test(base_url: str, ep: Endpoint) -> TestCase:
    """非法 ID 边界测试"""
    # 把路径参数替换为不存在的 ID
    path = ep.path
    for p in ep.parameters:
        if p.get("in") == "path":
            path = path.replace(f"{{{p['name']}}}", "99999999")
    url = _build_url(base_url, path)

    return TestCase(
        name=f"[{ep.method}] {ep.path} — 不存在的资源",
        type=TestType.API,
        tags=["api", "boundary", "not_found"],
        created_by="openapi",
        steps=[TestStep(
            id="step_1",
            type=StepType.HTTP_REQUEST,
            description=f"不存在的 ID: {ep.method} {path}",
            request={
                "method": ep.method,
                "url": url,
                "headers": {"Content-Type": "application/json"},
            },
            assertions=[
                Assertion(type=AssertionType.STATUS, expected=[404, 400]),
            ],
        )],
    )


def _make_not_found_test(base_url: str, ep: Endpoint) -> TestCase:
    """404 路径测试"""
    url = _build_url(base_url, ep.path) + "/nonexistent_deep_path"
    return TestCase(
        name=f"[{ep.method}] {ep.path} — 深层路径404",
        type=TestType.API,
        tags=["api", "boundary", "404"],
        created_by="openapi",
        steps=[TestStep(
            id="step_1",
            type=StepType.HTTP_REQUEST,
            description=f"404 测试: {ep.method} 深层路径",
            request={
                "method": ep.method,
                "url": url,
                "headers": {},
            },
            assertions=[
                Assertion(type=AssertionType.STATUS, expected=404),
            ],
        )],
    )


def _build_url(base: str, path: str) -> str:
    """拼接 base URL 和 path"""
    if path.startswith("http"):
        return path
    if not base:
        return path
    return base.rstrip("/") + "/" + path.lstrip("/")


def _infer_success_status(ep: Endpoint) -> int:
    """从 responses 推断成功状态码"""
    for code in ep.responses:
        if code.startswith("2"):
            return int(code)
    return 200 if ep.method == "GET" else 201


def _generate_sample_body(schema: dict) -> Any:
    """根据 schema 生成示例请求体"""
    if not isinstance(schema, dict):
        return {}

    # OpenAPI 3 requestBody 有 content 包装
    if "content" in schema:
        for media_type in schema["content"].values():
            if "schema" in media_type:
                return _generate_sample_body(media_type["schema"])
        return {}

    # 直接是 schema
    schema_type = schema.get("type", "object")
    properties = schema.get("properties", {})

    if schema_type == "object" and properties:
        result = {}
        for name, prop in properties.items():
            result[name] = _generate_sample_value(prop)
        return result

    return _generate_sample_value(schema)


def _generate_sample_value(prop: dict) -> Any:
    """根据属性 schema 生成示例值"""
    prop_type = prop.get("type", "string")
    fmt = prop.get("format", "")
    example = prop.get("example")

    if example is not None:
        return example

    if prop_type == "string":
        if fmt == "email":
            return "test@example.com"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt == "date":
            return "2026-01-01"
        if fmt == "date-time":
            return "2026-01-01T00:00:00Z"
        return "test_value"

    if prop_type == "integer":
        return 1
    if prop_type == "number":
        return 1.0
    if prop_type == "boolean":
        return True
    if prop_type == "array":
        return []
    if prop_type == "object":
        return {}

    return None
