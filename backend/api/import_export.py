"""导入/导出 API — 多格式测试用例导入导出

文档第十四节: POST /import, GET /export
文档第十五节: 已有测试导入（pytest/Jest/JUnit XML/Postman/OpenAPI/Playwright）
"""

import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from backend.models import TestCase, TestStep, StepType, Assertion, AssertionType, TestType
from backend.models.store import save_test, list_tests, get_test
from backend.safety.auth import get_current_user

logger = logging.getLogger("testforge")
router = APIRouter()


@router.post("/import")
async def import_tests(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    """导入已有测试（支持 pytest/Jest/JUnit XML/Postman/OpenAPI）

    文档第十五节: 自动识别格式并转为 TestCase
    """
    if not file.filename:
        raise HTTPException(400, "未提供文件名")

    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    filename = file.filename.lower()

    # 格式识别
    if filename.endswith(".py") or "def test_" in text:
        cases = _import_pytest(text)
    elif filename.endswith((".json")) and "item" in text:
        cases = _import_postman(text)
    elif filename.endswith((".yaml", ".yml")) and ("openapi" in text or "swagger" in text):
        cases = _import_openapi(text)
    elif filename.endswith(".xml") or "<testsuite" in text:
        cases = _import_junit_xml(text)
    elif filename.endswith((".js", ".ts")) and ("describe(" in text or "it(" in text):
        cases = _import_jest(text)
    else:
        raise HTTPException(400, f"无法识别文件格式: {filename}")

    saved_ids = []
    for tc in cases:
        await save_test(tc)
        saved_ids.append(tc.id)

    return {
        "filename": file.filename,
        "format": _detect_format(filename, text),
        "imported_count": len(cases),
        "test_ids": saved_ids,
    }


@router.get("/export")
async def export_tests(format: str = "yaml"):
    """导出所有测试用例

    文档第十四节: GET /export?format=yaml|json|junit
    """
    tests = await list_tests()

    if format == "json":
        data = [t.model_dump() for t in tests]
        return Response(
            content=json.dumps(data, ensure_ascii=False, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=testforge_export.json"},
        )
    elif format == "yaml":
        yaml_str = _tests_to_yaml(tests)
        return PlainTextResponse(
            content=yaml_str,
            media_type="text/yaml",
            headers={"Content-Disposition": "attachment; filename=testforge_export.yaml"},
        )
    elif format == "junit":
        from backend.reporter import generate_junit_xml
        executions = [
            {"execution_id": t.id, "test_id": t.id, "status": "passed", "duration_ms": 0}
            for t in tests
        ]
        xml = generate_junit_xml(executions)
        return PlainTextResponse(
            content=xml,
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=testforge_export.xml"},
        )
    else:
        raise HTTPException(400, f"不支持的导出格式: {format}")


# ---- 格式识别 ----

def _detect_format(filename: str, text: str) -> str:
    if filename.endswith(".py"):
        return "pytest"
    if filename.endswith((".yaml", ".yml")):
        return "openapi"
    if filename.endswith(".xml"):
        return "junit_xml"
    if "item" in text and "request" in text:
        return "postman"
    if "describe(" in text:
        return "jest"
    return "unknown"


# ---- pytest 导入 ----

def _import_pytest(source: str) -> list[TestCase]:
    """解析 pytest 测试文件

    规则: test_* 函数 → 测试用例，assert → 断言
    """
    cases = []
    # 匹配 def test_xxx():
    pattern = re.compile(r"(?:async\s+)?def\s+(test_\w+)\s*\(([^)]*)\)\s*:", re.MULTILINE)

    for m in pattern.finditer(source):
        func_name = m.group(1)
        # 提取函数体
        start = m.end()
        next_def = source.find("\ndef ", start)
        if next_def == -1:
            next_def = source.find("\nasync def ", start)
        body = source[start:next_def] if next_def != -1 else source[start:]

        # 提取 assert 语句
        assertions = []
        for am in re.finditer(r"assert\s+(.+?)(?:,\s*['\"](.+?)['\"])?\s*$", body, re.MULTILINE):
            expr = am.group(1).strip()
            assertions.append(Assertion(
                type=AssertionType.EQUALS,
                expected=expr,
            ))

        step = TestStep(
            id="step1",
            type=StepType.CODE_EXEC,
            description=f"pytest: {func_name}",
            query=body.strip()[:1000],
            assertions=assertions or [Assertion(type=AssertionType.STATUS, expected=0)],
        )

        cases.append(TestCase(
            name=func_name,
            type=TestType.UNIT,
            tags=["imported", "pytest"],
            created_by="imported",
            steps=[step],
        ))

    return cases


# ---- Postman 导入 ----

def _import_postman(json_text: str) -> list[TestCase]:
    """解析 Postman Collection JSON"""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Postman JSON 解析失败: {e}")

    cases = []

    def _walk_items(items):
        for item in items:
            if "item" in item:
                _walk_items(item["item"])
                continue
            request = item.get("request", {})
            method = request.get("method", "GET")
            url_raw = request.get("url", {})
            if isinstance(url_raw, dict):
                url = url_raw.get("raw", "")
            else:
                url = url_raw

            name = item.get("name", f"{method} {url[:30]}")
            headers = {}
            for h in request.get("header", []):
                headers[h.get("key", "")] = h.get("value", "")

            body = request.get("body", {}).get("raw")

            step = TestStep(
                id="step1",
                type=StepType.HTTP_REQUEST,
                description=name,
                request={
                    "method": method,
                    "url": url,
                    "headers": headers,
                    "body": json.loads(body) if body else None,
                },
                assertions=[Assertion(type=AssertionType.STATUS, expected=200)],
            )
            cases.append(TestCase(
                name=name[:60],
                type=TestType.API,
                tags=["imported", "postman"],
                created_by="imported",
                steps=[step],
            ))

    _walk_items(data.get("item", []))
    return cases


# ---- OpenAPI 导入 ----

def _import_openapi(yaml_text: str) -> list[TestCase]:
    """解析 OpenAPI/Swagger 生成 API 测试"""
    try:
        import yaml
        data = yaml.safe_load(yaml_text)
    except ImportError:
        raise HTTPException(500, "PyYAML 未安装")
    except Exception as e:
        raise HTTPException(400, f"OpenAPI 解析失败: {e}")

    cases = []
    base_url = ""
    servers = data.get("servers", [])
    if servers:
        base_url = servers[0].get("url", "")

    paths = data.get("paths", {})
    for path, methods in paths.items():
        for method, spec in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            url = base_url + path if base_url else path
            operation_id = spec.get("operationId", f"{method}_{path}")

            step = TestStep(
                id="step1",
                type=StepType.HTTP_REQUEST,
                description=spec.get("summary", operation_id),
                request={
                    "method": method.upper(),
                    "url": url,
                    "headers": {"Content-Type": "application/json"},
                },
                assertions=[Assertion(type=AssertionType.STATUS, expected=200)],
            )
            cases.append(TestCase(
                name=f"{operation_id}"[:60],
                type=TestType.API,
                tags=["imported", "openapi"],
                created_by="imported",
                steps=[step],
            ))

    return cases


# ---- JUnit XML 导入 ----

def _import_junit_xml(xml_text: str) -> list[TestCase]:
    """解析 JUnit XML 报告"""
    from xml.etree import ElementTree as ET

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise HTTPException(400, f"JUnit XML 解析失败: {e}")

    cases = []
    for testcase in root.iter("testcase"):
        name = testcase.get("name", "unknown")
        classname = testcase.get("classname", "")
        time_str = testcase.get("time", "0")

        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")

        if failure is not None:
            status_exp = "failed"
        elif error is not None:
            status_exp = "error"
        elif skipped is not None:
            status_exp = "skipped"
        else:
            status_exp = "passed"

        step = TestStep(
            id="step1",
            type=StepType.CODE_EXEC,
            description=f"{classname}.{name}",
            assertions=[Assertion(type=AssertionType.EQUALS, expected=status_exp)],
        )
        cases.append(TestCase(
            name=name[:60],
            type=TestType.UNIT,
            tags=["imported", "junit_xml"],
            created_by="imported",
            steps=[step],
        ))

    return cases


# ---- Jest 导入 ----

def _import_jest(source: str) -> list[TestCase]:
    """解析 Jest/Mocha 测试文件"""
    cases = []
    # describe → 套件, it/test → 用例
    it_pattern = re.compile(
        r"(?:it|test)\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*(?:async\s+)?\(?([^)]*)\)?\s*=>"
    )

    for m in it_pattern.finditer(source):
        name = m.group(1)
        start = m.end()
        # 简单提取函数体到下一个 it/describe
        next_it = source.find("it(", start)
        next_describe = source.find("describe(", start)
        end = min(x for x in [next_it, next_describe, len(source)] if x > 0)
        body = source[start:end]

        assertions = []
        for am in re.finditer(r"expect\((.+?)\)\.toBe\((.+?)\)", body):
            assertions.append(Assertion(type=AssertionType.EQUALS, expected=am.group(2)))

        step = TestStep(
            id="step1",
            type=StepType.CODE_EXEC,
            description=f"jest: {name}",
            query=body.strip()[:1000],
            assertions=assertions or [Assertion(type=AssertionType.STATUS, expected=0)],
        )
        cases.append(TestCase(
            name=name[:60],
            type=TestType.UNIT,
            tags=["imported", "jest"],
            created_by="imported",
            steps=[step],
        ))

    return cases


# ---- YAML 导出 ----

def _tests_to_yaml(tests: list[TestCase]) -> str:
    """将测试用例列表转为 YAML 文本"""
    lines = ["# TestForge 测试用例导出"]
    for tc in tests:
        lines.append(f"\n- id: \"{tc.id}\"")
        lines.append(f"  name: \"{tc.name}\"")
        lines.append(f"  type: {tc.type.value}")
        lines.append(f"  tags: {tc.tags}")
        lines.append(f"  status: {tc.status.value}")
        lines.append(f"  flaky_score: {tc.flaky_score}")
        lines.append(f"  health_score: {tc.health_score}")
        lines.append(f"  created_by: \"{tc.created_by}\"")
        if tc.steps:
            lines.append("  steps:")
            for s in tc.steps:
                lines.append(f"    - id: {s.id}")
                lines.append(f"      type: {s.type.value}")
                if s.description:
                    lines.append(f"      description: \"{s.description}\"")
                if s.request:
                    lines.append(f"      request: {json.dumps(s.request, ensure_ascii=False)}")
                if s.assertions:
                    lines.append("      assertions:")
                    for a in s.assertions:
                        lines.append(f"        - type: {a.type.value}")
                        lines.append(f"          expected: {a.expected}")
    return "\n".join(lines)
