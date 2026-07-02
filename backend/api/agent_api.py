"""Agent + RAG + 定时巡检 + BrowserAgent + E2E API 路由"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any

from backend.core.agent import TestAgent
from backend.core.multi_agent import multi_agent_system
from backend.core.langgraph_agent import run_langgraph_agents, is_langgraph_available, build_langgraph_workflow
from backend.core.streaming_agent import stream_agent_run
from backend.core.rag import vector_store, generate_with_rag, embedding_model
from backend.core.scheduler import scan_scheduler, ScanTask
from backend.safety.auth import get_current_user
from backend.executors.browser_executor import (
    is_playwright_available, check_browser_status, execute_browser_test,
)

router = APIRouter()


# ==== 单 Agent（ReAct 模式）====

class AgentRequest(BaseModel):
    code: str
    task: str = ""


@router.post("/agent/run")
async def run_agent(req: AgentRequest, user: str = Depends(get_current_user)):
    """启动单 Agent 自主测试（ReAct + Function Calling）"""
    agent = TestAgent(max_iterations=8)
    result = await agent.run(req.code, req.task)
    return result


@router.post("/agent/stream")
async def stream_agent(req: AgentRequest, user: str = Depends(get_current_user)):
    """流式运行 Agent — SSE 实时推送思考过程"""
    return StreamingResponse(
        stream_agent_run(req.code, req.task, max_iterations=8),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==== 多 Agent 协作（自研框架）====

class MultiAgentRequest(BaseModel):
    code: str
    task: str = ""


@router.post("/multi-agent/run")
async def run_multi_agent(req: MultiAgentRequest, user: str = Depends(get_current_user)):
    """启动多 Agent 协作测试（自研框架）"""
    multi_agent_system.reset()
    result = await multi_agent_system.run(req.code, req.task)
    return result


@router.get("/multi-agent/status")
async def multi_agent_status():
    """获取多 Agent 系统状态"""
    return multi_agent_system.get_statuses()


# ==== LangGraph 多 Agent（StateGraph）====

@router.get("/langgraph/available")
async def langgraph_available():
    """检查 LangGraph 是否可用"""
    return {
        "available": is_langgraph_available(),
        "framework": "langgraph" if is_langgraph_available() else "builtin",
    }


@router.get("/langgraph/structure")
async def langgraph_structure():
    """获取 LangGraph 工作流结构（供前端可视化）"""
    if not is_langgraph_available():
        return {"available": False, "framework": "builtin"}
    return {
        "available": True,
        "framework": "langgraph",
        "nodes": [
            {"id": "analyze", "name": "Analyst", "icon": "🔍", "description": "代码结构/复杂度/依赖分析"},
            {"id": "generate", "name": "Generator", "icon": "🧬", "description": "测试用例生成（多策略）"},
            {"id": "execute", "name": "Executor", "icon": "⚡", "description": "测试执行 + 安全扫描"},
            {"id": "review", "name": "Reviewer", "icon": "🛡️", "description": "质量评分 + 反思反馈"},
            {"id": "increment_retry", "name": "Retry", "icon": "🔄", "description": "重试计数器（反思循环）"},
        ],
        "edges": [
            {"from": "START", "to": "analyze", "type": "linear"},
            {"from": "analyze", "to": "generate", "type": "linear"},
            {"from": "generate", "to": "execute", "type": "linear"},
            {"from": "execute", "to": "review", "type": "linear"},
            {"from": "review", "to": "END", "type": "conditional", "condition": "pass"},
            {"from": "review", "to": "increment_retry", "type": "conditional", "condition": "fail + retry < max"},
            {"from": "increment_retry", "to": "generate", "type": "linear"},
        ],
        "features": [
            "StateGraph 声明式编排",
            "条件边路由（审查通过/失败）",
            "反思循环（review → generate 重试）",
            "MemorySaver checkpoint（状态持久化）",
            "TypedDict 共享状态",
        ],
    }


@router.post("/langgraph/run")
async def run_langgraph(req: MultiAgentRequest, user: str = Depends(get_current_user)):
    """启动 LangGraph 多 Agent 测试"""
    result = await run_langgraph_agents(req.code, req.task)
    return result


# ==== RAG ====

class RAGRequest(BaseModel):
    code: str
    language: str = "python"
    function_name: str = ""


@router.post("/rag/generate")
async def rag_generate(req: RAGRequest, user: str = Depends(get_current_user)):
    """RAG 增强的测试生成（ChromaDB 语义检索 / TF-IDF 降级）"""
    try:
        return await generate_with_rag(req.code, req.language, req.function_name)
    except Exception as e:
        return {"generated_count": 0, "test_cases": [], "rag_context": {}, "error": str(e)}


@router.get("/rag/stats")
async def rag_stats():
    """RAG 向量库统计"""
    return vector_store.stats()


@router.post("/rag/reload")
async def rag_reload(user: str = Depends(get_current_user)):
    """从数据库重新加载测试用例到向量库"""
    from backend.core.rag import load_from_database
    load_from_database()
    return {"status": "reloading", "current_size": vector_store.size(), "backend": vector_store.backend_name}


@router.post("/rag/search")
async def rag_search(query: str = "", top_k: int = 5, user: str = Depends(get_current_user)):
    """手动检索向量库"""
    if not query:
        return {"results": [], "backend": vector_store.backend_name}
    results = vector_store.search(query, top_k=top_k)
    return {"results": results, "backend": vector_store.backend_name, "count": len(results)}


# ==== 定时巡检 ====

class ScheduleRequest(BaseModel):
    name: str
    url: str
    interval_minutes: int = 60
    base_url: str = ""
    alert_emails: list[str] = []


@router.post("/schedule/tasks")
async def create_schedule_task(req: ScheduleRequest, user: str = Depends(get_current_user)):
    """创建定时巡检任务"""
    import uuid
    task = ScanTask(
        task_id=str(uuid.uuid4())[:8],
        name=req.name,
        url=req.url,
        interval_minutes=req.interval_minutes,
        base_url=req.base_url,
        alert_emails=req.alert_emails,
    )
    scan_scheduler.add_task(task)
    return {"status": "created", "task": task.to_dict()}


@router.get("/schedule/tasks")
async def list_schedule_tasks():
    """列出所有定时任务"""
    return {"tasks": scan_scheduler.list_tasks()}


@router.delete("/schedule/tasks/{task_id}")
async def delete_schedule_task(task_id: str, user: str = Depends(get_current_user)):
    """删除定时任务"""
    scan_scheduler.remove_task(task_id)
    return {"status": "deleted", "task_id": task_id}


@router.get("/schedule/alerts")
async def list_alerts():
    """获取告警列表"""
    return {"alerts": scan_scheduler.get_alerts()}


# ============================================================
# BrowserAgent — AI 驱动浏览器操控（新增）
# ============================================================

class BrowserAgentRequest(BaseModel):
    """BrowserAgent 请求 — 自然语言驱动浏览器"""
    task: str                           # "打开 example.com，点击登录按钮，输入 admin/123456，验证跳转到首页"
    start_url: str = ""                 # 起始 URL（可选，LLM 可从 task 推断）
    max_steps: int = 12                 # 最大循环步数
    headless: bool = True               # 是否无头模式


@router.post("/browser-agent/run")
async def run_browser_agent(req: BrowserAgentRequest, user: str = Depends(get_current_user)):
    """BrowserAgent — 自然语言驱动浏览器

    核心能力:
      - ReAct 循环：截图+a11y树 → LLM 决策 → Playwright 执行 → 重复
      - 21 种动作：navigate/click/input/select/scroll/wait/assert/drag/visual_click 等
      - 视觉定位：VLM 分析截图找元素坐标（无需 selector）
      - AI 语义断言：LLM 判断"是否登录成功""是否跳转到首页"
      - 自愈：操作失败自动重试 2 次 + 备选策略
      - 记忆：持久化经验到 SQLite，下次执行参考
    """
    from backend.core.browser_agent import run_browser_agent as browser_agent_run
    result = await browser_agent_run(
        task=req.task,
        start_url=req.start_url,
        max_steps=req.max_steps,
        headless=req.headless,
    )
    return result.to_dict()


@router.post("/browser-multi-agent/run")
async def run_browser_multi_agent(req: BrowserAgentRequest, user: str = Depends(get_current_user)):
    """多 Agent 协作浏览器测试

    Analyst(分析) → Executor(执行) → Verifier(验证)
    适用于复杂业务流程测试。
    """
    from backend.core.browser_multi_agent import run_browser_multi_agent as multi_run
    result = await multi_run(
        task=req.task,
        start_url=req.start_url,
        max_steps=req.max_steps,
    )
    return result.to_dict()


@router.get("/browser-agent/status")
async def browser_agent_status():
    """检查 BrowserAgent 环境状态"""
    playwright_ok = is_playwright_available()
    browser_status = await check_browser_status() if playwright_ok else {
        "available": False, "status": "playwright_not_installed",
        "hint": "pip install playwright && playwright install chromium"
    }
    from backend.config import settings
    return {
        "playwright_available": playwright_ok,
        "browser_status": browser_status,
        "llm_configured": bool(settings.llm_api_key),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "features": {
            "visual_locate": bool(settings.llm_api_key),
            "ai_assert": True,
            "self_heal": True,
            "memory": True,
            "multi_agent": True,
        },
    }


# ==== Agent Memory（经验记忆库）====

@router.get("/agent-memory/stats")
async def agent_memory_stats():
    """Agent 经验记忆库统计"""
    from backend.core.agent_memory import agent_memory
    return agent_memory.stats()


class MemorySearchRequest(BaseModel):
    domain: str = ""
    key_contains: str = ""
    limit: int = 10


@router.post("/agent-memory/search")
async def agent_memory_search(req: MemorySearchRequest, user: str = Depends(get_current_user)):
    """搜索 Agent 历史经验"""
    from backend.core.agent_memory import agent_memory
    exps = agent_memory.search(
        domain=req.domain,
        key_contains=req.key_contains,
        limit=req.limit,
    )
    return {"count": len(exps), "results": [e.to_dict() for e in exps]}


# ==== E2E 浏览器测试（旧版，保留兼容）====

class E2ERequest(BaseModel):
    steps: list[dict]
    base_url: str = ""
    timeout: int = 30


@router.get("/e2e/status")
async def e2e_status():
    """检查 E2E 浏览器环境状态"""
    return await check_browser_status()


@router.post("/e2e/run")
async def e2e_run(req: E2ERequest, user: str = Depends(get_current_user)):
    """执行 E2E 浏览器测试"""
    return await execute_browser_test(req.steps, req.base_url, req.timeout)
