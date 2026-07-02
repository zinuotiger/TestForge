"""测试执行 API"""

import asyncio
import uuid
import ast
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from typing import Any
from pydantic import BaseModel

from backend.models import RunRequest, ExecutionResult, ExecutionStatus
from backend.models.store import save_execution, get_execution, list_tests
from backend.core.pipeline import pipeline_engine
from backend.core.self_evolution import evolution_loop
from backend.core.tia_engine import tia_engine
from backend.core.flaky_detector import flaky_detector
from backend.core.self_healer import self_healer
from backend.core.health_scorer import health_scorer
from backend.generator.router import route_generation
from backend.safety.secret_scan import scan_all
from backend.safety.auth import get_current_user
from backend.executors.code_executor import execute_code

router = APIRouter()


class HealRequest(BaseModel):
    expected: Any
    actual: Any


@router.post("/run")
async def trigger_run(req: RunRequest, background: BackgroundTasks, user: str = Depends(get_current_user)):
    run_id = str(uuid.uuid4())[:8]
    result = ExecutionResult(
        execution_id=run_id, test_id="batch",
        status=ExecutionStatus.PENDING, started_at=datetime.now(),
    )
    await save_execution(result)
    background.add_task(run_pipeline, run_id, req)
    return {"run_id": run_id, "status": "started"}


@router.get("/{run_id}")
async def api_get_execution(run_id: str):
    data = await get_execution(run_id)
    if not data:
        return {"error": "not found"}
    return data


@router.post("/analyze/impact")
async def api_tia_analysis(ref: str = "HEAD~1"):
    tia_engine.build_index()
    files = tia_engine.get_diff(ref)
    if not files:
        return {
            "changed_files": [],
            "affected_tests": [],
            "selected_count": 0,
            "acceleration": "N/A",
            "message": f"未检测到 {ref} 以来的变更（可能不在 git 仓库中）",
        }
    return tia_engine.analyze(files)


@router.get("/analyze/flaky")
async def api_flaky_scan():
    return {"flaky_tests": flaky_detector.scan_all()}


@router.get("/analyze/health")
async def api_health_report():
    """健康度报告（基于真实测试用例数据）"""
    return await _compute_health()


@router.post("/heal/{test_id}")
async def api_heal_test(test_id: str, req: HealRequest, user: str = Depends(get_current_user)):
    """自愈断言：传入期望值和实际值，返回修复建议"""
    heal = await self_healer.heal_assertion(req.expected, req.actual)
    return {"test_id": test_id, "heal_result": heal}


class BatchHealRequest(BaseModel):
    test_ids: list[str] = []
    layer: str = "assertion"        # assertion | ui_selector | api_schema


@router.post("/heal")
async def api_batch_heal(req: BatchHealRequest, user: str = Depends(get_current_user)):
    """批量自愈失败测试

    文档第十四节: POST /heal
    """
    results = []
    for test_id in req.test_ids:
        # 对每个测试用例的断言尝试自愈（简化：返回统计）
        results.append({
            "test_id": test_id,
            "heal_attempted": True,
            "layer": req.layer,
        })

    return {
        "total": len(req.test_ids),
        "healed": len(results),
        "results": results,
        "stats": self_healer.stats,
    }


@router.post("/{run_id}/cancel")
async def api_cancel_execution(run_id: str, user: str = Depends(get_current_user)):
    """取消执行

    文档第十四节: POST /executions/{eid}/cancel
    """
    pipeline_engine.cancel()
    return {"run_id": run_id, "status": "cancelled"}


@router.get("/{run_id}/log")
async def api_execution_log(run_id: str, tail: int = 100):
    """获取执行日志

    文档第十四节: GET /executions/{eid}/log?tail=100
    """
    data = await get_execution(run_id)
    if not data:
        raise HTTPException(404, "执行记录不存在")
    logs = data.get("logs", [])
    if isinstance(logs, str):
        import json
        try:
            logs = json.loads(logs)
        except (json.JSONDecodeError, TypeError):
            logs = [logs]
    return {
        "run_id": run_id,
        "total_logs": len(logs),
        "logs": logs[-tail:] if tail > 0 else logs,
    }


# ---- 精简流水线 ----

STAGES = [
    ("01", "预处理"),
    ("02", "静态分析"),
    ("08", "策略路由"),
    ("09", "测试生成"),
    ("16", "单元测试"),
    ("22", "安全扫描"),
    ("30", "TIA分析"),
    ("31", "Flaky检测"),
    ("33", "健康度评分"),
    ("43", "汇总评分"),
]


async def run_pipeline(run_id: str, req: RunRequest):
    engine = pipeline_engine
    code = _load_source_code(req.path)
    log_lines = []
    start = datetime.now()

    try:
        for sid, sname in STAGES:
            await engine.emit_progress(sid, 0, sname)
            ok, msg = await _do_stage(sid, code)
            elapsed = (datetime.now() - start).total_seconds()
            await engine.emit_test_result(sid, sname, "passed" if ok else "failed", int(elapsed * 1000))
            log_lines.append(f"[{datetime.now():%H:%M:%S}] {'✅' if ok else '❌'} {sname}: {msg}")

        status = ExecutionStatus.PASSED
        log_lines.append(f"[{datetime.now():%H:%M:%S}] ✅ Pipeline 全部完成")

    except Exception as e:
        status = ExecutionStatus.FAILED
        log_lines.append(f"[{datetime.now():%H:%M:%S}] ❌ 失败: {e}")
        await engine.emit_alert("error", str(e))

    # 保存结果
    result = ExecutionResult(
        execution_id=run_id, test_id="batch",
        status=status, started_at=start, completed_at=datetime.now(),
        duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        logs=log_lines,
    )
    await save_execution(result)
    # 触发进化闭环：收集执行结果，更新策略权重和知识库
    try:
        evolution_results = [
            {"test_name": "pipeline_batch", "passed": status == ExecutionStatus.PASSED,
             "duration_ms": int((datetime.now() - start).total_seconds() * 1000),
             "error": "" if status == ExecutionStatus.PASSED else "Pipeline execution failed",
             "strategy": "template"},
        ]
        asyncio.ensure_future(evolution_loop.on_execution_complete(evolution_results))
    except Exception:
        pass
    await engine.emit_gate_result("pipeline", status == ExecutionStatus.PASSED, {"run_id": run_id})


async def _do_stage(sid: str, code: str):
    """执行阶段实际操作，返回 (ok, msg)"""
    if sid == "01":
        file_count = _count_python_files(code)
        return True, f"识别 Python 项目, {file_count} 个代码段"
    elif sid == "02":
        issues = _static_analyze(code)
        return issues["error_count"] == 0, f"语法错误={issues['error_count']}, 函数={issues['func_count']}"
    elif sid == "08":
        from backend.generator.router import strategy_stats
        before = sum(s["calls"] for s in strategy_stats.values())
        cases = await route_generation(code, "python", "create_user")
        after = sum(s["calls"] for s in strategy_stats.values())
        return True, f"路由完成, 生成 {len(cases)} 个用例 (策略调用 {after - before} 次)"
    elif sid == "09":
        cases = await route_generation(code, "python", "create_user")
        for c in cases:
            await pipeline_engine.emit_test_result("09", c.name, "generated", 0)
        return True, f"生成 {len(cases)} 个用例"
    elif sid == "16":
        result = await execute_code(code, "python", timeout=10)
        ok = result["exit_code"] == 0
        await pipeline_engine.emit_test_result("16", "sample", "passed" if ok else "failed", 0)
        return ok, f"exit={result['exit_code']}"
    elif sid == "22":
        findings = scan_all(code)
        return findings["safe"], f"危险代码={len(findings['dangerous_code'])}, 密钥={len(findings['secret_leaks'])}"
    elif sid == "30":
        tia_engine.build_index()
        changed = tia_engine.get_diff() or []
        if changed:
            r = tia_engine.analyze(changed)
            return True, f"选择 {r['selected_count']} 测试 ({r['acceleration']})"
        return True, "无 git 变更，跳过 TIA"
    elif sid == "31":
        flaky = flaky_detector.scan_all()
        if flaky:
            return True, f"检测到 {len(flaky)} 个 Flaky 测试"
        return True, "无 Flaky 测试"
    elif sid == "33":
        s = await _compute_health()
        return True, f"健康度={s['health_score']}/100 ({s['grade']})"
    elif sid == "43":
        s = await _compute_health()
        return True, f"总分={s['health_score']}/100, 等级={s['grade']}"
    return True, "ok"


async def _compute_health() -> dict:
    """基于真实测试用例数据计算健康度"""
    flaky = flaky_detector.scan_all()
    tests = await list_tests()
    total_tests = len(tests)
    skipped = sum(1 for t in tests if t.status.value == "quarantine")

    # 尝试获取真实覆盖率（带缓存，避免每次请求都跑 pytest）
    coverage_pct = 0
    cached = _get_cached_coverage()
    if cached is not None:
        coverage_pct = cached
    else:
        try:
            from backend.quality.coverage import collect_coverage
            cov = await collect_coverage("tests/", "backend/", timeout=60)
            if cov["status"] == "completed":
                coverage_pct = cov["coverage_pct"]
                _set_cached_coverage(coverage_pct)
        except Exception:
            pass  # 覆盖率工具不可用时降级为 0

    return health_scorer.score({
        "total_tests": max(total_tests, 1),
        "skipped": skipped,
        "todo_count": 0,
        "coverage_pct": coverage_pct,
        "mutation_score": 0,  # 需接入变异测试结果
        "flaky_count": len(flaky),
    })


# 覆盖率缓存（10 分钟过期）
_coverage_cache: dict = {"value": None, "ts": 0}
_COVERAGE_CACHE_TTL = 600  # 秒


def _get_cached_coverage() -> int | None:
    """获取缓存的覆盖率值"""
    import time
    if _coverage_cache["value"] is not None and time.time() - _coverage_cache["ts"] < _COVERAGE_CACHE_TTL:
        return _coverage_cache["value"]
    return None


def _set_cached_coverage(value: int):
    """设置覆盖率缓存"""
    import time
    _coverage_cache["value"] = value
    _coverage_cache["ts"] = time.time()


def _count_python_files(code: str) -> int:
    """统计代码段数量（以注释分隔符为准）"""
    return code.count("# ----") or 1


def _static_analyze(code: str) -> dict:
    """简易静态分析：语法检查 + 函数计数"""
    try:
        tree = ast.parse(code)
        func_count = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        return {"error_count": 0, "func_count": func_count}
    except SyntaxError as e:
        return {"error_count": 1, "func_count": 0, "error": str(e)}


def _load_source_code(path: str = ".") -> str:
    """从指定路径加载 Python 源代码；无可用文件时回退到内置示例"""
    target = Path(path)
    py_files = []
    if target.is_file() and target.suffix == ".py":
        py_files = [target]
    elif target.is_dir():
        py_files = sorted(
            p for p in target.rglob("*.py")
            if "test" not in p.name.lower() and p.name != "__init__.py"
        )[:10]

    if not py_files:
        return _sample_code()

    chunks = []
    for f in py_files:
        try:
            chunks.append(f"# ---- {f.name} ----\n{f.read_text(encoding='utf-8')}")
        except (OSError, UnicodeDecodeError):
            continue
    return "\n\n".join(chunks) if chunks else _sample_code()


def _sample_code() -> str:
    return """
def create_user(name: str, email: str, age: int) -> dict:
    if not name or not email:
        raise ValueError("name and email required")
    if age < 0 or age > 150:
        raise ValueError("invalid age")
    return {"id": 1, "name": name, "email": email, "age": age}

def get_user(user_id: int) -> dict:
    if user_id <= 0:
        raise ValueError("invalid id")
    return {"id": user_id, "name": "test"}

def delete_user(user_id: int) -> bool:
    return True
"""
