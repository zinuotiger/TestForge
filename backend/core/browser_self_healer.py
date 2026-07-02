"""浏览器自愈引擎 — 弹窗/错误页/选择器失败的自动恢复

针对图片中"异常自恢复（弹窗/错误页重试）"需求：
  - 弹窗处理：自动 accept/dismiss alert/confirm/prompt
  - 错误页检测：401/403/404/500 → 标记为环境问题
  - 选择器失败：自动重试 + 备选策略
  - 页面崩溃：自动刷新重试
  - 记录所有自愈事件到日志，供前端可视化
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.core.self_healer import self_healer

logger = logging.getLogger("testforge")


class HealType(str, Enum):
    DIALOG = "dialog"
    ERROR_PAGE = "error_page"
    SELECTOR_FAIL = "selector_fail"
    NAVIGATION_FAIL = "navigation_fail"
    TIMEOUT = "timeout"
    CRASH = "crash"


@dataclass
class HealEvent:
    """一次自愈事件记录"""
    timestamp: float
    heal_type: HealType
    description: str
    success: bool
    retry_count: int = 0
    before: str = ""
    after: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "type": self.heal_type.value,
            "description": self.description,
            "success": self.success,
            "retry_count": self.retry_count,
            "before": self.before,
            "after": self.after,
            "error": self.error,
        }


@dataclass
class HealStats:
    """自愈统计"""
    total_events: int = 0
    heal_success: int = 0
    by_type: dict = field(default_factory=dict)

    def record(self, event: HealEvent):
        self.total_events += 1
        if event.success:
            self.heal_success += 1
        t = event.heal_type.value
        self.by_type[t] = self.by_type.get(t, 0) + 1


class BrowserSelfHealer:
    """浏览器自愈引擎

    工作流：
    1. 监听 page.on("dialog") 自动处理弹窗
    2. 操作失败时调用 heal_operation() 尝试修复
    3. 记录所有自愈事件，提供给前端可视化
    """

    def __init__(self):
        self._events: list[HealEvent] = []
        self._stats = HealStats()
        self._dialog_handlers: dict[str, str] = {}  # selector -> action

    @property
    def events(self) -> list[HealEvent]:
        return self._events

    @property
    def stats(self) -> HealStats:
        return self._stats

    def register_dialog_handler(self, selector: str, action: str = "accept"):
        """注册弹窗处理策略（特定元素触发的弹窗）"""
        self._dialog_handlers[selector] = action

    def setup_dialog_listener(self, page):
        """在 Playwright page 上注册弹窗监听器"""
        async def handle_dialog(dialog):
            try:
                msg = dialog.message
                dialog_type = dialog.type  # alert/confirm/prompt/beforeunload
                event = HealEvent(
                    timestamp=time.time(),
                    heal_type=HealType.DIALOG,
                    description=f"{dialog_type}: {msg[:80]}",
                    success=False,  # 待更新
                    before=f"弹窗出现: {msg[:50]}",
                )

                # 默认策略：accept（更安全，多数 alert 只是通知）
                action = "accept"
                # 检查是否有针对该元素的自定义处理
                for sel, custom_action in self._dialog_handlers.items():
                    if sel in msg or sel in (dialog.default_value or ""):
                        action = custom_action
                        break

                if action == "accept":
                    await dialog.accept()
                    event.success = True
                    event.after = "已接受弹窗"
                elif action == "dismiss":
                    await dialog.dismiss()
                    event.success = True
                    event.after = "已取消弹窗"
                else:
                    await dialog.accept()
                    event.success = True
                    event.after = f"已处理（默认 accept）"

                self._record(event)
            except Exception as e:
                logger.warning("处理弹窗失败: %s", e)

        page.on("dialog", lambda d: asyncio.create_task(handle_dialog(d)))

    async def heal_operation(
        self,
        page,
        action: str,
        params: dict,
        original_error: str,
        max_retries: int = 2,
    ) -> tuple[bool, str, dict]:
        """自愈式操作：失败后自动重试 + 备选策略

        Args:
            page: Playwright page
            action: 原动作名
            params: 原参数
            original_error: 原始错误信息
            max_retries: 最大重试次数

        Returns:
            (success, error_msg, heal_log)
        """
        heal_log = {"action": action, "params": params, "retries": []}
        last_error = original_error

        for retry in range(max_retries + 1):
            if retry == 0:
                # 第一次：重试原参数（可能是偶发）
                heal_event = HealEvent(
                    timestamp=time.time(),
                    heal_type=HealType.SELECTOR_FAIL,
                    description=f"重试原操作: {action}",
                    success=False,
                    retry_count=retry,
                    error=last_error,
                )
                try:
                    from backend.core.browser_agent import _execute_action
                    success, err = await _execute_action(page, action, params)
                    heal_event.success = success
                    heal_event.after = "成功" if success else err
                    self._record(heal_event)
                    if success:
                        return True, "", heal_log
                    last_error = err
                except Exception as e:
                    heal_event.error = str(e)
                    self._record(heal_event)
                    last_error = str(e)
            else:
                # 后续：尝试备选策略
                alt_params = await self._suggest_alternative(page, action, params, last_error)
                if not alt_params:
                    break

                heal_event = HealEvent(
                    timestamp=time.time(),
                    heal_type=HealType.SELECTOR_FAIL,
                    description=f"备选策略 #{retry}",
                    success=False,
                    retry_count=retry,
                    before=str(params),
                    after=str(alt_params),
                )
                try:
                    from backend.core.browser_agent import _execute_action
                    success, err = await _execute_action(page, action, alt_params)
                    heal_event.success = success
                    if success:
                        heal_event.after = f"备选策略成功: {alt_params}"
                        self._record(heal_event)
                        return True, "", heal_log
                    last_error = err
                    self._record(heal_event)
                except Exception as e:
                    heal_event.error = str(e)
                    self._record(heal_event)
                    last_error = str(e)

        return False, last_error, heal_log

    async def _suggest_alternative(
        self, page, action: str, params: dict, error: str
    ) -> Optional[dict]:
        """为失败的操作生成备选参数"""
        if action in ("click", "input", "select", "hover", "wait_for", "upload_file"):
            sel = params.get("selector", "")
            if not sel:
                return None

            # 用 self_healer 找备选 selector
            heal_result = await self_healer.heal_ui_selector(
                original_selector=sel,
                page_url=page.url,
            )
            candidates = heal_result.get("candidates", [])
            if candidates:
                # 第一个候选的 selector
                new_sel = candidates[0][1] if isinstance(candidates[0], tuple) else candidates[0]
                new_params = {**params, "selector": new_sel}
                return new_params

        return None

    def detect_error_page(self, page, response_or_url: str = "") -> dict:
        """检测是否是错误页（404/500/网络错误）"""
        url = response_or_url or page.url
        is_error = False
        error_type = ""

        # URL 包含错误关键词
        error_indicators = ["error", "404", "500", "notfound", "not-found", "exception", "unavailable"]
        for kw in error_indicators:
            if kw in url.lower():
                is_error = True
                error_type = f"URL含错误关键词: {kw}"
                break

        if is_error:
            event = HealEvent(
                timestamp=time.time(),
                heal_type=HealType.ERROR_PAGE,
                description=error_type,
                success=False,
                before=url,
            )
            self._record(event)
            return {"is_error": True, "type": error_type, "url": url}
        return {"is_error": False, "url": url}

    def _record(self, event: HealEvent):
        self._events.append(event)
        self._stats.record(event)
        logger.info("自愈事件: %s - %s (%s)", event.heal_type.value, event.description, "成功" if event.success else "失败")

    def summary(self) -> dict:
        """自愈摘要"""
        return {
            "total_events": self._stats.total_events,
            "heal_success": self._stats.heal_success,
            "heal_rate": (
                self._stats.heal_success / self._stats.total_events * 100
                if self._stats.total_events > 0 else 0
            ),
            "by_type": self._stats.by_type,
            "recent_events": [e.to_dict() for e in self._events[-10:]],
        }


# 全局单例
browser_self_healer = BrowserSelfHealer()
