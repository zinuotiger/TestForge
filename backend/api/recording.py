"""录制 API — 浏览器录制 + API 流量录制

文档第十四节: POST /record/browser/start, /record/browser/stop,
              POST /record/api/start, /record/api/stop
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.generator.recorder import browser_recorder
from backend.generator.traffic_generator import traffic_generator
from backend.safety.auth import get_current_user

logger = logging.getLogger("testforge")
router = APIRouter()


class BrowserRecordRequest(BaseModel):
    url: str = "about:blank"
    browser: str = "chromium"      # chromium | firefox | webkit


class APIRecordRequest(BaseModel):
    app_command: str = ""          # 如 "python app.py"
    port: int = 8080


@router.post("/browser/start")
async def start_browser_record(req: BrowserRecordRequest, user: str = Depends(get_current_user)):
    """开始浏览器录制（Playwright codegen）"""
    result = await browser_recorder.start_recording(
        url=req.url, browser=req.browser
    )
    if result.get("status") == "error":
        raise HTTPException(503, result["error"])
    return result


@router.post("/browser/stop")
async def stop_browser_record(session_id: str = "", user: str = Depends(get_current_user)):
    """停止浏览器录制并生成测试用例"""
    if not session_id:
        raise HTTPException(400, "缺少 session_id 参数")
    result = await browser_recorder.stop_recording(session_id)
    if result.get("status") == "error":
        raise HTTPException(404, result["error"])
    return result


@router.post("/api/start")
async def start_api_record(req: APIRecordRequest, user: str = Depends(get_current_user)):
    """开始 API 流量录制（Keploy eBPF）"""
    result = await traffic_generator.start_capture(
        app_command=req.app_command, port=req.port
    )
    if result.get("status") == "error":
        raise HTTPException(503, result["error"])
    return result


@router.post("/api/stop")
async def stop_api_record(session_id: str = "", user: str = Depends(get_current_user)):
    """停止 API 流量录制并生成测试用例"""
    if not session_id:
        raise HTTPException(400, "缺少 session_id 参数")
    result = await traffic_generator.stop_capture(session_id)
    if result.get("status") == "error":
        raise HTTPException(404, result["error"])
    return result


class ParseScriptRequest(BaseModel):
    script: str
    url: str = ""


@router.post("/browser/parse")
async def parse_recorded_script(req: ParseScriptRequest):
    """解析已录制的 Playwright 脚本为 TestCase（无需实时录制）"""
    tc = browser_recorder.parse_recorded_script(req.script, req.url)
    if not tc:
        raise HTTPException(400, "无法从脚本解析出测试步骤")
    return {"test_case": tc.model_dump()}


class ParseKeployRequest(BaseModel):
    yaml_content: str


@router.post("/api/parse")
async def parse_keploy_yaml(req: ParseKeployRequest):
    """解析 Keploy 录制的 YAML 为 TestCase 列表"""
    cases = traffic_generator.parse_keploy_yaml(req.yaml_content)
    if not cases:
        raise HTTPException(400, "未解析出测试用例")
    return {
        "generated_count": len(cases),
        "test_cases": [tc.model_dump() for tc in cases],
    }
