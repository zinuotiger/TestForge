"""Allure 报告生成器 — 生成 Allure 兼容的 JSON 结果文件

文档第二节 L6 报告与集成层：Allure 报告。
生成 Allure 可识别的 JSON 测试结果，便于用 allure serve 渲染。
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("testforge")


def generate_allure_results(
    executions: list[dict],
    output_dir: str = "testgen-reports/allure-results",
) -> dict:
    """生成 Allure 兼容的 JSON 结果文件

    Args:
        executions: 执行记录列表
        output_dir: Allure 结果输出目录

    Returns:
        {"status": "completed", "files": int, "output_dir": str}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 清理旧结果
    for old in out.glob("*.json"):
        try:
            old.unlink()
        except OSError:
            pass

    count = 0
    for e in executions:
        result = _to_allure_result(e)
        fname = f"{result['uuid']}-result.json"
        with open(out / fname, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        count += 1

    logger.info("Allure 结果已生成: %d 个文件 → %s", count, output_dir)
    return {"status": "completed", "files": count, "output_dir": str(out)}


def _to_allure_result(execution: dict) -> dict:
    """将执行记录转为 Allure result JSON 格式"""
    status = _map_status(execution.get("status", ""))
    start_ms = _to_timestamp_ms(execution.get("started_at"))
    stop_ms = _to_timestamp_ms(execution.get("completed_at")) or start_ms
    duration = execution.get("duration_ms", 0)

    return {
        "uuid": str(uuid.uuid4()),
        "historyId": execution.get("execution_id", str(uuid.uuid4())),
        "name": execution.get("test_id", "unknown"),
        "fullName": f"testforge.{execution.get('test_id', 'batch')}",
        "status": status,
        "stage": "finished",
        "steps": _extract_steps(execution),
        "labels": [
            {"name": "suite", "value": "TestForge"},
            {"name": "framework", "value": "testforge"},
            {"name": "language", "value": "python"},
        ],
        "links": [],
        "start": start_ms,
        "stop": stop_ms or (start_ms + duration),
        "attachments": [],
        "parameters": [
            {"name": "duration_ms", "value": str(duration)},
        ],
    }


def _map_status(status: str) -> str:
    """映射执行状态到 Allure 状态"""
    mapping = {
        "passed": "passed",
        "failed": "failed",
        "error": "broken",
        "skipped": "skipped",
        "pending": "skipped",
        "running": "skipped",
    }
    return mapping.get(status, "unknown")


def _to_timestamp_ms(dt_str: str | None) -> int:
    """ISO 时间字符串转毫秒时间戳"""
    if not dt_str:
        return 0
    try:
        # 兼容多种格式
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(dt_str[:26] if "." in dt_str else dt_str[:19], fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
    except Exception:
        pass
    return 0


def _extract_steps(execution: dict) -> list[dict]:
    """从执行日志提取 Allure steps"""
    steps = []
    logs = execution.get("logs", [])
    if isinstance(logs, str):
        try:
            logs = json.loads(logs)
        except (json.JSONDecodeError, TypeError):
            logs = [logs]

    for i, log in enumerate(logs[:50]):  # 限制步数
        if not isinstance(log, str):
            continue
        steps.append({
            "name": log[:100],
            "status": "passed" if "✅" in log or "passed" in log.lower() else (
                "failed" if "❌" in log or "failed" in log.lower() else "passed"
            ),
            "stage": "finished",
            "start": 0,
            "stop": 0,
        })
    return steps
