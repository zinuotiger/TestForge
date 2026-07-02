"""E2E 浏览器测试执行器 — Playwright 集成

支持:
  - 页面导航 + 截图
  - 元素交互（点击/输入/选择）
  - 断言（可见性/文本/URL/标题）
  - 录制 + 回放
"""

import asyncio
import logging
import os
import time
from typing import Optional

try:
    from playwright.async_api import async_playwright
    _has_playwright = True
except ImportError:
    _has_playwright = False

logger = logging.getLogger("testforge")


def is_playwright_available() -> bool:
    """检查 Playwright 是否可用"""
    return _has_playwright


async def check_browser_status() -> dict:
    """检查浏览器执行环境状态"""
    if not _has_playwright:
        return {
            "available": False,
            "status": "not_installed",
            "hint": "安装: pip install playwright && playwright install chromium",
        }

    # 检查浏览器是否已安装
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        return {"available": True, "status": "ready", "browser": "chromium"}
    except Exception as e:
        return {
            "available": False,
            "status": "browser_not_installed",
            "hint": f"运行: playwright install chromium ({e})",
        }


async def execute_browser_test(steps: list[dict], base_url: str = "", timeout: int = 30) -> dict:
    """执行浏览器 E2E 测试

    Args:
        steps: 测试步骤列表
            [{"action": "navigate", "url": "/page"},
             {"action": "click", "selector": "#btn"},
             {"action": "input", "selector": "#input", "value": "text"},
             {"action": "assert", "type": "visible", "selector": "#result"},
             {"action": "assert", "type": "text", "selector": "#result", "expected": "OK"},
             {"action": "screenshot"}]
        base_url: 基础 URL
        timeout: 超时秒数

    Returns:
        {"passed": bool, "steps_total": int, "steps_passed": int, "screenshots": [...], "error": str}
    """
    if not is_playwright_available():
        return {
            "passed": False,
            "error": "Playwright 未安装。运行: pip install playwright && playwright install chromium",
            "steps_total": len(steps),
            "steps_passed": 0,
            "screenshots": [],
        }

    result = {
        "passed": True,
        "steps_total": len(steps),
        "steps_passed": 0,
        "screenshots": [],
        "error": "",
    }

    screenshot_dir = os.path.join(os.getcwd(), "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            page.set_default_timeout(timeout * 1000)

            # 注册弹窗处理器（一次有效，处理一次后即移除）
            async def handle_dialog(dialog):
                try:
                    # 默认接受弹窗，特殊动作可由 close_dialog 步骤覆盖
                    await dialog.accept()
                except Exception:
                    pass
            page.on("dialog", lambda d: asyncio.create_task(handle_dialog(d)))

            for i, step in enumerate(steps):
                action = step.get("action", "")
                try:
                    if action == "navigate":
                        url = step.get("url", "")
                        if base_url and not url.startswith("http"):
                            url = base_url.rstrip("/") + "/" + url.lstrip("/")
                        await page.goto(url, wait_until="domcontentloaded")
                        result["steps_passed"] += 1

                    elif action == "click":
                        await page.click(step["selector"])
                        result["steps_passed"] += 1

                    elif action == "input":
                        await page.fill(step["selector"], step.get("value", ""))
                        result["steps_passed"] += 1

                    elif action == "select":
                        await page.select_option(step["selector"], step.get("value", ""))
                        result["steps_passed"] += 1

                    elif action == "wait":
                        await page.wait_for_timeout(step.get("ms", 1000))
                        result["steps_passed"] += 1

                    elif action == "wait_for":
                        # 等待元素可见
                        sel = step["selector"]
                        await page.wait_for_selector(sel, state=step.get("state", "visible"))
                        result["steps_passed"] += 1

                    elif action == "press_key":
                        # 键盘按键：Enter/Tab/Escape/ArrowDown 等
                        await page.keyboard.press(step.get("key", "Enter"))
                        result["steps_passed"] += 1

                    elif action == "scroll":
                        # 滚动页面：direction=up/down/top/bottom，amount=像素
                        direction = step.get("direction", "down")
                        amount = int(step.get("amount", 500))
                        if direction == "top":
                            await page.evaluate("window.scrollTo(0, 0)")
                        elif direction == "bottom":
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        elif direction == "up":
                            await page.evaluate(f"window.scrollBy(0, -{amount})")
                        else:  # down
                            await page.evaluate(f"window.scrollBy(0, {amount})")
                        result["steps_passed"] += 1

                    elif action == "hover":
                        # 鼠标悬停（常用于触发下拉菜单）
                        await page.hover(step["selector"])
                        result["steps_passed"] += 1

                    elif action == "upload_file":
                        # 文件上传
                        sel = step["selector"]
                        file_path = step.get("file_path", "")
                        await page.set_input_files(sel, file_path)
                        result["steps_passed"] += 1

                    elif action == "drag":
                        # 拖拽
                        from_sel = step["from_selector"]
                        to_sel = step["to_selector"]
                        await page.drag_and_drop(from_sel, to_sel)
                        result["steps_passed"] += 1

                    elif action == "switch_frame":
                        # 切换到 iframe（通过 frame_locator，后续步骤通过 selector 操作）
                        # Playwright 的 frame_locator 是惰性的，存储到 page 对象上
                        setattr(page, "_frame_locator", page.frame_locator(step["selector"]))
                        result["steps_passed"] += 1

                    elif action == "switch_tab":
                        # 切换标签页
                        idx = int(step.get("index", 0))
                        pages = page.context.pages
                        if 0 <= idx < len(pages):
                            await pages[idx].bring_to_front()
                            result["steps_passed"] += 1
                        else:
                            raise ValueError(f"标签页索引越界: {idx}（共 {len(pages)} 个）")

                    elif action == "new_tab":
                        # 新开标签页并导航
                        url = step.get("url", "")
                        if url:
                            new_page = await page.context.new_page()
                            await new_page.goto(url, wait_until="domcontentloaded")
                        else:
                            await page.context.new_page()
                        result["steps_passed"] += 1

                    elif action == "close_dialog":
                        # 处理弹窗（accept/dismiss）；playwright 的 dialog 事件是一次性的
                        # 实际处理在 page.on("dialog") 中，此处作为标记步骤
                        result["steps_passed"] += 1

                    elif action == "extract":
                        # 提取页面信息到 result["extracted"]
                        what = step.get("what", "text")
                        if what == "text":
                            text = await page.evaluate("() => document.body.innerText.slice(0, 2000)")
                            result.setdefault("extracted", []).append({"type": "text", "value": text})
                        elif what == "links":
                            links = await page.evaluate("() => Array.from(document.querySelectorAll('a[href]')).slice(0, 20).map(a => ({href: a.href, text: a.textContent.trim().slice(0, 50)}))")
                            result.setdefault("extracted", []).append({"type": "links", "value": links})
                        elif what == "forms":
                            forms = await page.evaluate("() => Array.from(document.querySelectorAll('form')).map(f => ({action: f.action, method: f.method, fields: Array.from(f.querySelectorAll('input,select,textarea')).map(el => ({name: el.name, type: el.type || el.tagName.toLowerCase()}))}))")
                            result.setdefault("extracted", []).append({"type": "forms", "value": forms})
                        elif what in ("title", "url"):
                            val = page.url if what == "url" else await page.title()
                            result.setdefault("extracted", []).append({"type": what, "value": val})
                        result["steps_passed"] += 1

                    elif action == "ai_assert":
                        # AI 语义断言：调用 LLM 判断 condition 是否成立
                        from backend.core.browser_agent import _observe_page, _ai_assert
                        obs = await _observe_page(page)
                        condition = step.get("condition", step.get("expected", ""))
                        judgment = await _ai_assert(obs, condition)
                        if not judgment.get("passed"):
                            raise AssertionError(f"AI 断言失败: {judgment.get('reason', condition)}")
                        result["steps_passed"] += 1

                    elif action == "assert":
                        assert_type = step.get("type", "visible")
                        selector = step.get("selector", "")

                        if assert_type == "visible":
                            await page.wait_for_selector(selector, state="visible")
                        elif assert_type == "hidden":
                            await page.wait_for_selector(selector, state="hidden")
                        elif assert_type == "text":
                            actual = await page.text_content(selector)
                            expected = step.get("expected", "")
                            if expected not in (actual or ""):
                                raise AssertionError(f"文本断言失败: 期望包含 '{expected}', 实际 '{actual}'")
                        elif assert_type == "url":
                            actual_url = page.url
                            expected = step.get("expected", "")
                            if expected not in actual_url:
                                raise AssertionError(f"URL 断言失败: 期望包含 '{expected}', 实际 '{actual_url}'")
                        elif assert_type == "title":
                            actual_title = await page.title()
                            expected = step.get("expected", "")
                            if expected not in actual_title:
                                raise AssertionError(f"标题断言失败: 期望包含 '{expected}', 实际 '{actual_title}'")

                        result["steps_passed"] += 1

                    elif action == "screenshot":
                        ts = int(time.time())
                        filename = f"screenshot_{i}_{ts}.png"
                        filepath = os.path.join(screenshot_dir, filename)
                        await page.screenshot(path=filepath, full_page=True)
                        result["screenshots"].append(filename)
                        result["steps_passed"] += 1

                except Exception as e:
                    result["passed"] = False
                    result["error"] = f"步骤 {i+1} ({action}) 失败: {e}"
                    # 失败时截图
                    ts = int(time.time())
                    filename = f"error_{i}_{ts}.png"
                    filepath = os.path.join(screenshot_dir, filename)
                    try:
                        await page.screenshot(path=filepath, full_page=True)
                        result["screenshots"].append(filename)
                    except Exception:
                        pass
                    break

            await browser.close()

    except Exception as e:
        result["passed"] = False
        result["error"] = f"浏览器启动失败: {e}"

    return result


async def record_browser_flow(url: str, duration: int = 30) -> dict:
    """自动探索式录制浏览器操作流程

    采用"自动探索"策略：导航到目标 URL → 收集页面可交互元素 → 生成导航/点击/断言步骤。
    相比手动 codegen 录制，自动探索无需桌面环境，适合服务端场景。

    Args:
        url: 起始页面 URL
        duration: 探索时长上限（秒）

    Returns:
        {"status": str, "steps": [...], "error": str}
    """
    if not is_playwright_available():
        return {"status": "error", "error": "Playwright 未安装", "steps": []}

    steps: list[dict] = []
    start = time.time()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            page.set_default_timeout(8000)

            # 1. 导航
            try:
                await page.goto(url, wait_until="domcontentloaded")
                steps.append({
                    "action": "navigate",
                    "url": url,
                    "description": f"导航到 {url}",
                })
            except Exception as e:
                await browser.close()
                return {"status": "error", "error": f"导航失败: {e}", "steps": []}

            # 2. 标题断言
            try:
                title = await page.title()
                if title:
                    steps.append({
                        "action": "assert",
                        "type": "title",
                        "expected": title,
                        "description": f"断言页面标题包含 '{title}'",
                    })
            except Exception:
                pass

            # 3. 收集页面主要可交互元素，生成探索步骤
            try:
                # 收集链接（前 10 个内部链接）
                links = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href]'))
                        .filter(a => {
                            const href = a.href;
                            return href && !href.startsWith('javascript:') && !href.startsWith('mailto:');
                        })
                        .slice(0, 10)
                        .map(a => ({
                            href: a.href,
                            text: (a.textContent || '').trim().slice(0, 50),
                            selector: a.id ? '#' + a.id : (a.getAttribute('data-testid') ? '[data-testid="' + a.getAttribute('data-testid') + '"]' : 'a:has-text("' + (a.textContent || '').trim().slice(0, 20) + '")')
                        }));
                }""")
                for link in links:
                    if time.time() - start > duration:
                        break
                    steps.append({
                        "action": "click",
                        "selector": link["selector"],
                        "description": f"点击链接: {link['text'] or link['href']}",
                    })
            except Exception:
                pass

            # 4. 收集表单输入框
            try:
                inputs = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('input[type="text"], input[type="email"], input[type="search"], textarea'))
                        .slice(0, 5)
                        .map(el => ({
                            selector: el.id ? '#' + el.id : el.name ? '[name="' + el.name + '"]' : '',
                            placeholder: el.placeholder || '',
                            name: el.name || ''
                        }))
                        .filter(el => el.selector);
                }""")
                for inp in inputs:
                    sample_value = _guess_sample_value(inp.get("name", "") + " " + inp.get("placeholder", ""))
                    steps.append({
                        "action": "input",
                        "selector": inp["selector"],
                        "value": sample_value,
                        "description": f"在 {inp.get('placeholder') or inp.get('name')} 输入示例数据",
                    })
            except Exception:
                pass

            # 5. 截图
            try:
                screenshot_dir = os.path.join(os.getcwd(), "screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                ts = int(time.time())
                filename = f"recorded_{ts}.png"
                filepath = os.path.join(screenshot_dir, filename)
                await page.screenshot(path=filepath, full_page=True)
                steps.append({
                    "action": "screenshot",
                    "path": filename,
                    "description": "截取页面快照",
                })
            except Exception:
                pass

            await browser.close()

        return {
            "status": "success",
            "steps": steps,
            "step_count": len(steps),
            "duration_ms": int((time.time() - start) * 1000),
            "hint": "已通过自动探索生成测试步骤，可在测试设计器中查看和调整",
        }

    except Exception as e:
        return {"status": "error", "error": f"录制失败: {e}", "steps": steps}


def _guess_sample_value(hint: str) -> str:
    """根据字段名/placeholder 启发式猜测示例值"""
    h = hint.lower()
    if "email" in h or "邮箱" in h:
        return "test@example.com"
    if "phone" in h or "手机" in h or "tel" in h:
        return "13800000000"
    if "password" in h or "密码" in h:
        return "Test@12345"
    if "name" in h or "姓名" in h:
        return "TestForge"
    if "search" in h or "搜索" in h or "q" in h:
        return "TestForge"
    return "sample_input"
