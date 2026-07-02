"""测试用例 CRUD API — SQLite 持久化"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.models import TestCase, TestStatus
from backend.models.store import (
    list_tests, get_test, save_test, delete_test, quarantine_test,
)
from backend.safety.auth import get_current_user

router = APIRouter()


class NLCreateRequest(BaseModel):
    description: str
    base_url: str = ""


@router.get("/")
async def api_list_tests(status: str = "all", tags: str = ""):
    items = await list_tests(status, tags)
    return {"total": len(items), "items": items}


@router.get("/{test_id}")
async def api_get_test(test_id: str):
    tc = await get_test(test_id)
    if not tc:
        raise HTTPException(404, "测试用例不存在")
    return tc


@router.post("/")
async def api_create_test(test: TestCase, user: str = Depends(get_current_user)):
    await save_test(test)
    return {"id": test.id, "status": "created", "created_by": user}


@router.put("/{test_id}")
async def api_update_test(test_id: str, test: TestCase, user: str = Depends(get_current_user)):
    existing = await get_test(test_id)
    if not existing:
        raise HTTPException(404, "测试用例不存在")
    test.id = test_id
    await save_test(test)
    return {"id": test_id, "status": "updated"}


@router.delete("/{test_id}")
async def api_delete_test(test_id: str, user: str = Depends(get_current_user)):
    existing = await get_test(test_id)
    if not existing:
        raise HTTPException(404, "测试用例不存在")
    await delete_test(test_id)
    return {"id": test_id, "status": "deleted"}


@router.post("/{test_id}/quarantine")
async def api_quarantine_test(test_id: str, user: str = Depends(get_current_user)):
    existing = await get_test(test_id)
    if not existing:
        raise HTTPException(404, "测试用例不存在")
    await quarantine_test(test_id)
    return {"id": test_id, "status": "quarantined"}


@router.post("/{test_id}/clone")
async def api_clone_test(test_id: str, user: str = Depends(get_current_user)):
    """克隆测试用例"""
    existing = await get_test(test_id)
    if not existing:
        raise HTTPException(404, "测试用例不存在")
    cloned = existing.model_copy()
    # 生成新 ID 和名称
    from datetime import datetime
    cloned.id = f"tc_{datetime.now().strftime('%Y%m%d%H%M%S')}_clone"
    cloned.name = f"{existing.name} (副本)"
    cloned.flaky_score = 0.0
    cloned.health_score = 100.0
    await save_test(cloned)
    return {"id": cloned.id, "cloned_from": test_id, "status": "cloned"}


@router.post("/nl")
async def api_create_from_natural_language(req: NLCreateRequest, user: str = Depends(get_current_user)):
    """自然语言创建测试用例

    文档第十四节: POST /tests/nl
    Body: { "description": "用户登录的各种异常情况" }
    """
    from backend.core.designer import test_designer
    from backend.safety.prompt_guard import prompt_guard

    # Prompt 注入防护
    guard = prompt_guard.check_input(req.description)
    if not guard.safe and guard.risk_level in ("high", "critical"):
        raise HTTPException(400, f"输入含可疑内容: {guard.reason}")

    cases = test_designer.design_from_natural_language(
        req.description, req.base_url
    )
    saved = []
    for tc in cases:
        await save_test(tc)
        saved.append(tc.id)

    return {
        "description": req.description,
        "generated_count": len(cases),
        "test_ids": saved,
        "created_by": user,
    }
