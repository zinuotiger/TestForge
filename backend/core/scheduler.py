"""定时巡检调度器 — asyncio 后台定时执行网站测试 + 变更告警"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional

from backend.config import settings

logger = logging.getLogger("testforge")


class ScanTask:
    """定时扫描任务"""
    def __init__(
        self,
        task_id: str,
        name: str,
        url: str,
        interval_minutes: int = 60,
        base_url: str = "",
        alert_emails: list[str] = None,
    ):
        self.task_id = task_id
        self.name = name
        self.url = url
        self.interval = interval_minutes
        self.base_url = base_url
        self.alert_emails = alert_emails or []
        self.last_run: Optional[datetime] = None
        self.next_run: datetime = datetime.now()
        self.last_result: Optional[dict] = None
        self.last_pass_rate: Optional[float] = None
        self.enabled = True
        self.run_count = 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "url": self.url,
            "interval_minutes": self.interval,
            "base_url": self.base_url,
            "alert_emails": self.alert_emails,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat(),
            "last_pass_rate": self.last_pass_rate,
            "enabled": self.enabled,
            "run_count": self.run_count,
        }


class ScanScheduler:
    """定时巡检调度器"""

    def __init__(self):
        self._tasks: dict[str, ScanTask] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._alerts: list[dict] = []

    def add_task(self, task: ScanTask):
        """添加定时任务"""
        self._tasks[task.task_id] = task
        logger.info("定时任务已添加: %s (%s) 每 %d 分钟", task.name, task.task_id, task.interval)

    def remove_task(self, task_id: str):
        """移除定时任务"""
        self._tasks.pop(task_id, None)
        logger.info("定时任务已移除: %s", task_id)

    def get_task(self, task_id: str) -> Optional[ScanTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict]:
        return [t.to_dict() for t in self._tasks.values()]

    def get_alerts(self, limit: int = 20) -> list[dict]:
        return self._alerts[-limit:]

    def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._run_loop())
        logger.info("定时巡检调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("定时巡检调度器已停止")

    async def _run_loop(self):
        """主调度循环"""
        while self._running:
            try:
                now = datetime.now()
                for task in list(self._tasks.values()):
                    if not task.enabled:
                        continue
                    if now >= task.next_run:
                        await self._execute_task(task)
                        task.last_run = now
                        task.next_run = now + timedelta(minutes=task.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("调度循环异常: %s", e)

            await asyncio.sleep(30)  # 每 30 秒检查一次

    async def _execute_task(self, task: ScanTask):
        """执行单个扫描任务"""
        logger.info("执行定时扫描: %s → %s", task.name, task.url)

        try:
            from backend.generator.openapi_parser import parse_openapi_url
            from backend.generator.api_test_generator import generate_api_tests
            from backend.executors.http_executor import execute_api_tests

            spec = await parse_openapi_url(task.url)
            test_cases = generate_api_tests(spec, task.base_url)
            cases_data = [tc.model_dump() for tc in test_cases]
            base = task.base_url or spec.base_url
            execution = await execute_api_tests(cases_data, base)

            total = execution.get("total", 0)
            passed = execution.get("passed", 0)
            pass_rate = round(passed / total * 100, 1) if total else 0

            task.last_result = execution
            task.last_pass_rate = pass_rate
            task.run_count += 1

            # 检测通过率下降（变更告警）
            if task.last_pass_rate is not None and pass_rate < task.last_pass_rate - 10:
                alert = {
                    "timestamp": datetime.now().isoformat(),
                    "task_id": task.task_id,
                    "task_name": task.name,
                    "type": "pass_rate_drop",
                    "message": f"通过率从 {task.last_pass_rate}% 降至 {pass_rate}%",
                    "old_rate": task.last_pass_rate,
                    "new_rate": pass_rate,
                }
                self._alerts.append(alert)
                logger.warning("告警: %s", alert["message"])

                # 发送邮件告警
                if task.alert_emails:
                    await self._send_alert_email(task, alert)

            logger.info("定时扫描完成: %s — %d/%d 通过 (%.1f%%)",
                        task.name, passed, total, pass_rate)

        except Exception as e:
            logger.error("定时扫描失败 %s: %s", task.name, e)
            self._alerts.append({
                "timestamp": datetime.now().isoformat(),
                "task_id": task.task_id,
                "task_name": task.name,
                "type": "error",
                "message": str(e),
            })

    async def _send_alert_email(self, task: ScanTask, alert: dict):
        """发送告警邮件"""
        try:
            from backend.safety.notifier import is_email_configured, send_test_report_email
            if not is_email_configured():
                return
            send_test_report_email(
                to_emails=task.alert_emails,
                api_title=f"[告警] {task.name}",
                execution=task.last_result or {},
                scan_url=task.url,
            )
        except Exception as e:
            logger.error("告警邮件发送失败: %s", e)


# 全局调度器
scan_scheduler = ScanScheduler()
