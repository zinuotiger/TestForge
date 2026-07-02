"""报告 API — 基于真实执行记录，复用 reporter 模块"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from datetime import datetime
from backend.models.store import list_executions, list_tests
from backend.reporter import (
    generate_junit_xml,
    generate_json_report,
    generate_html_report,
    generate_coverage_badge,
    generate_score_badge,
    generate_pass_rate_badge,
    generate_allure_results,
)

router = APIRouter()


@router.get("/latest")
async def latest_report():
    """最新报告摘要（基于真实执行记录）"""
    executions = await list_executions(limit=100)
    tests = await list_tests()

    total = len(executions)
    passed = sum(1 for e in executions if e["status"] == "passed")
    failed = sum(1 for e in executions if e["status"] == "failed")
    errors = sum(1 for e in executions if e["status"] == "error")
    pass_rate = round(passed / total * 100, 1) if total else 0.0

    latest = executions[0] if executions else None
    timestamp = (
        (latest["completed_at"] or latest["started_at"])
        if latest else datetime.now().isoformat()
    )

    return {
        "timestamp": timestamp,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": pass_rate,
            "total_test_cases": len(tests),
        },
        "latest_run": latest,
        "recent_runs": executions[:10],
        "formats": ["html", "json", "junit"],
    }


@router.get("/html")
async def html_report():
    """HTML 报告（复用 reporter 模块，带样式和表格）"""
    executions = await list_executions(limit=100)
    tests = await list_tests()
    html = generate_html_report(executions, tests)
    return HTMLResponse(html)


@router.get("/json")
async def json_report():
    """JSON 报告（复用 reporter 模块）"""
    executions = await list_executions(limit=100)
    tests = await list_tests()
    json_str = generate_json_report(executions, tests)
    return Response(content=json_str, media_type="application/json")


@router.get("/junit")
async def junit_report():
    """JUnit XML 报告（复用 reporter 模块）"""
    executions = await list_executions(limit=100)
    xml_str = generate_junit_xml(executions)
    return PlainTextResponse(content=xml_str, media_type="application/xml")


@router.get("/badge/coverage")
async def coverage_badge():
    """覆盖率 SVG 徽章"""
    from backend.quality.coverage import collect_coverage

    cov = await collect_coverage("tests/", "backend/", timeout=60)
    pct = cov.get("coverage_pct", 0) if cov.get("status") == "completed" else 0
    svg = generate_coverage_badge(pct)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/badge/health")
async def health_badge():
    """健康度 SVG 徽章"""
    executions = await list_executions(limit=100)
    total = len(executions)
    passed = sum(1 for e in executions if e["status"] == "passed")
    score = (passed / total * 100) if total else 0
    svg = generate_score_badge(score, label="health")
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/badge/pass-rate")
async def pass_rate_badge():
    """通过率 SVG 徽章"""
    executions = await list_executions(limit=100)
    total = len(executions)
    passed = sum(1 for e in executions if e["status"] == "passed")
    svg = generate_pass_rate_badge(passed, total)
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/allure")
async def allure_report(output_dir: str = "testgen-reports/allure-results"):
    """生成 Allure 兼容结果文件"""
    executions = await list_executions(limit=200)
    result = generate_allure_results(executions, output_dir)
    return result


@router.get("/trend")
async def trend_report():
    """历史趋势数据（基于执行记录）"""
    executions = await list_executions(limit=500)
    # 按天聚合
    daily: dict[str, dict] = {}
    for e in executions:
        ts = e.get("started_at") or ""
        day = ts[:10] if ts else "unknown"
        if day not in daily:
            daily[day] = {"date": day, "total": 0, "passed": 0, "failed": 0}
        daily[day]["total"] += 1
        if e.get("status") == "passed":
            daily[day]["passed"] += 1
        elif e.get("status") == "failed":
            daily[day]["failed"] += 1

    trend = sorted(daily.values(), key=lambda x: x["date"])
    return {"trend": trend, "days": len(trend)}
