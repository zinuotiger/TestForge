"""LangGraph 多 Agent 系统 — StateGraph + 节点 + 条件路由

架构对比（自研 vs LangGraph）:
  自研: Orchestrator 串行调用 Agent，消息传递
  LangGraph: StateGraph 声明式编排，节点 = Agent，边 = 条件路由

LangGraph 优势:
  1. 声明式状态图，可视化协作流程
  2. 内置 checkpoint（状态持久化 + 恢复）
  3. 条件边支持复杂路由（如审查不通过 → 回到生成）
  4. 流式输出支持（stream_mode="updates"）
  5. 与 LangChain 生态无缝集成

工作流:
  START → analyze → generate → execute → review
                                       │
                                   ┌───┴───┐
                                 pass     fail
                                   │       │
                                 END    regenerate (回到 generate，最多重试 2 次)
"""

import json
import time
import logging
from typing import TypedDict, Literal, Annotated, Optional
from operator import add

from backend.config import settings

logger = logging.getLogger("testforge")

# ============ LangGraph 可选导入 ============

try:
    from langgraph.graph import StateGraph, END, START
    from langgraph.checkpoint.memory import MemorySaver
    _HAS_LANGGRAPH = True
except ImportError:
    _HAS_LANGGRAPH = False
    logger.info("LangGraph 未安装，多 Agent 系统将使用自研框架降级。安装: pip install langgraph")

try:
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    _HAS_LANGCHAIN = True
except ImportError:
    _HAS_LANGCHAIN = False


# ============ 共享状态定义 ============

class AgentState(TypedDict):
    """LangGraph 共享状态 — 所有节点共享这个 dict

    每个节点读取需要的字段，写入结果字段。
    LangGraph 会自动合并状态更新。
    """
    # 输入
    source_code: str
    task_description: str

    # 分析结果
    analysis: dict
    risk_assessment: dict

    # 测试生成
    test_cases: list[dict]
    test_count: int

    # 执行结果
    execution_result: dict
    security_scan: dict

    # 审查结果
    quality_score: int
    review_passed: bool
    review_feedback: dict

    # 控制流
    retry_count: int
    max_retries: int

    # 可观测性
    timeline: Annotated[list[dict], add]   # 使用 add reducer，各节点追加事件
    current_node: str


# ============ 节点函数 ============

def _log_event(state: AgentState, node: str, action: str, detail: str):
    """记录时间线事件"""
    event = {
        "node": node,
        "action": action,
        "detail": detail,
        "timestamp": time.time(),
    }
    if "timeline" not in state:
        state["timeline"] = []
    state["timeline"].append(event)
    logger.info("[LangGraph:%s] %s: %s", node, action, detail)


def analyze_node(state: AgentState) -> dict:
    """分析师节点 — 代码结构/复杂度/依赖分析"""
    _log_event(state, "analyst", "start", "开始代码分析")
    code = state["source_code"]

    from backend.analyzer.static_analyzer import analyze_code
    analysis = analyze_code(code, "python")

    _log_event(
        state, "analyst", "complete",
        f"发现 {len(analysis.get('functions', []))} 函数, "
        f"{len(analysis.get('classes', []))} 类, 复杂度 {analysis.get('complexity', 0)}"
    )

    return {
        "analysis": analysis,
        "current_node": "analyst",
    }


def generate_node(state: AgentState) -> dict:
    """生成者节点 — 测试用例生成"""
    retry = state.get("retry_count", 0)
    feedback = state.get("review_feedback", {})

    if retry > 0:
        _log_event(state, "generator", "regenerate", f"根据反馈重新生成（第 {retry} 次重试）")
    else:
        _log_event(state, "generator", "start", "开始生成测试用例")

    code = state["source_code"]

    from backend.generator.router import route_generation
    import asyncio

    # route_generation 是 async，在同步节点中需要处理
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在 async 上下文中，创建新线程跑
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                test_cases = pool.submit(
                    asyncio.run, route_generation(code, "python", "")
                ).result(timeout=30)
        else:
            test_cases = loop.run_until_complete(route_generation(code, "python", ""))
    except RuntimeError:
        test_cases = asyncio.run(route_generation(code, "python", ""))

    cases_data = [
        {"name": tc.name, "type": tc.type.value, "steps": len(tc.steps)}
        for tc in test_cases
    ]

    _log_event(state, "generator", "complete", f"生成 {len(cases_data)} 个测试用例")

    return {
        "test_cases": cases_data,
        "test_count": len(cases_data),
        "current_node": "generator",
    }


def execute_node(state: AgentState) -> dict:
    """执行者节点 — 测试执行 + 安全扫描"""
    _log_event(state, "executor", "start", "开始执行测试")
    code = state["source_code"]

    from backend.executors.code_executor import execute_code
    from backend.safety.secret_scan import scan_all
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                exec_result = pool.submit(
                    asyncio.run, execute_code(code, "python", timeout=15)
                ).result(timeout=20)
        else:
            exec_result = loop.run_until_complete(execute_code(code, "python", timeout=15))
    except RuntimeError:
        exec_result = asyncio.run(execute_code(code, "python", timeout=15))

    security_result = scan_all(code)

    passed = exec_result.get("exit_code", -1) == 0
    _log_event(
        state, "executor", "complete",
        f"执行{'通过' if passed else '失败'}（exit={exec_result.get('exit_code', -1)}）"
    )

    return {
        "execution_result": exec_result,
        "security_scan": security_result,
        "current_node": "executor",
    }


def review_node(state: AgentState) -> dict:
    """审查者节点 — 质量评分 + 决定是否通过"""
    _log_event(state, "reviewer", "start", "开始质量审查")

    analysis = state.get("analysis", {})
    test_count = state.get("test_count", 0)
    execution = state.get("execution_result", {})
    security = state.get("security_scan", {})

    # 基于规则评分
    score = 0

    # 测试数量 (30分)
    if test_count >= 5:
        score += 30
    elif test_count >= 3:
        score += 20
    elif test_count >= 1:
        score += 10

    # 执行结果 (30分)
    if execution.get("exit_code") == 0:
        score += 30
    else:
        score += 10

    # 覆盖率估算 (20分)
    func_count = len(analysis.get("functions", []))
    if func_count > 0 and test_count > 0:
        score += int(20 * min(test_count / func_count, 1.0))
    else:
        score += 5

    # 安全 (20分)
    if not security.get("issues"):
        score += 20
    else:
        score += 10

    score = min(score, 100)
    passed = score >= 60

    # LLM 深度审查（可选）
    llm_feedback = {}
    if settings.llm_api_key and _HAS_LANGCHAIN:
        try:
            llm_feedback = _llm_review(state)
            if llm_feedback.get("score"):
                score = llm_feedback["score"]
                passed = score >= 60
        except Exception as e:
            _log_event(state, "reviewer", "llm_error", str(e))

    _log_event(state, "reviewer", "complete", f"评分 {score}/100 ({'通过' if passed else '未通过'})")

    return {
        "quality_score": score,
        "review_passed": passed,
        "review_feedback": llm_feedback or {
            "score": score,
            "issues": [] if passed else ["质量评分未达标"],
        },
        "current_node": "reviewer",
    }


def _llm_review(state: AgentState) -> dict:
    """LLM 深度审查"""
    import litellm

    system_prompt = """你是测试质量审查专家。综合评估测试质量，返回 JSON:
{"score": 0-100, "strengths": [], "weaknesses": [], "improvements": [], "verdict": "pass|fail"}"""

    user_msg = (
        f"分析: {json.dumps(state.get('analysis', {}), ensure_ascii=False, default=str)[:1000]}\n"
        f"测试数量: {state.get('test_count', 0)}\n"
        f"执行: {json.dumps(state.get('execution_result', {}), ensure_ascii=False, default=str)[:500]}"
    )

    response = litellm.completion(
        model=f"{settings.llm_provider}/{settings.llm_model}",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        api_key=settings.llm_api_key,
        api_base=settings.llm_api_base,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3]

    return json.loads(content.strip())


# ============ 条件路由 ============

def should_retry_or_finish(state: AgentState) -> Literal["regenerate", "finish"]:
    """审查后的条件路由

    - 通过 → finish
    - 未通过且重试次数 < 上限 → regenerate（回到 generate）
    - 未通过但重试次数已达上限 → finish（放弃）
    """
    if state.get("review_passed", False):
        return "finish"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if retry_count < max_retries:
        return "regenerate"
    return "finish"


def increment_retry(state: AgentState) -> dict:
    """重试计数器 +1（regenerate 路由经过的中间节点）"""
    return {"retry_count": state.get("retry_count", 0) + 1}


# ============ LangGraph 工作流构建 ============

def build_langgraph_workflow():
    """构建 LangGraph StateGraph 工作流

    图结构:
        START → analyze → generate → execute → review → [should_retry_or_finish]
                                                      ├─ finish → END
                                                      └─ regenerate → increment_retry → generate (循环)
    """
    if not _HAS_LANGGRAPH:
        return None

    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("review", review_node)
    workflow.add_node("increment_retry", increment_retry)

    # 添加边（线性流程）
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "generate")
    workflow.add_edge("generate", "execute")
    workflow.add_edge("execute", "review")

    # 条件边：审查后决定下一步
    workflow.add_conditional_edges(
        "review",
        should_retry_or_finish,
        {
            "finish": END,
            "regenerate": "increment_retry",
        },
    )

    # 重试循环：increment_retry → generate
    workflow.add_edge("increment_retry", "generate")

    # 编译（带 checkpoint 支持状态恢复）
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

    logger.info("LangGraph 工作流已构建: analyze → generate → execute → review → (retry|finish)")
    return app


# ============ 运行入口 ============

async def run_langgraph_agents(source_code: str, task_desc: str = "") -> dict:
    """运行 LangGraph 多 Agent 系统

    Returns:
        {
            "status": "completed",
            "framework": "langgraph",
            "quality_score": int,
            "review_passed": bool,
            "analysis": {...},
            "test_cases": [...],
            "execution_result": {...},
            "timeline": [...],
            "retry_count": int,
            "duration_ms": int,
        }
    """
    if not _HAS_LANGGRAPH:
        # 降级到自研多 Agent
        logger.info("LangGraph 不可用，降级到自研多 Agent 系统")
        from backend.core.multi_agent import multi_agent_system
        multi_agent_system.reset()
        result = await multi_agent_system.run(source_code, task_desc)
        result["framework"] = "builtin_fallback"
        return result

    start_time = time.time()
    app = build_langgraph_workflow()

    # 初始化状态
    initial_state: AgentState = {
        "source_code": source_code,
        "task_description": task_desc or "分析代码并生成、执行、审查测试",
        "analysis": {},
        "risk_assessment": {},
        "test_cases": [],
        "test_count": 0,
        "execution_result": {},
        "security_scan": {},
        "quality_score": 0,
        "review_passed": False,
        "review_feedback": {},
        "retry_count": 0,
        "max_retries": 2,
        "timeline": [],
        "current_node": "start",
    }

    # 运行工作流
    try:
        # LangGraph 的 invoke 是同步的，在 async 上下文中用线程跑
        import asyncio
        import concurrent.futures

        config = {"configurable": {"thread_id": f"testforge_{int(time.time())}"}}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    final_state = pool.submit(
                        app.invoke, initial_state, config
                    ).result(timeout=120)
            else:
                final_state = app.invoke(initial_state, config)
        except RuntimeError:
            final_state = app.invoke(initial_state, config)

    except Exception as e:
        logger.error("LangGraph 工作流执行失败: %s", e)
        return {
            "status": "error",
            "framework": "langgraph",
            "error": str(e),
            "duration_ms": int((time.time() - start_time) * 1000),
        }

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "status": "completed",
        "framework": "langgraph",
        "quality_score": final_state.get("quality_score", 0),
        "review_passed": final_state.get("review_passed", False),
        "analysis": {
            "function_count": len(final_state.get("analysis", {}).get("functions", [])),
            "class_count": len(final_state.get("analysis", {}).get("classes", [])),
            "complexity": final_state.get("analysis", {}).get("complexity", 0),
            "smells": len(final_state.get("analysis", {}).get("smells", [])),
        },
        "test_cases": final_state.get("test_cases", []),
        "test_count": final_state.get("test_count", 0),
        "execution_result": {
            "exit_code": final_state.get("execution_result", {}).get("exit_code", -1),
            "passed": final_state.get("execution_result", {}).get("exit_code", -1) == 0,
        },
        "review_feedback": final_state.get("review_feedback", {}),
        "retry_count": final_state.get("retry_count", 0),
        "timeline": final_state.get("timeline", []),
        "duration_ms": duration_ms,
        "graph_structure": {
            "nodes": ["analyze", "generate", "execute", "review", "increment_retry"],
            "edges": [
                "START → analyze",
                "analyze → generate",
                "generate → execute",
                "execute → review",
                "review → END (pass)",
                "review → increment_retry → generate (fail, retry)",
            ],
        },
    }


def is_langgraph_available() -> bool:
    """检查 LangGraph 是否可用"""
    return _HAS_LANGGRAPH
