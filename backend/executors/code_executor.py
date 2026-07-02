"""真实测试执行器 — 替换 sleep 模拟"""

import asyncio
import subprocess
import tempfile
import os
from pathlib import Path
from backend.config import settings


async def execute_pytest(
    test_file: str,
    source_file: str = "",
    timeout: int = 60,
) -> dict:
    """真实执行 pytest 并收集结果"""

    test_path = Path(test_file)
    if not test_path.exists():
        return {
            "exit_code": -1,
            "output": f"测试文件不存在: {test_file}",
            "total": 0, "passed": 0, "failed": 0, "coverage": 0,
        }

    try:
        # pytest --cov 如果源文件存在
        cmd = ["python", "-m", "pytest", str(test_path), "-v", "--tb=short", "--no-header"]

        if source_file and Path(source_file).exists():
            cmd.extend(["--cov=" + os.path.dirname(source_file), "--cov-report=json"])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(test_path.parent),
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"exit_code": -1, "output": "执行超时", "total": 0, "passed": 0, "failed": 0, "coverage": 0}

        output = (stdout + stderr).decode("utf-8", errors="replace")

        # 解析 pytest 输出
        return _parse_pytest_output(output, proc.returncode or 0)

    except FileNotFoundError:
        return {"exit_code": -1, "output": "pytest 未安装", "total": 0, "passed": 0, "failed": 0, "coverage": 0}


async def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
) -> dict:
    """执行代码片段"""

    if language == "python":
        return await _execute_python(code, timeout)
    elif language in ("javascript", "typescript"):
        return await _execute_node(code, timeout)
    return {"exit_code": -1, "output": f"不支持的语言: {language}"}


async def _execute_python(code: str, timeout: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        tmpname = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", tmpname,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "exit_code": proc.returncode or 0,
            "output": (stdout + stderr).decode("utf-8", errors="replace")[:5000],
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"exit_code": -1, "output": "执行超时"}
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass


async def _execute_node(code: str, timeout: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", f.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "exit_code": proc.returncode or 0,
                "output": (stdout + stderr).decode("utf-8", errors="replace")[:5000],
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"exit_code": -1, "output": "执行超时"}
        finally:
            os.unlink(f.name)


def _parse_pytest_output(output: str, exit_code: int) -> dict:
    """解析 pytest 输出"""
    import re

    # 解析通过/失败数
    passed = 0
    failed = 0
    total = 0

    # 匹配 "X passed, Y failed"
    match = re.search(r"(\d+)\s+passed", output)
    if match:
        passed = int(match.group(1))

    match = re.search(r"(\d+)\s+failed", output)
    if match:
        failed = int(match.group(1))

    total = passed + failed

    # 如果没有匹配到，尝试从末尾行解析
    if total == 0:
        for line in output.split("\n"):
            if "passed" in line and "failed" in line:
                m = re.search(r"(\d+)\s+passed.*?(\d+)\s+failed", line)
                if m:
                    passed = int(m.group(1))
                    failed = int(m.group(2))
                    total = passed + failed
                    break

    coverage = 0
    cov_match = re.search(r"TOTAL.*?(\d+)%", output)
    if cov_match:
        coverage = int(cov_match.group(1))

    return {
        "exit_code": exit_code,
        "output": output[-3000:],  # 截取最后 3000 字符
        "total": total,
        "passed": passed,
        "failed": failed,
        "coverage": coverage,
    }


async def execute_pytest_via_code(
    test_code: str,
    timeout: int = 60,
) -> dict:
    """将测试代码写入临时文件，用 pytest 真实执行并解析结果

    这是 Agent 闭环的核心：generate_tests 产生的代码 → pytest 真实运行 → 解析结果

    Args:
        test_code: 生成的 pytest 测试代码（含 import pytest / def test_xxx）
        timeout: 超时秒数

    Returns:
        {"exit_code": int, "output": str, "total": int, "passed": int, "failed": int, "details": str}
    """
    import tempfile, os

    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False, prefix="testforge_"
    ) as f:
        f.write(test_code)
        f.flush()
        tmpname = f.name

    try:
        cmd = ["python", "-m", "pytest", tmpname, "-v", "--tb=short", "--no-header", "-q"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"exit_code": -1, "output": "pytest 执行超时", "total": 0, "passed": 0, "failed": 0, "details": "超时"}

        output = (stdout + stderr).decode("utf-8", errors="replace")
        parsed = _parse_pytest_output(output, proc.returncode or 0)
        parsed["details"] = output[-2000:]
        return parsed

    except FileNotFoundError:
        return {"exit_code": -1, "output": "pytest 未安装 (pip install pytest)", "total": 0, "passed": 0, "failed": 0, "details": "pytest 未安装"}
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass
