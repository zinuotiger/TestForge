"""脚本执行器 — Shell / Python 脚本沙箱执行

文档第二节 L3 执行层 6 种执行器之一。
带超时控制、危险命令拦截、输出捕获。
"""

import asyncio
import logging
import re
import time
from typing import Optional

logger = logging.getLogger("testforge")


# 危险命令模式（拒绝执行）
_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",            # rm -rf /
    r"\bmkfs\b",                  # 格式化磁盘
    r"\bdd\s+if=.*of=/dev/",      # dd 写入设备
    r":\(\)\s*\{\s*:\|:&\s*\};:", # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r">\s*/dev/sd[a-z]",          # 写入块设备
    r"\bcurl\s+.*\|\s*sh",        # curl | sh 远程执行
    r"\bwget\s+.*\|\s*sh",
]


class ScriptExecutor:
    """Shell/Python 脚本执行器（带安全防护）"""

    async def execute(
        self,
        script: str,
        language: str = "shell",      # shell | python
        timeout: int = 30,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        assertions: list[dict] = None,
    ) -> dict:
        """执行脚本并验证断言

        Args:
            script: 脚本内容
            language: shell 或 python
            timeout: 超时秒数
            cwd: 工作目录
            env: 环境变量
            assertions: 断言列表

        Returns:
            {
                "passed": bool,
                "exit_code": int,
                "stdout": str,
                "stderr": str,
                "duration_ms": int,
                "assertions": [{type, expected, actual, passed}],
                "error": str,
            }
        """
        result = {
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "duration_ms": 0,
            "assertions": [],
            "error": "",
        }

        # 安全校验
        safety = self._validate_script(script)
        if not safety["safe"]:
            result["error"] = safety["reason"]
            return result

        # 选择解释器
        if language == "python":
            cmd = ["python", "-c", script]
        else:
            cmd = ["sh", "-c", script]

        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                result["error"] = f"执行超时 ({timeout}s)"
                result["duration_ms"] = int((time.time() - start) * 1000)
                return result

            result["exit_code"] = proc.returncode
            result["stdout"] = stdout.decode("utf-8", errors="replace")[:5000]  # 截断
            result["stderr"] = stderr.decode("utf-8", errors="replace")[:2000]

        except FileNotFoundError:
            result["error"] = f"解释器未找到: {cmd[0]}"
            result["duration_ms"] = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            result["error"] = f"执行异常: {e}"
            result["duration_ms"] = int((time.time() - start) * 1000)
            return result

        result["duration_ms"] = int((time.time() - start) * 1000)

        # 验证断言
        all_passed = True
        for a in (assertions or []):
            a_result = self._check_assertion(a, result)
            result["assertions"].append(a_result)
            if not a_result["passed"]:
                all_passed = False

        # 若无断言，默认 exit_code == 0 即通过
        if not assertions:
            result["passed"] = result["exit_code"] == 0
        else:
            result["passed"] = all_passed

        return result

    # ---- 安全校验 ----

    def _validate_script(self, script: str) -> dict:
        """校验脚本安全性"""
        if not script or not script.strip():
            return {"safe": False, "reason": "空脚本"}

        for pattern in _DANGEROUS_PATTERNS:
            if re.search(pattern, script, re.IGNORECASE):
                return {"safe": False, "reason": f"检测到危险命令模式: {pattern}"}

        return {"safe": True, "reason": ""}

    # ---- 断言校验 ----

    def _check_assertion(self, assertion: dict, result: dict) -> dict:
        """检查脚本断言"""
        a_type = assertion.get("type", "exit_code")
        expected = assertion.get("expected")
        actual = None
        passed = False

        if a_type == "exit_code":
            actual = result["exit_code"]
            passed = actual == expected

        elif a_type == "stdout_contains":
            actual = result["stdout"]
            passed = str(expected) in actual

        elif a_type == "stdout_equals":
            actual = result["stdout"].strip()
            passed = actual == str(expected).strip()

        elif a_type == "stderr_contains":
            actual = result["stderr"]
            passed = str(expected) in actual

        elif a_type == "stdout_regex":
            actual = result["stdout"]
            try:
                passed = bool(re.search(expected, actual))
            except re.error:
                passed = False

        return {
            "type": a_type,
            "expected": expected,
            "actual": actual,
            "passed": passed,
        }


# 全局单例
script_executor = ScriptExecutor()
