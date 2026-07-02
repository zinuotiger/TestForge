"""测试设计器 — LLM 驱动的自然语言 → 测试用例生成

将需求描述解析为结构化 TestCase：
  1. 优先使用 LLM（DashScope/LiteLLM）智能理解需求
  2. 降级方案：关键词匹配（LLM 不可用时）
"""

import json
import logging
import re
from typing import Optional

from backend.models import TestCase, TestStep, TestType, StepType, Assertion, AssertionType
from backend.config import settings

logger = logging.getLogger("testforge")


class TestDesigner:
    """LLM 驱动的自然语言测试设计器

    两阶段策略：
      1. LLM 模式（默认）：将自然语言发给 LLM，让它生成结构化 TestCase JSON
      2. 关键词模式（降级）：LLM 不可用时，用关键词规则匹配
    """

    TYPE_KEYWORDS = {
        TestType.API: ["api", "接口", "endpoint", "rest", "http", "请求", "响应"],
        TestType.BOUNDARY: ["边界", "boundary", "异常值", "极限", "越界", "等价类"],
        TestType.E2E: ["e2e", "端到端", "流程", "登录", "下单", "结账", "browser"],
        TestType.PERFORMANCE: ["性能", "压测", "并发", "performance", "响应时间"],
        TestType.UNIT: ["单元", "unit", "函数", "方法", "代码"],
        TestType.FUNCTIONAL: ["功能", "functional", "验证", "测试"],
    }

    HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

    LLM_SYSTEM_PROMPT = """你是测试用例设计师。根据用户的自然语言需求描述，生成结构化的测试用例。

输出严格 JSON 数组，每个元素格式：
{
  "name": "用例名称（中文，简短）",
  "type": "api|unit|e2e|boundary|performance|functional",
  "steps": [
    {
      "type": "http_request|browser_action|code_exec|script|assertion",
      "description": "步骤描述",
      "request": {"method": "GET/POST", "url": "URL", "headers": {}, "body": {}},
      "action": "navigate/click/input",
      "query": "要执行的代码（code_exec/script 类型时必填）",
      "assertions": [{"type": "status|equals|contains|json_path", "expected": 200}]
    }
  ],
  "tags": ["标签"]
}

规则：
- type 根据需求推断：提到"接口/API/请求"用 api，提到"登录/流程/浏览器"用 e2e，提到"函数/代码/单元"用 unit
- 每个步骤 type 合理：HTTP 请求用 http_request，浏览器操作用 browser_action，代码执行用 code_exec
- assertions 必须具体：status 期望具体的 HTTP 状态码（如 200、400、404），equals 期望具体的值
- 异常路径（如"登录失败""错误输入"）生成 status 期望 401/400/422 的用例
- 中文名，英文 JSON key

只输出 JSON 数组。"""

    async def design_from_natural_language(
        self,
        description: str,
        base_url: str = "",
    ) -> list[TestCase]:
        """从自然语言描述生成测试用例
        
        Args:
            description: 自然语言需求，如 "用户登录的各种异常情况"
            base_url: 基础 URL（可选）
        """
        if not description or not description.strip():
            return []

        desc = description.strip()

        # 策略1: 尝试 LLM
        if settings.llm_api_key:
            try:
                cases = await self._design_via_llm(desc, base_url)
                if cases:
                    logger.info("LLM 生成 %d 个测试用例", len(cases))
                    return cases
            except Exception as e:
                logger.warning("LLM 测试设计失败，降级到关键词模式: %s", e)

        # 策略2: 关键词降级
        logger.info("使用关键词模式生成测试用例")
        return self._design_via_keywords(desc, base_url)

    async def _design_via_llm(self, desc: str, base_url: str) -> list[TestCase]:
        """LLM 驱动的测试设计"""
        import aiohttp

        url = f"{settings.llm_api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": self.LLM_SYSTEM_PROMPT},
                {"role": "user", "content": f"需求：{desc}\n基础URL：{base_url or '(无)'}\n请生成测试用例JSON数组："},
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
        }

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=body, headers=headers) as resp:
                data = await resp.json(content_type=None)
                content = data["choices"][0]["message"]["content"]
                return self._parse_llm_response(content, desc, base_url)

    def _parse_llm_response(self, content: str, desc: str, base_url: str) -> list[TestCase]:
        """解析 LLM 返回的 JSON → TestCase 列表"""
        content = content.strip()

        # 提取 JSON 数组
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 ```json ... ``` 块
            m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", content, re.DOTALL)
            if m:
                raw = json.loads(m.group(1))
            else:
                # 提取第一个 [...] 
                m = re.search(r"\[.*\]", content, re.DOTALL)
                if m:
                    raw = json.loads(m.group(0))
                else:
                    logger.warning("LLM 响应无法解析为 JSON: %s", content[:200])
                    return []

        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            return []

        cases = []
        for item in raw:
            try:
                test_type = self._infer_type(item.get("type", ""))
                steps = []
                for s in item.get("steps", []):
                    step_type = StepType(s.get("type", "script"))
                    assertions = []
                    for a in s.get("assertions", []):
                        atype = AssertionType(a.get("type", "equals"))
                        assertions.append(Assertion(
                            type=atype,
                            expected=a.get("expected"),
                            path=a.get("path"),
                        ))

                    steps.append(TestStep(
                        id=f"step_{len(steps)+1}",
                        type=step_type,
                        description=s.get("description", ""),
                        request=s.get("request") if s.get("request") else None,
                        action=s.get("action"),
                        query=s.get("query"),
                        assertions=assertions,
                    ))

                cases.append(TestCase(
                    name=item.get("name", desc[:60]),
                    type=test_type,
                    tags=item.get("tags", ["nl-generated"]) + ["llm-generated"],
                    created_by="ai",
                    steps=steps,
                ))
            except Exception as e:
                logger.warning("解析单条用例失败: %s", e)
                continue

        return cases

    def _design_via_keywords(self, desc: str, base_url: str) -> list[TestCase]:
        """关键词降级方案（原有逻辑）"""
        test_type = self._infer_type(desc)
        cases: list[TestCase] = []

        if test_type == TestType.API or self._has_url(desc):
            api_case = self._build_api_case(desc, base_url)
            if api_case:
                cases.append(api_case)

        if test_type == TestType.BOUNDARY:
            boundary_cases = self._build_boundary_cases(desc, base_url)
            cases.extend(boundary_cases)

        if not cases:
            cases.append(self._build_functional_case(desc))

        if any(k in desc for k in ["异常", "错误", "失败", "invalid", "error"]):
            cases.append(self._build_exception_case(desc, base_url))

        return cases

    def _infer_type(self, description: str) -> TestType:
        desc_lower = description.lower()
        for ttype, keywords in self.TYPE_KEYWORDS.items():
            if any(k in desc_lower for k in keywords):
                return ttype
        return TestType.FUNCTIONAL

    def _has_url(self, text: str) -> bool:
        return bool(re.search(r"https?://|/api/|/v\d+/", text))

    def _build_api_case(self, desc: str, base_url: str) -> Optional[TestCase]:
        url_match = re.search(r"(https?://[^\s，,。]+|/api/[^\s，,。]+)", desc)
        if not url_match:
            return None
        url = url_match.group(1)
        if base_url and url.startswith("/"):
            url = base_url.rstrip("/") + url
        method = "GET"
        for m in self.HTTP_METHODS:
            if m in desc.upper():
                method = m
                break

        step = TestStep(
            id="step1", type=StepType.HTTP_REQUEST,
            description=f"{method} {url}",
            request={"method": method, "url": url, "headers": {"Content-Type": "application/json"}},
            assertions=[Assertion(type=AssertionType.STATUS, expected=200)],
        )
        return TestCase(name=desc[:60], type=TestType.API, tags=["nl-generated", "api"], created_by="ai", steps=[step])

    def _build_boundary_cases(self, desc: str, base_url: str) -> list[TestCase]:
        from backend.core.boundary_engine import boundary_engine
        param_names = re.findall(r"参数[:：\s]*(\w+)", desc)
        if not param_names:
            param_names = ["value"]
        parameters = []
        for name in param_names[:3]:
            ptype = "integer" if re.search(r"数量|个数|年龄|id|count|age", name, re.I) else "string"
            parameters.append({"name": name, "type": ptype, "constraints": {}})
        expansion = boundary_engine.expand_for_test_case(parameters)
        cases = []
        for exp in expansion[:10]:
            step = TestStep(
                id="step1", type=StepType.HTTP_REQUEST,
                description=f"参数 {exp['parameter']}={exp['value']}",
                request={"method": "POST", "url": base_url or "/api/test", "body": {exp["parameter"]: exp["value"]}},
                assertions=[Assertion(type=AssertionType.STATUS, expected=exp["expected_status"])],
            )
            cases.append(TestCase(
                name=f"{desc[:30]} - {exp['reason']}", type=TestType.BOUNDARY,
                tags=["nl-generated", "boundary"], created_by="ai", steps=[step],
                boundary_expansion={"parameters": parameters, "generated_cases": [exp]},
            ))
        return cases

    def _build_functional_case(self, desc: str) -> TestCase:
        """构建功能测试用例"""
        step = TestStep(
            id="step1", type=StepType.SCRIPT,
            description=f"验证: {desc}",
            query=f"# 待实现: {desc} 的验证逻辑",
            assertions=[Assertion(type=AssertionType.EQUALS, expected=True)],
        )
        return TestCase(name=desc[:60], type=TestType.FUNCTIONAL, tags=["nl-generated", "functional"], created_by="ai", steps=[step])

    def _build_exception_case(self, desc: str, base_url: str) -> TestCase:
        step = TestStep(
            id="step1", type=StepType.HTTP_REQUEST,
            description=f"异常路径: {desc}",
            request={"method": "POST", "url": base_url or "/api/test", "body": {"invalid": True}},
            assertions=[Assertion(type=AssertionType.STATUS, expected=400)],
        )
        return TestCase(name=f"{desc[:30]} - 异常路径", type=TestType.FUNCTIONAL, tags=["nl-generated", "exception"], created_by="ai", steps=[step])


# 全局单例
test_designer = TestDesigner()
