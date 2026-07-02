"""Token 用量 API — LLM 消耗统计与预算管理

文档第二十一节成本估算 + 第二十三节监控告警。
提供用量摘要、按模型/场景/提供商分组、趋势、定价表、预算设置。
"""

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.core.token_tracker import token_tracker
from backend.safety.auth import get_current_user

logger = logging.getLogger("testforge")
router = APIRouter()


class BudgetRequest(BaseModel):
    monthly_budget_usd: float


@router.get("/summary")
async def get_summary():
    """Token 用量总体摘要"""
    return token_tracker.get_summary()


@router.get("/by-model")
async def get_by_model():
    """按模型分组统计"""
    return {"models": token_tracker.get_by_model()}


@router.get("/by-scene")
async def get_by_scene():
    """按调用场景分组统计"""
    return {"scenes": token_tracker.get_by_scene()}


@router.get("/by-provider")
async def get_by_provider():
    """按提供商分组统计"""
    return {"providers": token_tracker.get_by_provider()}


@router.get("/trend")
async def get_trend(days: int = 30):
    """每日用量趋势"""
    return {"trend": token_tracker.get_daily_trend(days), "days": days}


@router.get("/recent")
async def get_recent(limit: int = 50):
    """最近调用记录"""
    return {"records": token_tracker.get_recent_records(limit), "count": limit}


@router.get("/pricing")
async def get_pricing():
    """模型定价表"""
    return {"pricing": token_tracker.get_model_pricing()}


@router.post("/budget")
async def set_budget(req: BudgetRequest, user: str = Depends(get_current_user)):
    """设置月度预算"""
    token_tracker.set_budget(req.monthly_budget_usd)
    return {
        "status": "updated",
        "monthly_budget_usd": req.monthly_budget_usd,
        "current_summary": token_tracker.get_summary(),
    }


@router.post("/reset")
async def reset_records(user: str = Depends(get_current_user)):
    """清空所有用量记录"""
    token_tracker.reset()
    return {"status": "cleared", "summary": token_tracker.get_summary()}
