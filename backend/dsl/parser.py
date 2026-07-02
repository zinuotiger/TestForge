"""测试场景 DSL 解析器 — YAML 格式测试定义

DSL 示例:
    name: 用户注册流程
    description: 完整注册+验证+登录
    variables:
      base_url: http://localhost:9876
    steps:
      - name: 注册
        request:
          method: POST
          url: /api/auth/register
          body: {username: testuser, password: Test1234}
        assert:
          - status: 201
          - jsonpath: $.user.id
            equals: not_null

      - name: 登录
        request:
          method: POST
          url: /api/auth/login
          body: {username: testuser, password: Test1234}
        extract:
          token: $.access_token
        assert:
          - status: 200
"""

import re
import yaml
from pathlib import Path
from backend.models import (
    TestCase, TestStep, Assertion, AssertionType, StepType, TestType,
)


def parse_dsl(dsl_str: str) -> TestCase:
    """解析 DSL 字符串为 TestCase"""
    data = yaml.safe_load(dsl_str)
    if not isinstance(data, dict):
        raise ValueError("DSL 根节点必须是字典")

    steps = []
    for i, step_data in enumerate(data.get("steps", [])):
        step = _parse_step(step_data, i)
        steps.append(step)

    return TestCase(
        name=data.get("name", "DSL测试场景"),
        type=TestType(data.get("type", "functional")),
        tags=data.get("tags", []),
        created_by="dsl",
        variables=data.get("variables", {}),
        steps=steps,
        boundary_expansion=data.get("boundary_expansion"),
        impact_analysis=data.get("impact_analysis"),
    )


def parse_dsl_file(filepath: str) -> TestCase:
    """从文件加载 DSL"""
    content = Path(filepath).read_text(encoding="utf-8")
    return parse_dsl(content)


def _parse_step(step_data: dict, index: int) -> TestStep:
    """解析单个步骤"""
    request = step_data.get("request", {})
    assertions = []

    for a in step_data.get("assert", []):
        assertions.append(_parse_assertion(a))

    # 判断步骤类型
    if "request" in step_data:
        step_type = StepType.HTTP_REQUEST
    elif "action" in step_data:
        step_type = StepType.BROWSER_ACTION
    elif "query" in step_data:
        step_type = StepType.DB_QUERY
    elif "code" in step_data:
        step_type = StepType.CODE_EXEC
    else:
        step_type = StepType.SCRIPT

    return TestStep(
        id=step_data.get("id", f"step_{index + 1}"),
        type=step_type,
        description=step_data.get("name") or step_data.get("description", ""),
        request=request if step_type == StepType.HTTP_REQUEST else None,
        action=step_data.get("action"),
        query=step_data.get("query"),
        assertions=assertions,
    )


def _parse_assertion(a: dict) -> Assertion:
    """解析断言定义"""
    if "status" in a:
        return Assertion(type=AssertionType.STATUS, expected=a["status"])
    elif "jsonpath" in a:
        if "equals" in a:
            return Assertion(type=AssertionType.JSON_PATH, path=a["jsonpath"], expected=a["equals"])
        elif "contains" in a:
            return Assertion(type=AssertionType.CONTAINS, path=a["jsonpath"], expected=a["contains"])
        elif "regex" in a:
            return Assertion(type=AssertionType.REGEX, path=a["jsonpath"], expected=a["regex"])
        else:
            return Assertion(type=AssertionType.JSON_PATH, path=a["jsonpath"])
    elif "equals" in a:
        return Assertion(type=AssertionType.EQUALS, expected=a["equals"])
    elif "contains" in a:
        return Assertion(type=AssertionType.CONTAINS, expected=a["contains"])
    elif "regex" in a:
        return Assertion(type=AssertionType.REGEX, expected=a["regex"])
    else:
        return Assertion(type=AssertionType.EQUALS, expected=str(a))


def validate_dsl(dsl_str: str) -> dict:
    """校验 DSL 语法，返回错误列表"""
    import yaml
    errors = []
    try:
        data = yaml.safe_load(dsl_str)
        if not isinstance(data, dict):
            return {"valid": False, "errors": ["DSL 根节点必须是字典"]}

        if not data.get("name"):
            errors.append("缺少 name 字段或 name 为空")

        steps = data.get("steps")
        if not steps:
            errors.append("没有定义任何 steps")
        else:
            for i, step in enumerate(steps):
                if not step.get("name") and not step.get("description"):
                    errors.append(f"步骤 {i+1} 缺少 name/description")
                if "request" in step and not step.get("request"):
                    errors.append(f"步骤 {i+1} 是 HTTP 请求但 request 为空")
    except yaml.YAMLError as e:
        errors.append(f"YAML 解析错误: {e}")
    except Exception as e:
        errors.append(str(e))

    return {"valid": len(errors) == 0, "errors": errors}
