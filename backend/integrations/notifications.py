"""通知集成 — Slack / 钉钉 Webhook 推送

文档第二节横切面 C 自进化 + 第十四节 API 集成。
与 safety/notifier.py (邮件) 互补，覆盖 Slack/钉钉渠道。
"""

import logging
from datetime import datetime
from typing import Optional

import aiohttp

from backend.config import settings

logger = logging.getLogger("testforge")


class NotificationSender:
    """多渠道通知发送器（Slack / 钉钉）"""

    def __init__(
        self,
        slack_webhook: Optional[str] = None,
        dingtalk_webhook: Optional[str] = None,
    ):
        self.slack_webhook = slack_webhook or settings.slack_webhook_url
        self.dingtalk_webhook = dingtalk_webhook or settings.dingtalk_webhook_url

    def is_configured(self) -> dict:
        """检查各渠道配置状态"""
        return {
            "slack": bool(self.slack_webhook),
            "dingtalk": bool(self.dingtalk_webhook),
            "any": bool(self.slack_webhook or self.dingtalk_webhook),
        }

    async def send_execution_result(self, execution: dict, title: str = "TestForge") -> dict:
        """推送测试执行结果通知

        Args:
            execution: 执行结果 {status, total, passed, failed, duration_ms}
            title: 通知标题

        Returns:
            {"slack": {...}, "dingtalk": {...}}
        """
        status = execution.get("status", "unknown")
        total = execution.get("total", 0)
        passed = execution.get("passed", 0)
        failed = execution.get("failed", 0)
        duration = execution.get("duration_ms", 0)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        emoji = "✅" if failed == 0 else "⚠️"
        color = "#36a64f" if failed == 0 else "#dc2626"
        message = (
            f"{emoji} {title} 测试执行完成\n"
            f"状态: {status}\n"
            f"通过: {passed}/{total}\n"
            f"失败: {failed}\n"
            f"耗时: {duration}ms\n"
            f"时间: {now}"
        )

        results = {}
        if self.slack_webhook:
            results["slack"] = await self._send_slack(message, color, title)
        if self.dingtalk_webhook:
            results["dingtalk"] = await self._send_dingtalk(message, title)

        return results

    async def send_alert(self, severity: str, message: str, title: str = "TestForge 告警") -> dict:
        """推送告警通知

        Args:
            severity: critical | high | medium | low
            message: 告警内容
            title: 通知标题

        Returns:
            {"slack": {...}, "dingtalk": {...}}
        """
        emoji_map = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
        emoji = emoji_map.get(severity, "⚪")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"{emoji} [{severity.upper()}] {title}\n{message}\n时间: {now}"

        results = {}
        if self.slack_webhook:
            results["slack"] = await self._send_slack(full_msg, "#dc2626", title)
        if self.dingtalk_webhook:
            results["dingtalk"] = await self._send_dingtalk(full_msg, title)
        return results

    # ---- 渠道发送 ----

    async def _send_slack(self, message: str, color: str, title: str) -> dict:
        """发送 Slack Incoming Webhook"""
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "text": message,
                    "ts": int(datetime.now().timestamp()),
                }
            ]
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    ok = resp.status == 200
                    text = await resp.text()
                    if not ok:
                        logger.warning("Slack 通知失败: %s %s", resp.status, text)
                    return {"success": ok, "status": resp.status, "response": text[:200]}
        except Exception as e:
            logger.error("Slack 通知异常: %s", e)
            return {"success": False, "error": str(e)}

    async def _send_dingtalk(self, message: str, title: str) -> dict:
        """发送钉钉机器人消息"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{message}",
            },
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.dingtalk_webhook, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    ok = resp.status == 200
                    text = await resp.text()
                    if not ok:
                        logger.warning("钉钉通知失败: %s %s", resp.status, text)
                    return {"success": ok, "status": resp.status, "response": text[:200]}
        except Exception as e:
            logger.error("钉钉通知异常: %s", e)
            return {"success": False, "error": str(e)}


# 全局单例
notifier = NotificationSender()
