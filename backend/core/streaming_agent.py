"""流式 Agent — SSE 实时输出 LLM 思考过程

特性:
  - litellm.acompletion(stream=True) 逐 token 输出
  - SSE (Server-Sent Events) 推送到前端
  - 工具调用过程实时展示
  - ReAct 循环每一步都有事件

事件类型:
  - thought_start:  LLM 开始思考
  - token:          逐 token 输出
  - thought_end:    思考完成
  - tool_call:      调用工具
  - tool_result:    工具返回
  - iteration:      迭代信息
  - done:           完成
  - error:          错误
"""

import json
import time
import logging
from typing import AsyncGenerator

from backend.config import settings
from backend.core.agent import AGENT_TOOLS

logger = logging.getLogger("testforge")


async def stream_agent_run(
    source_code: str,
    task: str = "",
    max_iterations: int = 8,
) -> AsyncGenerator[str, None]:
    """流式运行 Agent，产出 SSE 格式事件

    Yields:
        SSE 格式字符串: "data: {json}\n\n"
    """
    import litellm

    def sse_event(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"

    system_prompt = (
        "你是 TestForge AI 测试 Agent。你的任务是分析源代码、生成测试、"
        "执行测试、扫描安全风险，最终给出质量评估。\n\n"
        "工作流程:\n"
        "1. 先调用 analyze_code 分析代码结构\n"
        "2. 调用 generate_tests 生成测试用例\n"
        "3. 调用 execute_tests 执行代码\n"
        "4. 调用 scan_security 安全扫描\n"
        "5. 调用 finish 给出最终总结\n\n"
        "每次只能调用一个工具，根据观察结果决定下一步。"
    )

    user_message = f"请测试以下代码:\n\n```python\n{source_code}\n```"
    if task:
        user_message += f"\n\n额外要求: {task}"

    conversation = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    yield sse_event("start", {"message": "Agent 启动", "max_iterations": max_iterations})

    for i in range(max_iterations):
        yield sse_event("iteration", {"current": i + 1, "max": max_iterations})

        # ---- 流式 LLM 调用 ----
        yield sse_event("thought_start", {"iteration": i + 1})

        full_content = ""
        tool_calls = None
        try:
            response = await litellm.acompletion(
                model=f"{settings.llm_provider}/{settings.llm_model}",
                messages=conversation,
                tools=AGENT_TOOLS,
                tool_choice="auto",
                api_key=settings.llm_api_key,
                api_base=settings.llm_api_base,
                temperature=0.2,
                stream=True,
            )

            # 逐 token 读取流
            current_tool_calls = {}
            async for chunk in response:
                delta = chunk.choices[0].delta

                # 内容 token
                if delta.content:
                    full_content += delta.content
                    yield sse_event("token", {"content": delta.content})

                # 工具调用（流式累积）
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            current_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                current_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                current_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

            # 转换工具调用格式
            if current_tool_calls:
                tool_calls = list(current_tool_calls.values())

        except Exception as e:
            logger.error("LLM 流式调用失败: %s", e)
            yield sse_event("error", {"message": f"LLM 调用失败: {e}"})
            return

        yield sse_event("thought_end", {
            "iteration": i + 1,
            "content": full_content[:500],
        })

        # 构建 assistant 消息
        assistant_msg = {"role": "assistant", "content": full_content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        conversation.append(assistant_msg)

        # ---- 没有工具调用 → 直接回复 ----
        if not tool_calls:
            yield sse_event("done", {
                "status": "completed",
                "summary": full_content,
                "iterations": i + 1,
            })
            return

        # ---- 执行工具 ----
        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            try:
                tool_args = json.loads(func["arguments"])
            except json.JSONDecodeError:
                tool_args = {}

            yield sse_event("tool_call", {
                "iteration": i + 1,
                "tool": tool_name,
                "args": list(tool_args.keys()),
            })

            # finish 工具
            if tool_name == "finish":
                yield sse_event("done", {
                    "status": "completed",
                    "summary": tool_args.get("summary", ""),
                    "quality_score": tool_args.get("quality_score", 0),
                    "iterations": i + 1,
                })
                return

            # 执行工具
            tool_result = await _execute_tool(tool_name, tool_args, source_code)

            yield sse_event("tool_result", {
                "iteration": i + 1,
                "tool": tool_name,
                "result_preview": str(tool_result)[:300],
            })

            conversation.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": json.dumps(tool_result, ensure_ascii=False, default=str),
            })

    # 达到最大迭代
    yield sse_event("done", {
        "status": "max_iterations",
        "summary": "Agent 达到最大迭代次数",
        "iterations": max_iterations,
    })


async def _execute_tool(name: str, args: dict, source_code: str) -> dict:
    """执行工具调用（复用 Agent 的工具逻辑）"""
    try:
        if name == "analyze_code":
            from backend.analyzer import analyze_code
            return analyze_code(args.get("code", source_code), "python")

        elif name == "generate_tests":
            from backend.generator.router import route_generation
            cases = await route_generation(
                args.get("code", source_code), "python", args.get("function_name", "")
            )
            return {
                "count": len(cases),
                "test_cases": [{"name": c.name, "type": c.type.value} for c in cases],
            }

        elif name == "execute_tests":
            from backend.executors.code_executor import execute_code
            return await execute_code(args.get("code", source_code), "python", timeout=15)

        elif name == "scan_security":
            from backend.safety.secret_scan import scan_all
            return scan_all(args.get("code", source_code))

        else:
            return {"error": f"未知工具: {name}"}

    except Exception as e:
        logger.error("工具 %s 执行失败: %s", name, e)
        return {"error": str(e)}
