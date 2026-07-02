"""Keploy 流量录制集成 — eBPF API 流量捕获 + 测试用例转换"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("testforge")


async def check_keploy_available() -> dict:
    """检查 Keploy 是否可用"""
    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            "keploy", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
        return {"available": True, "status": "installed"}
    except (FileNotFoundError, asyncio.TimeoutError, OSError):
        return {"available": False, "status": "not_installed", "hint": "安装: curl -sSL https://keploy.io/install.sh | bash"}


async def record_traffic(app_cmd: str, duration: int = 60, output_dir: str = "keploy-reports") -> dict:
    """启动 Keploy 录制模式

    Args:
        app_cmd: 启动应用的命令（如 "node server.js"）
        duration: 录制时长（秒）
        output_dir: 录制输出目录

    Returns:
        {"status": "recording" | "completed" | "error", "output_dir": str, "count": int}
    """
    import asyncio
    available = await check_keploy_available()
    if not available["available"]:
        return {"status": "error", "error": available["hint"]}

    os.makedirs(output_dir, exist_ok=True)

    try:
        proc = await asyncio.create_subprocess_exec(
            "keploy", "record", "-c", app_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=output_dir,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=duration)
        except asyncio.TimeoutError:
            proc.terminate()
    except Exception as e:
        return {"status": "error", "error": str(e)}

    cases = parse_keploy_recordings(output_dir)
    return {"status": "completed", "output_dir": output_dir, "count": len(cases)}


def parse_keploy_recordings(recordings_dir: str) -> list[dict]:
    """解析 Keploy 录制文件为测试用例

    Keploy 录制格式: YAML 文件，包含请求/响应对
    """
    import yaml  # 延迟导入，避免无 yaml 时整个模块不可用

    cases = []
    rec_path = Path(recordings_dir)

    for yaml_file in rec_path.rglob("*.yaml"):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            continue

        if not isinstance(data, dict):
            continue

        for test in data.get("tests", []):
            req = test.get("request", {})
            resp = test.get("response", {})
            cases.append({
                "name": test.get("name", yaml_file.stem),
                "type": "api",
                "method": req.get("method", "GET"),
                "url": req.get("url", ""),
                "request_body": req.get("body", ""),
                "expected_status": resp.get("status_code", 200),
                "source": "keploy",
            })

    return cases


def recordings_to_testcases(recordings_dir: str) -> list[dict]:
    """将 Keploy 录制转换为 TestForge TestCase 格式"""
    raw = parse_keploy_recordings(recordings_dir)
    return [
        {
            "name": r["name"],
            "type": "api",
            "created_by": "keploy",
            "tags": ["traffic", "keploy"],
            "steps": [{
                "type": "http_request",
                "request": {
                    "method": r["method"],
                    "url": r["url"],
                    "body": r["request_body"],
                },
                "assertions": [
                    {"type": "status", "expected": r["expected_status"]},
                ],
            }],
        }
        for r in raw
    ]
