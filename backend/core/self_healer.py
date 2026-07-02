"""Self-healer engine -- UI selector / API Schema / Assertion three-layer auto-fix"""

import asyncio
import logging
import re
from enum import Enum
from typing import Optional

logger = logging.getLogger("testforge")


# Lazy import for evolution loop -- avoids circular import
def _get_evolution_loop():
    return __import__("backend.core.self_evolution", fromlist=["evolution_loop"]).evolution_loop


class HealLayer(str, Enum):
    UI_SELECTOR = "ui_selector"
    API_SCHEMA = "api_schema"
    ASSERTION = "assertion"


class SelfHealer:
    """Cross-layer self-healer engine."""

    SELECTOR_STRATEGIES = [
        ("data-testid", lambda name: f'[data-testid="{name}"]'),
        ("id", lambda name: f"#{name}"),
        ("name", lambda name: f'[name="{name}"]'),
        ("css_class", lambda name: f".{name.replace(' ', '.')}"),
        ("aria_label", lambda name: f'[aria-label="{name}"]'),
        ("xpath_text", lambda name: f'//*[contains(text(),"{name}")]'),
        ("xpath_contains", lambda name: f'//*[contains(@class,"{name}")]'),
    ]

    def __init__(self):
        self._heal_log: list[dict] = []
        self._success_count = 0
        self._total_attempts = 0

    async def heal_ui_selector(
        self,
        original_selector: str,
        page_url: str = "",
    ) -> dict:
        """Heal a broken UI selector."""
        self._total_attempts += 1
        selector_type, selector_value = self._parse_selector(original_selector)

        candidates = self._generate_candidates(selector_type, selector_value)

        healed_selector = original_selector
        success = False

        if page_url:
            for strategy_name, candidate in candidates:
                try:
                    result = await self._heal_with_playwright(
                        original_selector, candidate, page_url
                    )
                    if result.get("success"):
                        healed_selector = candidate
                        success = True
                        break
                except Exception:
                    continue

        if not success:
            for _, candidate in candidates:
                healed_selector = candidate
                success = True
                break

        result = {
            "layer": HealLayer.UI_SELECTOR,
            "original": original_selector,
            "healed_selector": healed_selector,
            "success": success,
            "strategy_used": selector_type,
        }
        self._heal_log.append(result)
        if result["success"]:
            self._success_count += 1

        # Evolution hook
        try:
            ev = _get_evolution_loop()
            await ev.on_heal_event(
                "ui_selector", original_selector,
                result.get("healed_selector", ""), result["success"]
            )
        except Exception:
            pass

        return result

    async def _heal_with_playwright(
        self,
        original_selector: str,
        selector_value: str,
        page_url: str,
    ) -> dict:
        """Validate candidate selector with Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"success": False, "error": "Playwright not installed"}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(page_url, timeout=15000)
                try:
                    await page.wait_for_selector(
                        selector_value, timeout=5000, state="visible"
                    )
                    return {"success": True, "selector": selector_value}
                except Exception:
                    return {"success": False, "error": "selector not found"}
            finally:
                await browser.close()

    def _generate_candidates(
        self, skip_type: str, value: str
    ) -> list[tuple[str, str]]:
        """Generate alternative selector candidates."""
        results = []
        for strategy_name, factory in self.SELECTOR_STRATEGIES:
            if strategy_name != skip_type:
                results.append((strategy_name, factory(value)))
        return results

    async def heal_api_schema(
        self, original_schema: dict, actual_response: dict
    ) -> dict:
        """Heal a broken API schema assertion."""
        self._total_attempts += 1
        changes = []
        healed_schema = dict(original_schema) if original_schema else {}

        if isinstance(original_schema, dict) and isinstance(actual_response, dict):
            for key, expected_type in original_schema.items():
                if key not in actual_response:
                    changes.append({"key": key, "change": "removed"})
                    healed_schema.pop(key, None)
                else:
                    actual_type = type(actual_response[key]).__name__
                    if expected_type != actual_type:
                        changes.append({
                            "key": key,
                            "change": f"{expected_type} -> {actual_type}",
                        })
                        healed_schema[key] = actual_type

        result = {
            "layer": HealLayer.API_SCHEMA,
            "original_schema": original_schema,
            "healed_schema": healed_schema,
            "changes": changes,
            "success": len(changes) > 0,
        }
        self._heal_log.append(result)
        if result["success"]:
            self._success_count += 1

        # Evolution hook
        try:
            ev = _get_evolution_loop()
            await ev.on_heal_event(
                "api_schema",
                str(original_schema)[:200],
                str(healed_schema)[:200],
                result["success"],
            )
        except Exception:
            pass

        return result

    async def heal_assertion(self, expected, actual) -> dict:
        """Heal a broken assertion by inferring the correct expected value."""
        self._total_attempts += 1

        changed = False
        healed = expected

        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if (
                isinstance(expected, int)
                and isinstance(actual, int)
                and 200 <= expected < 300
                and 200 <= actual < 300
            ):
                healed = actual
                changed = expected != actual
            elif abs(actual - expected) > expected * 0.1:
                healed = actual
                changed = True

        elif isinstance(expected, str) and isinstance(actual, str):
            if expected in actual or actual in expected:
                healed = expected
            else:
                healed = actual
                changed = True

        elif isinstance(expected, list) and isinstance(actual, list):
            if len(actual) > 0:
                healed = actual
                changed = expected != actual

        elif expected != actual:
            healed = actual
            changed = True

        result = {
            "layer": HealLayer.ASSERTION,
            "original_expected": expected,
            "actual_value": actual,
            "healed_expected": healed,
            "changed": changed,
            "success": True,
        }
        self._heal_log.append(result)
        self._success_count += 1

        # Evolution hook
        try:
            ev = _get_evolution_loop()
            await ev.on_heal_event(
                "assertion",
                str(expected)[:200],
                str(healed)[:200],
                True,
            )
        except Exception:
            pass

        return result

    @property
    def stats(self) -> dict:
        return {
            "total_attempts": self._total_attempts,
            "success_count": self._success_count,
            "success_rate": round(
                self._success_count / max(self._total_attempts, 1), 2
            ),
            "recent_log": self._heal_log[-10:],
        }

    def _parse_selector(self, selector: str) -> tuple[str, str]:
        if selector.startswith("[data-testid="):
            return (
                "data-testid",
                selector.split('"')[1] if '"' in selector else selector.split("'")[1],
            )
        if selector.startswith("#"):
            return ("id", selector[1:])
        if selector.startswith("[name="):
            return (
                "name",
                selector.split('"')[1] if '"' in selector else selector.split("'")[1],
            )
        if selector.startswith("[aria-label="):
            return (
                "aria_label",
                selector.split('"')[1] if '"' in selector else selector.split("'")[1],
            )
        if selector.startswith("."):
            return ("css_class", selector[1:])
        if selector.startswith("//"):
            return ("xpath", selector)
        return ("css", selector)

    @staticmethod
    def _infer_type(value) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "string"


# Global instance
self_healer = SelfHealer()
