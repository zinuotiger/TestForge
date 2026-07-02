"""浏览器录制器 — Playwright codegen 封装

文档第二节 L1 测试设计层：录制回放（浏览器操作 Playwright）。
启动录制 → 用户操作 → 生成 Playwright 脚本 → 转为 TestCase。
"""

import asyncio
import logging
import re
import tempfile
from pathlib import Path

from backend.models import TestCase, TestStep, StepType, Assertion, AssertionType, TestType

logger = logging.getLogger("testforge")


class BrowserRecorder:
    """浏览器录制器

    使用 Playwright codegen 录制用户操作，生成测试脚本。
    需要: pip install playwright && playwright install chromium
    """

    def __init__(self):
        self._active_sessions: dict[str, dict] = {}

    async def start_recording(
        self,
        url: str = "about:blank",
        browser: str = "chromium",     # chromium | firefox | webkit
        session_id: str = "",
    ) -> dict:
        """启动浏览器录制会话

        Args:
            url: 起始 URL
            browser: 浏览器类型
            session_id: 会话 ID（为空自动生成）

        Returns:
            {"session_id": str, "status": "recording", "url": str}
        """
        import uuid
        sid = session_id or str(uuid.uuid4())[:8]

        if not self._check_playwright():
            return {
                "session_id": sid,
                "status": "error",
                "error": "Playwright 未安装，请运行: pip install playwright && playwright install",
            }

        self._active_sessions[sid] = {
            "url": url,
            "browser": browser,
            "started_at": asyncio.get_event_loop().time(),
            "script_path": None,
        }

        # 实际启动 codegen 需要桌面环境，这里返回会话信息
        # 真正的录制在前端通过 Playwright browser ext 或 codegen CLI 完成
        logger.info("录制会话已启动: %s (url=%s)", sid, url)
        return {
            "session_id": sid,
            "status": "recording",
            "url": url,
            "browser": browser,
            "hint": "请在打开的浏览器窗口中操作，关闭窗口即结束录制",
        }

    async def stop_recording(self, session_id: str) -> dict:
        """停止录制并生成测试用例

        Args:
            session_id: 会话 ID

        Returns:
            {"session_id": str, "status": "completed", "test_case": dict}
        """
        session = self._active_sessions.get(session_id)
        if not session:
            return {"session_id": session_id, "status": "error", "error": "会话不存在"}

        # 读取录制脚本（实际由 codegen 写入）
        script_path = session.get("script_path")
        script = ""
        if script_path and Path(script_path).exists():
            script = Path(script_path).read_text(encoding="utf-8")

        # 将脚本转为 TestCase
        test_case = self._script_to_test_case(script, session["url"])

        del self._active_sessions[session_id]
        return {
            "session_id": session_id,
            "status": "completed",
            "script": script,
            "test_case": test_case.model_dump() if test_case else None,
        }

    def parse_recorded_script(self, script: str, url: str = "") -> TestCase | None:
        """解析 Playwright 录制脚本为 TestCase（公开方法）"""
        return self._script_to_test_case(script, url)

    # ---- 内部 ----

    def _check_playwright(self) -> bool:
        try:
            import shutil
            # 检查 npx playwright 或 playwright 模块
            return shutil.which("npx") is not None
        except Exception:
            return False

    def _script_to_test_case(self, script: str, url: str) -> TestCase | None:
        """将 Playwright 脚本解析为 TestCase"""
        if not script.strip():
            return None

        steps: list[TestStep] = []
        step_idx = 0

        # 解析 page.goto(url)
        for m in re.finditer(r'page\.goto\(["\']([^"\']+)["\']', script):
            step_idx += 1
            steps.append(TestStep(
                id=f"step{step_idx}",
                type=StepType.BROWSER_ACTION,
                description=f"导航到 {m.group(1)}",
                action="navigate",
                request={"url": m.group(1)},
                assertions=[
                    Assertion(type=AssertionType.STATUS, expected=200),
                ],
            ))

        # 解析 page.click(selector)
        for m in re.finditer(r'page\.click\(["\']([^"\']+)["\']', script):
            step_idx += 1
            steps.append(TestStep(
                id=f"step{step_idx}",
                type=StepType.BROWSER_ACTION,
                description=f"点击 {m.group(1)}",
                action="click",
                request={"selector": m.group(1)},
            ))

        # 解析 page.fill(selector, value)
        for m in re.finditer(r'page\.fill\(["\']([^"\']+)["\'],\s*["\']([^"\']*)["\']', script):
            step_idx += 1
            steps.append(TestStep(
                id=f"step{step_idx}",
                type=StepType.BROWSER_ACTION,
                description=f"在 {m.group(1)} 输入 {m.group(2)}",
                action="fill",
                request={"selector": m.group(1), "value": m.group(2)},
            ))

        # 解析 expect(page).to_have_title / to_contain_text
        for m in re.finditer(r'to_have_title\(["\']([^"\']+)["\']', script):
            if steps:
                steps[-1].assertions.append(
                    Assertion(type=AssertionType.CONTAINS, expected=m.group(1))
                )

        if not steps:
            # 无可解析步骤，整体作为脚本保存
            steps.append(TestStep(
                id="step1",
                type=StepType.SCRIPT,
                description="录制脚本",
                query=script,
            ))

        return TestCase(
            name=f"录制测试 - {url or 'browser'}",
            type=TestType.E2E,
            tags=["recorded", "browser"],
            created_by="recorded",
            steps=steps,
        )


# 全局单例
browser_recorder = BrowserRecorder()
