"""进化闭环 API — 知识库查询、策略推荐、跨项目迁移"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from backend.core.self_evolution import evolution_loop

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])


class ExecutionResultItem(BaseModel):
    test_name: str = ""
    passed: bool = False
    duration_ms: int = 0
    error: str = ""
    strategy: str = ""
    heal_info: dict | None = None
    flaky_info: dict | None = None


class ExecutionCompleteRequest(BaseModel):
    project_id: str = "default"
    results: list[ExecutionResultItem] = []


class StrategyRecordRequest(BaseModel):
    project_id: str = "default"
    strategy: str
    case_count: int = 1
    duration_ms: int = 0


class HealRecordRequest(BaseModel):
    project_id: str = "default"
    layer: str
    original: str
    healed: str
    success: bool


class FlakyRecordRequest(BaseModel):
    project_id: str = "default"
    test_name: str
    flaky_score: float
    root_cause: str


class ComputeProjectHashRequest(BaseModel):
    project_id: str
    samples: list[dict] = []


class CrossProjectRequest(BaseModel):
    source_project: str
    all_projects: list[str]


@router.post("/execution-complete")
async def on_execution_complete(req: ExecutionCompleteRequest):
    """执行完成后触发进化闭环"""
    evolution_loop.set_project(req.project_id)
    results_dicts = [
        {
            "test_name": r.test_name,
            "passed": r.passed,
            "duration_ms": r.duration_ms,
            "error": r.error,
            "strategy": r.strategy,
            "heal_info": r.heal_info,
            "flaky_info": r.flaky_info,
        }
        for r in req.results
    ]
    outcome = await evolution_loop.on_execution_complete(results_dicts)
    return outcome


@router.post("/strategy-called")
async def on_strategy_called(req: StrategyRecordRequest):
    """记录策略调用"""
    evolution_loop.set_project(req.project_id)
    await evolution_loop.on_strategy_called(req.strategy, req.case_count, req.duration_ms)
    return {"status": "recorded"}


@router.post("/heal-event")
async def on_heal_event(req: HealRecordRequest):
    """记录自愈事件"""
    evolution_loop.set_project(req.project_id)
    await evolution_loop.on_heal_event(req.layer, req.original, req.healed, req.success)
    return {"status": "recorded"}


@router.post("/flaky-detected")
async def on_flaky_detected(req: FlakyRecordRequest):
    """记录 Flaky 检测事件"""
    evolution_loop.set_project(req.project_id)
    await evolution_loop.on_flaky_detected(req.test_name, req.flaky_score, req.root_cause)
    return {"status": "recorded"}


@router.get("/knowledge")
async def search_knowledge(
    query: str = Query(default="", description="搜索关键词"),
    category: str = Query(default="", description="知识类别"),
    limit: int = Query(default=20, le=100),
):
    """搜索进化知识库"""
    results = evolution_loop.search_knowledge(query=query, category=category, limit=limit)
    return {"total": len(results), "results": results}


@router.get("/strategies/recommended")
async def get_recommended_strategies():
    """获取策略推荐（按权重排序）"""
    strategies = evolution_loop.get_recommended_strategies()
    primary = strategies[0]["name"] if strategies else "template"
    return {"primary_strategy": primary, "strategies": strategies}


@router.get("/report")
async def get_evolution_report():
    """获取进化报告"""
    return evolution_loop.get_evolution_report()


@router.post("/cross-project/hash")
async def compute_project_hash(req: ComputeProjectHashRequest):
    """计算项目模式哈希"""
    from backend.core.self_evolution import ProjectTransfer
    transfer = ProjectTransfer(evolution_loop.db)
    hash_val = transfer.compute_project_hash(req.project_id, req.samples)
    return {"project_id": req.project_id, "project_hash": hash_val}


@router.post("/cross-project/recommendations")
async def get_cross_project_recommendations(req: CrossProjectRequest):
    """跨项目迁移推荐"""
    return evolution_loop.get_cross_project_recommendations(req.source_project, req.all_projects)


@router.get("/events")
async def get_events(
    event_type: str = Query(default="", description="事件类型"),
    project_id: str = Query(default="", description="项目ID"),
    limit: int = Query(default=50, le=200),
):
    """获取进化事件历史"""
    events = evolution_loop.db.get_recent_events(event_type=event_type, project_id=project_id, limit=limit)
    return {"total": len(events), "events": events}


@router.get("/stats")
async def get_evolution_stats():
    """进化引擎统计概览"""
    strategies = evolution_loop.get_recommended_strategies()
    knowledge_count = evolution_loop.knowledge_count()
    recent_events = evolution_loop.db.get_recent_events(limit=100)
    event_counts = {}
    for e in recent_events:
        t = e["event_type"]
        event_counts[t] = event_counts.get(t, 0) + 1
    return {
        "total_knowledge": knowledge_count,
        "strategies": strategies,
        "recent_events": event_counts,
        "total_events_100": len(recent_events),
    }
