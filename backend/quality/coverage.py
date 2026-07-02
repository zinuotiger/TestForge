"""覆盖率收集器 — 基于 pytest-cov 真实覆盖率"""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path


async def collect_coverage(
    test_path: str,
    source_dir: str = ".",
    timeout: int = 120,
) -> dict:
    """执行 pytest --cov 并解析覆盖率 JSON 报告。

    返回:
        {
            "coverage_pct": float,
            "covered_lines": int,
            "total_lines": int,
            "missing_lines": int,
            "files": [{file, coverage_pct, covered, total, missing}],
            "status": "completed" | "unavailable" | "error",
            "error": str,
        }
    """
    test = Path(test_path)
    if not test.exists():
        return _empty_result("unavailable", f"测试路径不存在: {test_path}")

    source = Path(source_dir)
    cov_dir = tempfile.mkdtemp(prefix="testforge_cov_")
    cov_json = os.path.join(cov_dir, "coverage.json")

    try:
        return await _run_coverage(test, source, cov_json, cov_dir, timeout)
    finally:
        # 清理整个临时目录（不只是 json 文件）
        shutil.rmtree(cov_dir, ignore_errors=True)


async def _run_coverage(test: Path, source: Path, cov_json: str, cov_dir: str, timeout: int) -> dict:
    """执行 pytest --cov 并解析结果"""

    cmd = [
        "python", "-m", "pytest", str(test),
        f"--cov={source}",
        "--cov-report=json:" + cov_json,
        "--cov-report=term-missing",
        "-q", "--no-header", "--tb=short",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(source.parent),
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return _empty_result("error", "覆盖率收集超时")
    except FileNotFoundError:
        return _empty_result("unavailable", "pytest 未安装")

    if not os.path.exists(cov_json):
        return _empty_result("unavailable", "coverage.json 未生成（可能未安装 pytest-cov）")

    try:
        with open(cov_json, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return _empty_result("error", f"解析 coverage.json 失败: {e}")

    totals = data.get("totals", {})
    coverage_pct = round(totals.get("percent_covered", 0), 1)
    covered = totals.get("covered_lines", 0)
    total = totals.get("num_statements", 0)
    missing = totals.get("missing_lines", 0)

    files = []
    for fpath, fdata in data.get("files", {}).items():
        ftotals = fdata.get("summary", {})
        files.append({
            "file": fpath,
            "coverage_pct": round(ftotals.get("percent_covered", 0), 1),
            "covered": ftotals.get("covered_lines", 0),
            "total": ftotals.get("num_statements", 0),
            "missing": ftotals.get("missing_lines", 0),
        })
    files.sort(key=lambda x: x["coverage_pct"])

    return {
        "coverage_pct": coverage_pct,
        "covered_lines": covered,
        "total_lines": total,
        "missing_lines": missing,
        "files": files,
        "status": "completed",
        "error": "",
    }


def _empty_result(status: str, error: str) -> dict:
    return {
        "coverage_pct": 0,
        "covered_lines": 0,
        "total_lines": 0,
        "missing_lines": 0,
        "files": [],
        "status": status,
        "error": error,
    }


async def collect_coverage_data(source_code: str = "", timeout: int = 60) -> dict:
    """Agent 工具用：轻量级覆盖率收集（无需预存的测试文件）

    如果没有 source_code，尝试对当前项目的 backend/ 目录做覆盖率统计
    """
    if source_code:
        # 从源码提取可运行的部分做基本分析
        lines = source_code.split("\n")
        total_lines = len([l for l in lines if l.strip() and not l.strip().startswith("#")])
        return {
            "status": "estimated",
            "estimated_total_lines": total_lines,
            "hint": "完整覆盖率需在项目目录运行 pytest --cov。Agent 已生成测试代码，建议手动运行: pytest --cov=your_module test_file.py",
        }

    # 尝试对项目根目录跑覆盖率
    try:
        import os
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..")
        if os.path.exists(os.path.join(backend_path, "backend")):
            result = await collect_coverage(
                test_path=backend_path,
                source_dir=os.path.join(backend_path, "backend"),
                timeout=timeout,
            )
            return result
    except Exception as e:
        return {"status": "error", "error": str(e)}

    return {"status": "unavailable", "hint": "未找到可分析的源代码"} 
