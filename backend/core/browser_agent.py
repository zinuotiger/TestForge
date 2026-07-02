"""BrowserAgent — AI 驱动的浏览器操控 Agent

核心理念：自然语言 → LLM 决策 → Playwright 执行 → 截图观察 → 循环直到任务完成

设计要点：
1. ReAct 循环：Observation（截图+DOM）→ Thought（LLM 推理）→ Action（Playwright 操作）→ 重复
2. 自然语言任务解析：用户用中文/英文描述需求，LLM 自动拆解为步骤
3. 视觉理解：截图 + 页面可访问树（a11y tree）作为观察输入
4. AI 断言：LLM 判断"是否登录成功""商品是否已加入购物车"等语义级断言
5. 记忆机制：保存执行历史，下一次执行可参考
6. 自愈能力：操作失败时自动尝试替代方案
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

from backend.config import settings

logger = logging.getLogger("testforge")

# ============================================================
# Agent 可用的操作（Action）— Playwright 命令的语义化封装
# ============================================================
AGENT_ACTIONS = [
    "navigate",         # 打开 URL
    "click",            # 点击元素
    "input",            # 输入文本
    "select",           # 下拉选择
    "hover",            # 鼠标悬停
    "scroll",           # 滚动页面
    "wait",             # 等待
    "wait_for",         # 等待元素出现
    "press_key",        # 按键
    "screenshot",       # 截图
    "extract",          # 提取信息
    "assert",           # AI 语义断言
    "switch_tab",       # 切换标签页
    "switch_frame",     # 切换 iframe
    "close_dialog",     # 处理弹窗
    "upload_file",      # 文件上传
    "drag",             # 拖拽
    "visual_click",     # 视觉定位点击（截图→AI→坐标）
    "visual_find",      # 视觉定位（不点击，只返回坐标）
    "smart_locate",     # 智能定位（selector→a11y→视觉）
    "finish",           # 任务完成
]

# 系统提示词：教导 LLM 如何扮演 Browser Agent
SYSTEM_PROMPT = """你是 TestForge BrowserAgent，一个用自然语言操作浏览器的 AI 助手。

【你的能力】
你可以一步步操作真实浏览器（Playwright + Chromium），执行以下动作：
- navigate(url): 打开网页
- click(selector): 点击元素（selector 支持 CSS / 文本匹配 / data-testid）
- input(selector, value): 在输入框填入文本
- select(selector, value): 选择下拉框选项
- hover(selector): 鼠标悬停
- scroll(direction, amount): 滚动页面（direction: up/down/top/bottom，amount: 像素数）
- wait(ms): 等待若干毫秒
- wait_for(selector, timeout): 等待元素出现
- press_key(key): 按键（Enter, Tab, Escape, ArrowDown 等）
- screenshot(): 截屏
- extract(what): 从页面提取信息（text, links, forms, title, url, all）
- assert(condition): AI 语义判断（例：assert('页面已跳转到首页'), assert('错误提示可见')）
- switch_tab(index): 切换到第 N 个标签页
- switch_frame(selector): 切换到指定 iframe
- close_dialog(action): 处理弹窗（action: accept/dismiss）
- upload_file(selector, file_path): 文件上传
- drag(from_selector, to_selector): 拖拽
- visual_click(description): 视觉定位点击（用截图+AI找"登录按钮"等元素，无需 selector）
- visual_find(description): 仅返回元素坐标（不点击）
- smart_locate(target): 智能定位（先 selector→a11y→视觉，自动选最优策略）
- finish(reason, success): 任务结束，输出结论

【工作流程】ReAct 循环
1. **Observation** — 观察当前页面（你将看到 URL + 标题 + 可访问树 + 截图描述）
2. **Thought** — 思考下一步该做什么
3. **Action** — 输出一条 JSON 格式的动作

【输出格式】
严格使用以下 JSON 结构（不要包裹在 markdown 代码块中，直接输出 JSON）：
{
  "thought": "简要说明你的推理（中文）",
  "action": "动作名",
  "params": { ...动作参数... }
}

最后一步使用 finish 动作：
{"thought": "任务完成", "action": "finish", "params": {"reason": "完成原因", "success": true}}

【选择 selector 的策略】
- 优先使用：#id, [data-testid="..."], [name="..."]
- 次选：button:has-text("登录"), a:has-text("首页")
- 避免：长 CSS 链、易变的 class 名

【重要规则】
- 每次只做一个动作，循序渐进
- 如果操作失败，思考替代方案（换 selector / 滚动 / 等待）
- 不确定时先 screenshot 或 extract 看看
- 完成后必须用 finish 收尾
"""


@dataclass
class AgentStep:
    """Agent 的一步决策与执行结果"""
    step_id: int
    thought: str
    action: str
    params: dict
    observation: str = ""          # 执行后的观察（截图描述 + DOM 摘要）
    success: bool = True
    error: str = ""
    screenshot_b64: str = ""       # 步骤截图（base64）
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "thought": self.thought,
            "action": self.action,
            "params": self.params,
            "observation": self.observation,
            "success": self.success,
            "error": self.error,
            "screenshot_b64": self.screenshot_b64[:100] + "..." if self.screenshot_b64 else "",
            "has_screenshot": bool(self.screenshot_b64),
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentResult:
    """Agent 任务完整结果"""
    task: str
    start_url: str
    success: bool
    finish_reason: str
    steps: list[AgentStep] = field(default_factory=list)
    total_duration_ms: int = 0
    error: str = ""
    final_screenshot_b64: str = ""
    final_url: str = ""
    final_title: str = ""

    def to_dict(self) -> dict:
        d = {
            "task": self.task,
            "start_url": self.start_url,
            "success": self.success,
            "finish_reason": self.finish_reason,
            "total_steps": len(self.steps),
            "total_duration_ms": self.total_duration_ms,
            "error": self.error,
            "final_url": self.final_url,
            "final_title": self.final_title,
            "final_screenshot_b64": self.final_screenshot_b64,
            "steps": [s.to_dict() for s in self.steps],
        }
        # 附加自愈摘要（如有）
        if hasattr(self, "heal_summary") and self.heal_summary:
            d["heal_summary"] = self.heal_summary
        return d

    def to_dict_with_heal(self, heal_summary: dict = None) -> dict:
        d = self.to_dict()
        if heal_summary:
            d["heal_summary"] = heal_summary
        return d


# ============================================================
# LLM 调用：复用项目现有的 DashScope / LiteLLM 通道
# ============================================================

async def _call_llm(messages: list[dict], max_tokens: int = 800, temperature: float = 0.3) -> str:
    """调用 LLM 并返回文本响应"""
    # 通道 1: DashScope（项目主用）
    if settings.llm_api_key and "dashscope" in settings.llm_provider.lower():
        try:
            return await _call_dashscope(messages, max_tokens, temperature)
        except Exception as e:
            logger.warning("DashScope 调用失败: %s", e)

    # 通道 2: 通用 OpenAI 兼容 API
    if settings.llm_api_key:
        try:
            return await _call_openai_compatible(messages, max_tokens, temperature)
        except Exception as e:
            logger.warning("OpenAI 兼容 API 调用失败: %s", e)

    raise RuntimeError("LLM 未配置或调用失败：请在 .env 中设置 TESTFORGE_LLM_API_KEY 等")


async def _call_dashscope(messages: list[dict], max_tokens: int, temperature: float) -> str:
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=body, headers=headers) as resp:
            data = await resp.json(content_type=None)
            return data["choices"][0]["message"]["content"]


async def _call_openai_compatible(messages: list[dict], max_tokens: int, temperature: float) -> str:
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=body, headers=headers) as resp:
            data = await resp.json(content_type=None)
            return data["choices"][0]["message"]["content"]


def _parse_llm_action(text: str) -> dict:
    """从 LLM 响应中解析 JSON 动作

    LLM 可能返回纯 JSON、JSON in markdown code block、或带杂质文本
    """
    text = text.strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    if "```" in text:
        try:
            start = text.find("```")
            if start != -1:
                # 跳过 ```json 或 ```
                after = text.find("\n", start)
                if after != -1:
                    inner_start = after + 1
                else:
                    inner_start = start + 3
                end = text.find("```", inner_start)
                if end != -1:
                    inner = text[inner_start:end].strip()
                    return json.loads(inner)
        except (json.JSONDecodeError, ValueError):
            pass

    # 尝试提取 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析 LLM 响应为 JSON: {text[:200]}")


# ============================================================
# 页面观察：截图 + 可访问树
# ============================================================

async def _observe_page(page) -> dict:
    """观察当前页面：URL、标题、可访问树、截图"""
    try:
        url = page.url
        title = await page.title()
    except Exception:
        url, title = "", ""

    # 提取可访问树（用于 LLM 理解页面结构）
    try:
        a11y_tree = await page.evaluate("""() => {
            function describe(el, depth=0) {
                if (depth > 4) return '';
                const tag = el.tagName ? el.tagName.toLowerCase() : '';
                if (!tag) return '';
                const role = el.getAttribute('role') || '';
                const text = (el.innerText || el.textContent || '').trim().slice(0, 80);
                const id = el.id ? '#' + el.id : '';
                const cls = el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '';
                const testid = el.getAttribute('data-testid') ? '[data-testid="' + el.getAttribute('data-testid') + '"]' : '';
                const name = el.getAttribute('name') ? '[name="' + el.getAttribute('name') + '"]' : '';
                const type = el.getAttribute('type') ? '[type="' + el.getAttribute('type') + '"]' : '';
                const placeholder = el.getAttribute('placeholder') || '';
                const aria = el.getAttribute('aria-label') || '';
                const href = el.getAttribute('href') || '';

                let line = '  '.repeat(depth) + tag + id + cls + testid + name + type;
                if (role) line += '[role=' + role + ']';
                if (placeholder) line += '[placeholder=' + placeholder + ']';
                if (aria) line += '[aria=' + aria + ']';
                if (href) line += '[href=' + href.slice(0, 50) + ']';
                if (text && text.length < 60) line += ' "' + text + '"';
                let result = line + '\\n';

                // 递归到关键子元素
                for (const child of el.children) {
                    result += describe(child, depth + 1);
                }
                return result;
            }
            return describe(document.body).slice(0, 4000);
        }""")
    except Exception as e:
        a11y_tree = f"(a11y tree 提取失败: {e})"

    # 截图为 base64
    try:
        screenshot_bytes = await page.screenshot(full_page=False, type="jpeg", quality=70)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    except Exception:
        screenshot_b64 = ""

    return {
        "url": url,
        "title": title,
        "a11y_tree": a11y_tree,
        "screenshot_b64": screenshot_b64,
    }


def _format_observation(obs: dict) -> str:
    """将观察格式化为 LLM 输入"""
    return f"""【当前页面】
URL: {obs['url']}
标题: {obs['title']}

【可访问树（前 4 层）】
{obs['a11y_tree']}
"""


# ============================================================
# 动作执行器：把 LLM 决策转为 Playwright 操作
# ============================================================

async def _execute_action(page, action: str, params: dict) -> tuple[bool, str]:
    """执行一个动作，返回 (成功, 错误信息)"""
    try:
        if action == "navigate":
            url = params.get("url", "")
            if not url:
                return False, "缺少 url 参数"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        elif action == "click":
            sel = params.get("selector", "")
            if not sel:
                return False, "缺少 selector 参数"
            await page.click(sel, timeout=10000)

        elif action == "input":
            sel = params.get("selector", "")
            value = params.get("value", "")
            if not sel:
                return False, "缺少 selector 参数"
            await page.fill(sel, value, timeout=10000)

        elif action == "select":
            sel = params.get("selector", "")
            value = params.get("value", "")
            if not sel:
                return False, "缺少 selector 参数"
            await page.select_option(sel, value, timeout=10000)

        elif action == "hover":
            sel = params.get("selector", "")
            if not sel:
                return False, "缺少 selector 参数"
            await page.hover(sel, timeout=10000)

        elif action == "scroll":
            direction = params.get("direction", "down")
            amount = int(params.get("amount", 500))
            if direction == "down":
                await page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                await page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "top":
                await page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        elif action == "wait":
            ms = int(params.get("ms", 1000))
            await page.wait_for_timeout(ms)

        elif action == "wait_for":
            sel = params.get("selector", "")
            timeout = int(params.get("timeout", 10000))
            if not sel:
                return False, "缺少 selector 参数"
            await page.wait_for_selector(sel, timeout=timeout)

        elif action == "press_key":
            key = params.get("key", "")
            if not key:
                return False, "缺少 key 参数"
            await page.keyboard.press(key)

        elif action == "screenshot":
            pass  # 在 observe 时自动截图

        elif action == "extract":
            what = params.get("what", "text")
            if what == "text":
                text = await page.evaluate("() => document.body.innerText.slice(0, 1000)")
                return True, f"页面文本: {text}"
            elif what == "links":
                links = await page.evaluate("() => Array.from(document.querySelectorAll('a[href]')).slice(0, 10).map(a => a.href)")
                return True, f"链接列表: {links}"
            elif what == "forms":
                forms = await page.evaluate("() => Array.from(document.querySelectorAll('form')).map(f => ({action: f.action, method: f.method}))")
                return True, f"表单列表: {forms}"
            elif what in ("title", "url"):
                return True, f"{what}: {page.url if what == 'url' else await page.title()}"
            elif what == "all":
                text = await page.evaluate("() => document.body.innerText.slice(0, 2000)")
                title = await page.title()
                return True, f"标题: {title}\n正文: {text}"

        elif action == "assert":
            # AI 语义断言：把当前页面快照 + 断言条件发给 LLM 判断
            obs = await _observe_page(page)
            condition = params.get("condition", "")
            judgment = await _ai_assert(obs, condition)
            if not judgment["passed"]:
                return False, f"断言失败: {judgment['reason']}"
            return True, f"断言通过: {judgment['reason']}"

        elif action == "switch_tab":
            idx = int(params.get("index", 0))
            pages = page.context.pages
            if idx < 0 or idx >= len(pages):
                return False, f"标签页索引越界: {idx}（共 {len(pages)} 个）"
            page = pages[idx]
            await page.bring_to_front()

        elif action == "switch_frame":
            sel = params.get("selector", "")
            if not sel:
                return False, "缺少 selector 参数"
            frame = page.frame_locator(sel)
            # 切换主引用（用 child_frame 拿到实际 page frame）
            child_frames = [f for f in page.frames if f != page.main_frame]
            target = None
            for f in child_frames:
                try:
                    if await f.locator(sel).count() > 0:
                        target = f
                        break
                except Exception:
                    continue
            if target:
                # 后续操作需要用 target frame；这里通过 page.main_frame 替代
                # 实际切换 frame 在 BrowserAgent._step_executor 中处理
                pass

        elif action == "close_dialog":
            action_type = params.get("dialog_action", "accept")
            # Playwright 对话框需要在 page.on 事件中处理；这里标记待处理
            return True, f"弹窗处理已设置: {action_type}"

        elif action == "upload_file":
            sel = params.get("selector", "")
            file_path = params.get("file_path", "")
            if not sel or not file_path:
                return False, "缺少 selector 或 file_path 参数"
            await page.set_input_files(sel, file_path)

        elif action == "drag":
            from_sel = params.get("from_selector", "")
            to_sel = params.get("to_selector", "")
            if not from_sel or not to_sel:
                return False, "缺少 from_selector 或 to_selector 参数"
            await page.drag_and_drop(from_sel, to_sel)

        elif action == "visual_click":
            # 视觉定位点击：用 VLM 看截图 + 元素描述 → 找到坐标 → click
            from backend.core.visual_locator import click_by_visual
            desc = params.get("description", "")
            if not desc:
                return False, "缺少 description 参数（如'登录按钮'）"
            result = await click_by_visual(page, desc)
            if not result.get("success"):
                return False, f"视觉点击失败: {result.get('error', '未知')}"
            # 附加元信息到返回值（通过特殊前缀）
            return True, f"视觉点击成功 ({result.get('method', '?')}, 置信度 {result.get('confidence', 0):.0%}, 坐标 {result['x']},{result['y']})"

        elif action == "visual_find":
            # 视觉定位（不点击）
            from backend.core.visual_locator import locate_element_by_visual
            desc = params.get("description", "")
            if not desc:
                return False, "缺少 description 参数"
            loc = await locate_element_by_visual(page, desc)
            if not loc.get("found"):
                return False, f"视觉定位失败: {loc.get('error', '未知')}"
            return True, f"视觉定位成功: ({loc['x']},{loc['y']}) 置信度 {loc.get('confidence', 0):.0%}"

        elif action == "smart_locate":
            # 智能定位
            from backend.core.visual_locator import smart_locate
            target = params.get("target", "")
            prefer_visual = bool(params.get("visual", False))
            if not target:
                return False, "缺少 target 参数"
            loc = await smart_locate(page, target, prefer_visual=prefer_visual)
            return True, f"智能定位: 策略={loc.get('strategy', '?')}, 结果={json.dumps(loc, ensure_ascii=False)[:200]}"

        elif action == "finish":
            return True, "任务完成"

        else:
            return False, f"未知动作: {action}"

        return True, ""

    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}"


async def _ai_assert(obs: dict, condition: str) -> dict:
    """AI 语义断言：让 LLM 判断 condition 是否在当前页面成立"""
    obs_text = f"""URL: {obs['url']}
标题: {obs['title']}
页面文本（前 1500 字）:
{obs['a11y_tree'][:1500]}"""
    messages = [
        {"role": "system", "content": "你是一个网页状态判断助手。根据当前页面内容判断给定条件是否成立。\n\n输出严格 JSON：\n{\"passed\": true/false, \"reason\": \"判断理由（中文，20字内）\"}"},
        {"role": "user", "content": f"【断言条件】\n{condition}\n\n【当前页面】\n{obs_text}"},
    ]
    try:
        text = await _call_llm(messages, max_tokens=200, temperature=0.0)
        return _parse_llm_action(text)
    except Exception as e:
        return {"passed": False, "reason": f"AI 断言异常: {e}"}


# ============================================================
# 自然语言任务解析：把用户自然语言描述拆解为初始步骤
# ============================================================

async def parse_natural_task(task: str, start_url: str) -> list[dict]:
    """把自然语言任务解析为初始测试计划

    Returns:
        [{"action": "navigate", "params": {...}, "description": "..."}, ...]
    """
    messages = [
        {"role": "system", "content": """你是测试计划生成器。根据用户的自然语言任务描述，生成一个初步的浏览器测试步骤列表。

每步格式：
{"action": "动作名", "params": {"参数": 值}, "description": "此步的中文说明"}

动作：navigate, click, input, select, scroll, wait, wait_for, assert, extract, screenshot, finish

只输出 JSON 数组，不要其他文字。"""},
        {"role": "user", "content": f"""任务：{task}

起始 URL：{start_url}

请输出测试步骤："""},
    ]
    try:
        text = await _call_llm(messages, max_tokens=800, temperature=0.2)
        plans = _parse_llm_action(text)
        if isinstance(plans, list):
            return plans
        if isinstance(plans, dict) and "steps" in plans:
            return plans["steps"]
        return []
    except Exception as e:
        logger.warning("自然语言任务解析失败: %s", e)
        # 兜底：只导航
        return [{"action": "navigate", "params": {"url": start_url}, "description": f"打开 {start_url}"}]


# ============================================================
# 主入口：ReAct 循环
# ============================================================

async def run_browser_agent(
    task: str,
    start_url: str = "",
    max_steps: int = 12,
    headless: bool = True,
) -> AgentResult:
    """运行 BrowserAgent 执行自然语言任务

    Args:
        task: 自然语言任务描述（如："打开 example.com，验证页面有标题"）
        start_url: 起始 URL（可选，LLM 可自行 navigate）
        max_steps: 最大循环步数（防止死循环）
        headless: 是否无头模式

    Returns:
        AgentResult 包含每步决策、执行结果、最终结论
    """
    from playwright.async_api import async_playwright

    result = AgentResult(
        task=task,
        start_url=start_url,
        success=False,
        finish_reason="",
    )
    start_time = time.time()

    if not start_url:
        # 让 LLM 从任务中推断起始 URL
        start_url = "https://www.example.com"

    # 解析自然语言任务为初始计划
    initial_plan = await parse_natural_task(task, start_url)
    logger.info("自然语言任务解析为 %d 步初始计划", len(initial_plan))

    # 加载历史经验（如有）
    from urllib.parse import urlparse
    domain = urlparse(start_url).netloc if start_url else ""
    memory_context = ""
    try:
        from backend.core.agent_memory import agent_memory
        memory_context = agent_memory.format_for_llm(domain, current_action=task[:50])
        if memory_context:
            logger.info("加载历史经验: %d 条相关记录", memory_context.count("- ["))
    except Exception as e:
        logger.debug("记忆加载失败: %s", e)

    # 自愈器
    from backend.core.browser_self_healer import browser_self_healer as self_healer_engine
    heal_log_summary = {"total": 0, "success": 0, "events": []}

    history: list[dict] = []  # LLM 对话历史

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) TestForge BrowserAgent/1.0",
            )
            page = await context.new_page()
            page.set_default_timeout(15000)

            # 注册弹窗自愈监听器
            self_healer_engine.setup_dialog_listener(page)

            # 初始导航
            if start_url:
                try:
                    await page.goto(start_url, wait_until="domcontentloaded", timeout=15000)
                except Exception as e:
                    logger.warning("初始导航失败: %s", e)

            # 初始观察
            obs = await _observe_page(page)
            user_msg = f"【任务】\n{task}\n\n{_format_observation(obs)}"
            if memory_context:
                user_msg += f"\n\n{memory_context}"
            history.append({"role": "user", "content": user_msg})
            result.final_url = obs["url"]
            result.final_title = obs["title"]

            # ReAct 循环
            for step_id in range(1, max_steps + 1):
                t0 = time.time()

                # 调用 LLM 决策
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
                try:
                    llm_text = await _call_llm(messages, max_tokens=600, temperature=0.3)
                    decision = _parse_llm_action(llm_text)
                except Exception as e:
                    error_msg = f"LLM 决策失败: {e}"
                    logger.warning(error_msg)
                    result.steps.append(AgentStep(
                        step_id=step_id,
                        thought="",
                        action="error",
                        params={},
                        success=False,
                        error=error_msg,
                        duration_ms=int((time.time() - t0) * 1000),
                    ))
                    break

                thought = decision.get("thought", "")
                action = decision.get("action", "")
                params = decision.get("params", {})

                # 视觉增强：对 click/input/hover 类操作，如果 LLM 用了描述而非 selector，
                # 自动补充 a11y 坐标
                if action in ("click", "input", "hover") and not params.get("selector"):
                    desc = params.get("description", "") or params.get("text", "") or params.get("value", "")
                    if desc and not desc.startswith("#") and not desc.startswith("["):
                        from backend.core.visual_locator import _locate_via_a11y
                        a11y = await _locate_via_a11y(page, desc)
                        if a11y.get("found"):
                            params["selector"] = (
                                a11y.get("matched_element", {}).get("id")
                                and f"#{a11y['matched_element']['id']}"
                            ) or a11y.get("matched_element", {}).get("selector", "")

                # 执行动作（带自愈重试）
                success, error = await _execute_action(page, action, params)
                heal_info = None
                if not success and action in ("click", "input", "select", "hover", "wait_for"):
                    # 触发自愈
                    heal_success, heal_error, heal_log = await self_healer_engine.heal_operation(
                        page, action, params, error, max_retries=2
                    )
                    heal_info = heal_log
                    heal_log_summary["total"] += len(heal_log.get("retries", []))
                    if heal_success:
                        success = True
                        error = ""
                        heal_log_summary["success"] += 1

                # 视觉理解补充：每步执行后用截图给 LLM 提供更丰富观察
                visual_description = ""
                if action not in ("screenshot", "finish"):
                    try:
                        from backend.core.visual_locator import enumerate_visible_elements
                        visible = await enumerate_visible_elements(page)
                        if visible:
                            # 提取前 5 个有意义的元素
                            elements_desc = []
                            for el in visible[:8]:
                                txt = el.get("text", "") or el.get("aria", "") or el.get("placeholder", "")
                                if txt and len(txt.strip()) > 0:
                                    elements_desc.append(f"[{el['tag']}] {txt[:30]}")
                            if elements_desc:
                                visual_description = "\n【页面上可见的交互元素（前 8 个）】\n" + "\n".join(elements_desc)
                    except Exception:
                        pass

                # 截图（除 finish 外都截）
                screenshot_b64 = ""
                if action != "finish":
                    try:
                        ss_obs = await _observe_page(page)
                        screenshot_b64 = ss_obs.get("screenshot_b64", "")
                    except Exception:
                        pass

                duration_ms = int((time.time() - t0) * 1000)

                step = AgentStep(
                    step_id=step_id,
                    thought=thought,
                    action=action,
                    params=params,
                    success=success,
                    error=error,
                    screenshot_b64=screenshot_b64,
                    duration_ms=duration_ms,
                )

                # 观察
                if action != "finish":
                    try:
                        new_obs = await _observe_page(page)
                        step.observation = _format_observation(new_obs)
                        if visual_description:
                            step.observation += visual_description
                        result.final_url = new_obs["url"]
                        result.final_title = new_obs["title"]
                    except Exception as e:
                        step.observation = f"观察失败: {e}"

                # 记录到长期记忆
                if action in ("click", "input", "select", "wait_for") and params.get("selector"):
                    from backend.core.agent_memory import agent_memory, ExperienceType
                    try:
                        if success:
                            agent_memory.record(
                                exp_type=ExperienceType.SUCCESS_PATTERN,
                                key=params["selector"][:200],
                                context={"action": action, "params": {k: v for k, v in params.items() if k != "value"}},
                                outcome="success",
                                domain=domain,
                            )
                        else:
                            agent_memory.record(
                                exp_type=ExperienceType.FAILURE_PATTERN,
                                key=params["selector"][:200],
                                context={"action": action, "error": error[:200]},
                                outcome="failure",
                                domain=domain,
                            )
                    except Exception:
                        pass

                result.steps.append(step)

                # 把这步加到 LLM 历史
                history.append({
                    "role": "assistant",
                    "content": json.dumps(decision, ensure_ascii=False),
                })
                if not success:
                    history.append({
                        "role": "user",
                        "content": f"⚠️ 上一步执行失败：{error}\n请尝试其他方案。\n\n{step.observation or '请重新观察页面'}",
                    })
                elif action != "finish":
                    history.append({
                        "role": "user",
                        "content": f"✅ 步骤 {step_id} 执行成功。\n\n{step.observation or ''}\n\n请决定下一步动作。",
                    })

                # 终止条件
                if action == "finish":
                    result.success = bool(params.get("success", True))
                    result.finish_reason = params.get("reason", "LLM 主动结束")
                    break

                if not success:
                    # 失败后让 LLM 继续决策一次（已经加到历史了）
                    if step_id >= max_steps - 1:
                        result.finish_reason = f"达到最大步数 {max_steps} 后仍有失败"
                        break

            # 收尾
            try:
                final_obs = await _observe_page(page)
                result.final_screenshot_b64 = final_obs.get("screenshot_b64", "")
                result.final_url = final_obs.get("url", result.final_url)
                result.final_title = final_obs.get("title", result.final_title)
            except Exception:
                pass

            await context.close()
            await browser.close()

    except Exception as e:
        result.error = f"Agent 运行异常: {e}"
        result.finish_reason = "异常退出"
        logger.exception("BrowserAgent 运行失败")

    result.total_duration_ms = int((time.time() - start_time) * 1000)
    if not result.finish_reason:
        result.finish_reason = f"达到最大步数 {max_steps}"

    # 把自愈引擎数据存到结果（通过给 AgentResult 动态挂载）
    result.heal_summary = self_healer_engine.summary()

    # 记录任务级经验
    try:
        from backend.core.agent_memory import agent_memory, ExperienceType
        agent_memory.record_task_outcome(
            task=task,
            domain=domain,
            success=result.success,
            final_url=result.final_url,
            step_count=len(result.steps),
            duration_ms=result.total_duration_ms,
        )
    except Exception:
        pass

    return result


# ============================================================
# 同步包装（用于直接调用）
# ============================================================

def run_browser_agent_sync(task: str, start_url: str = "", max_steps: int = 12) -> dict:
    """同步入口"""
    result = asyncio.run(run_browser_agent(task, start_url, max_steps))
    return result.to_dict()
