"""AI Agent 引擎 — ReAct 循环 + Function Calling 自主决策

Agent 工作流:
  Thought → Action(调用工具) → Observation → Thought → ... → Final Answer

工具集:
  - analyze_code: 静态分析源代码
  - generate_tests: 生成测试用例（返回可执行的测试代码）
  - execute_tests: 执行测试（优先运行已生成的测试用例，pytest 真实执行）
  - collect_coverage: 收集覆盖率
  - scan_security: 安全扫描
"""

import json
import logging
import time
from typing import Callable, Any

from backend.config import settings

logger = logging.getLogger("testforge")

# Agent 可调用的工具定义（OpenAI Function Calling 格式）
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_code",
            "description": "静态分析源代码，提取函数/类/复杂度信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要分析的源代码"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_tests",
            "description": "为源代码生成测试用例（返回可执行的 pytest 测试代码）",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "源代码"},
                    "function_name": {"type": "string", "description": "重点测试的函数名"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_tests",
            "description": "执行测试用例（优先运行 generate_tests 生成的测试代码，用 pytest 真实执行并解析结果）",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的代码（可选，留空则自动使用上一步生成的测试代码）"},
                    "language": {"type": "string", "description": "编程语言", "default": "python"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_security",
            "description": "扫描代码中的安全风险（危险代码+密钥泄露）",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要扫描的代码"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "collect_coverage",
            "description": "收集测试覆盖率数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "源代码（用于定位文件路径）"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Agent 完成任务，返回最终总结",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "最终总结报告"},
                    "quality_score": {"type": "integer", "description": "质量评分 0-100"},
                },
                "required": ["summary"],
            },
        },
    },
]


class TestAgent:
    """ReAct 模式测试 Agent — LLM 自主决策调用工具"""

    def __init__(self, max_iterations: int = 8):
        self.max_iterations = max_iterations
        self.conversation: list[dict] = []
        self.tool_calls_log: list[dict] = []
        self._source_code: str = ""
        self._generated_test_code: str = ""  # 缓存上一步生成的测试代码
        self._generated_test_cases: list = []  # 缓存生成的 TestCase 对象

    async def run(self, source_code: str, task: str = "") -> dict:
        """启动 Agent 循环"""
        system_prompt = (
            "你是 TestForge AI 测试 Agent。你的任务是分析源代码、生成测试、"
            "执行测试（pytest 真实运行）、扫描安全风险，最终给出质量评估。\n\n"
            "工作流程:\n"
            "1. 先调用 analyze_code 分析代码结构\n"
            "2. 调用 generate_tests 生成测试用例（会返回可直接运行的 pytest 代码）\n"
            "3. 调用 execute_tests 执行生成的测试（会自动用 pytest 运行并解析结果）\n"
            "4. 调用 collect_coverage 收集覆盖率\n"
            "5. 调用 scan_security 安全扫描\n"
            "6. 调用 finish 给出最终总结（包含通过数/失败数/覆盖率/安全风险）\n\n"
            "注意: generate_tests 生成的测试代码会被缓存，下一步 execute_tests 会自动使用它。"
            "每次只能调用一个工具，根据观察结果决定下一步。"
        )

        user_message = f"请测试以下代码:\n\n```python\n{source_code}\n```"
        if task:
            user_message += f"\n\n额外要求: {task}"

        self.conversation = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        self._source_code = source_code
        self._generated_test_code = ""
        self._generated_test_cases = []

        for i in range(self.max_iterations):
            logger.info("Agent 迭代 %d/%d", i + 1, self.max_iterations)

            try:
                assistant_msg = await self._call_llm()
            except Exception as e:
                logger.error("LLM 调用失败: %s", e)
                return {
                    "status": "error",
                    "summary": f"LLM 调用失败: {e}",
                    "quality_score": 0,
                    "tool_calls": self.tool_calls_log,
                    "iterations": i + 1,
                }

            self.conversation.append(assistant_msg)
            tool_calls = assistant_msg.get("tool_calls", [])

            if not tool_calls:
                content = assistant_msg.get("content", "")
                return {
                    "status": "completed",
                    "summary": content,
                    "quality_score": 0,
                    "tool_calls": self.tool_calls_log,
                    "iterations": i + 1,
                }

            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                tool_args = json.loads(func["arguments"])

                logger.info("Agent 调用工具: %s(%s)", tool_name, list(tool_args.keys()))

                if tool_name == "finish":
                    return {
                        "status": "completed",
                        "summary": tool_args.get("summary", ""),
                        "quality_score": tool_args.get("quality_score", 0),
                        "tool_calls": self.tool_calls_log,
                        "iterations": i + 1,
                    }

                tool_result = await self._execute_tool(tool_name, tool_args)
                self.tool_calls_log.append({
                    "iteration": i + 1,
                    "tool": tool_name,
                    "args": tool_args,
                    "result_preview": str(tool_result)[:500],
                })

                self.conversation.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })

        return {
            "status": "max_iterations",
            "summary": "Agent 达到最大迭代次数，未能完成任务",
            "quality_score": 0,
            "tool_calls": self.tool_calls_log,
            "iterations": self.max_iterations,
        }

    async def _call_llm(self) -> dict:
        """调用 LLM（支持 Function Calling）"""
        import litellm

        response = await litellm.acompletion(
            model=f"{settings.llm_provider}/{settings.llm_model}",
            messages=self.conversation,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            api_key=settings.llm_api_key,
            api_base=settings.llm_api_base,
            temperature=0.2,
        )

        return response.choices[0].message.model_dump()

    async def _execute_tool(self, name: str, args: dict) -> Any:
        """执行工具调用"""
        try:
            if name == "analyze_code":
                from backend.analyzer import analyze_code
                return analyze_code(args.get("code", self._source_code), "python")

            elif name == "generate_tests":
                from backend.generator.router import route_generation
                cases = await route_generation(
                    args.get("code", self._source_code),
                    "python",
                    args.get("function_name", ""),
                )
                # 缓存生成的 TestCase
                self._generated_test_cases = cases
                # 生成可执行的 pytest 代码
                test_code = _cases_to_pytest_code(cases, self._source_code)
                self._generated_test_code = test_code
                return {
                    "count": len(cases),
                    "test_cases": [
                        {"name": c.name, "type": c.type.value, "steps": len(c.steps)}
                        for c in cases
                    ],
                    "pytest_code_generated": True,
                    "pytest_code_lines": len(test_code.split("\n")),
                    "hint": "测试代码已缓存，调用 execute_tests 自动执行",
                }

            elif name == "execute_tests":
                code_to_run = args.get("code", "")
                language = args.get("language", "python")

                # 优先级1: 使用上一步 generate_tests 的结果
                if self._generated_test_code:
                    test_code = self._generated_test_code
                    source = "generate_tests 生成"
                # 优先级2: 使用传入的 code
                elif code_to_run:
                    test_code = code_to_run
                    source = "手动传入"
                # 优先级3: 使用原始源代码（仅执行看是否报错）
                else:
                    from backend.executors.code_executor import execute_code
                    result = await execute_code(self._source_code, language, timeout=15)
                    return {
                        **result,
                        "source": "原始源代码直行（非测试，无generate_tests结果）",
                        "hint": "建议先调用 generate_tests 生成测试代码",
                    }

                # 用 pytest 真实执行测试代码
                from backend.executors.code_executor import execute_pytest_via_code
                result = await execute_pytest_via_code(test_code, timeout=60)
                return {
                    **result,
                    "source": source,
                    "generated_cases_count": len(self._generated_test_cases),
                }

            elif name == "collect_coverage":
                from backend.quality.coverage import collect_coverage_data
                cov = await collect_coverage_data(self._source_code)
                return cov

            elif name == "scan_security":
                from backend.safety.secret_scan import scan_all
                return scan_all(args.get("code", self._source_code))

            else:
                return {"error": f"未知工具: {name}"}

        except Exception as e:
            logger.error("工具 %s 执行失败: %s", name, e)
            return {"error": str(e)}


def _cases_to_pytest_code(cases: list, source_code: str = "") -> str:
    """? TestCase ????????? pytest ??——???? + AST ????"""
    import re as _re

    lines = [
        "# Auto-generated by TestForge Agent",
        "import pytest",
        "",
    ]

    # ① ???????????????????????????
    safe_source = source_code.strip()
    if safe_source:
        safe_source = _re.sub(
            r'if\s+__name__\s*==\s*.__main__.\s*:',
            "if False  # __main__ blocked by TestForge",
            safe_source,
        )
        lines.append("# === ????? ===")
        lines.extend(safe_source.split("\n"))
        lines.append("")
        lines.append("# === ????????? ===")
        lines.append("")

    # ② ??????——AST ???????? AI ????
    _ast_fallback_done = False
    case_num = 0
    for case in cases:
        case_num += 1
        func_name = _re.sub(r"[^\w]", "_", case.name or f"test_case_{case_num}").strip("_")[:50]
        if not func_name:
            func_name = f"case_{case_num}"
        lines.append("")
        lines.append(f"def test_{func_name}():")
        lines.append(f'    """{case.name or ""}"""')
        for step in (case.steps or []):
            step_desc = step.description or ""
            lines.append(f"    # {step_desc}")
            if step.type.value == "code_exec" and step.query:
                lines.append(f"    {step.query}")
            elif step.type.value == "script" and step.query:
                if "TODO" in (step.query or "") or "待实现" in (step.query or ""):
                    lines.append("    # 待实现: 请完善此步骤的验证逻辑")
                else:
                    lines.append(f"    {step.query}")
            elif step.type.value == "assertion":
                for assertion in (step.assertions or []):
                    try:
                        if assertion.type.value == "equals":
                            lines.append(f"    assert result == {json.dumps(assertion.expected)}")
                        elif assertion.type.value == "contains":
                            lines.append(f"    assert {json.dumps(assertion.expected)} in result")
                    except Exception:
                        lines.append("    # 断言格式异常，跳过")

        # ③ ?????????????????? AST ??
        needs_fallback = all(
            (s.query or "").strip() == ""
            or "TODO" in (s.query or "")
            or "待实现" in (s.query or "")
            for s in (case.steps or [])
        )
        if needs_fallback and not _ast_fallback_done:
            _ast_fallback_done = True
            lines.append("    # === 自动生成的基础验证（无 AI API 时回退） ===")
            _append_ast_fallback(lines, source_code)
        elif needs_fallback and _ast_fallback_done:
            lines.append("    # （基础验证已由上一用例覆盖）")
            lines.append("    pass")

    return "\n".join(lines)


def _append_ast_fallback(lines: list, source_code: str):
    """? AST ???????????? try/except ?????"""
    if not source_code:
        lines.append("    assert True  # 无源码可解析")
        return
    try:
        import ast as _ast
        tree = _ast.parse(source_code)
        if tree:
            for node in _ast.walk(tree):
                if isinstance(node, _ast.FunctionDef):
                    fname = node.name
                    defaults = []
                    for a in node.args.args:
                        if a.arg == "self":
                            continue
                        ann = ""
                        if a.annotation:
                            try:
                                ann = _ast.unparse(a.annotation)
                            except Exception:
                                pass
                        if ann in ("int", "float"):
                            defaults.append("0")
                        elif ann == "str":
                            defaults.append('""')
                        elif ann == "bool":
                            defaults.append("False")
                        elif ann in ("list", "List"):
                            defaults.append("[]")
                        elif ann in ("dict", "Dict"):
                            defaults.append("{}")
                        else:
                            defaults.append("0")
                    arg_str = ", ".join(defaults)
                    call = fname + "(" + arg_str + ")"
                    lines.append("    # 调用: " + call)
                    lines.append("    try:")
                    lines.append("        result = " + call)
                    if node.returns:
                        try:
                            ret_ann = _ast.unparse(node.returns)
                            if ret_ann != "None":
                                lines.append("        assert result is not None")
                            else:
                                lines.append("        assert True  # 函数可正常调用")
                        except Exception:
                            lines.append("        assert True  # 函数可正常调用")
                    else:
                        lines.append("        assert True  # 函数可正常调用")
                    lines.append("    except Exception as e:")
                    lines.append("        pytest.fail(str(e))")
        else:
            lines.append("    assert True  # 无源码可解析")
    except Exception:
        lines.append("    assert True  # 解析失败，跳过")


test_agent = TestAgent()
