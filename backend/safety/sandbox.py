"""Docker 沙箱执行器 — Docker 不可用时拒绝执行（不降级到本地）"""

import asyncio
import os
import tempfile
import subprocess
from backend.config import settings

try:
    import docker
    _has_docker = True
except ImportError:
    _has_docker = False


async def execute_in_sandbox(code: str, test_code: str = "", language: str = "python", timeout: int = 30) -> dict:
    """在沙箱中执行代码。

    安全策略：
    - sandbox_enabled=False: 用户显式关闭沙箱，允许本地执行（仅限隔离环境）
    - sandbox_enabled=True + Docker 可用: 在容器内执行
    - sandbox_enabled=True + Docker 不可用: 拒绝执行，返回错误（不再降级）
    """

    if not settings.sandbox_enabled:
        return await _execute_local(code, test_code, language, timeout)

    if not _docker_available():
        return {
            "exit_code": -1,
            "output": (
                "沙箱已启用但 Docker 不可用。请启动 Docker 服务，"
                "或在隔离环境中设置 TESTFORGE_SANDBOX_ENABLED=false 以允许本地执行。"
            ),
            "sandbox": "none",
        }

    if not _has_docker:
        return {"exit_code": -1, "output": "Docker SDK 未安装 (pip install docker)", "sandbox": "none"}

    client = docker.from_env()

    with tempfile.TemporaryDirectory() as tmpdir:
        code_path = os.path.join(tmpdir, f"source.{_ext(language)}")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)
        if test_code:
            test_path = os.path.join(tmpdir, f"test_source.{_ext(language)}")
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_code)

        image = _image(language)
        try:
            container = client.containers.run(
                image=image, command=_cmd(language, bool(test_code)),
                volumes={tmpdir: {"bind": "/code", "mode": "ro"}},
                working_dir="/code", mem_limit="512m",
                network_mode="none", read_only=True,
                tmpfs={"/tmp": "size=64m"},
                user="nobody", remove=True, detach=True,
            )
        except Exception as e:
            return {"exit_code": -1, "output": f"容器启动失败: {e}", "sandbox": "docker"}

        try:
            result = container.wait(timeout=timeout)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            return {"exit_code": result["StatusCode"], "output": logs[:5000], "sandbox": "docker"}
        except Exception:
            try:
                container.kill()
            except Exception:
                pass
            return {"exit_code": -1, "output": "执行超时", "sandbox": "docker"}


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=True)
        return True
    except Exception:
        return False


async def _execute_local(code: str, test_code: str, language: str, timeout: int) -> dict:
    """本地执行（仅在 sandbox_enabled=false 时调用）"""
    if language != "python":
        return {"exit_code": -1, "output": f"本地执行不支持 {language}，请安装 Docker", "sandbox": "local"}
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        if test_code:
            f.write("\n\n" + test_code)
        f.flush()
        tmpname = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", tmpname, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {"exit_code": proc.returncode or 0, "output": (stdout + stderr).decode("utf-8", errors="replace")[:5000], "sandbox": "local"}
    except asyncio.TimeoutError:
        proc.kill()
        return {"exit_code": -1, "output": "执行超时", "sandbox": "local"}
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass


def _ext(lang: str) -> str: return {"python": "py", "javascript": "js", "go": "go"}.get(lang, "txt")
def _image(lang: str) -> str: return {"python": "python:3.12-slim", "javascript": "node:22-slim", "go": "golang:1.23-slim"}.get(lang, "python:3.12-slim")
def _cmd(lang: str, has_test: bool) -> str:
    if lang == "python": return "python -m pytest test_source.py -v --tb=short 2>&1 || python source.py 2>&1" if has_test else "python source.py 2>&1"
    return "node source.js 2>&1"
