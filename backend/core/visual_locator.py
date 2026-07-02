"""视觉定位器 — 截图 + 元素名称 → 坐标

根据图片中的要求，元素视觉定位的完整工作流：
  1. 调用视觉语言模型（VLM）分析当前页面截图
  2. 输入元素描述（如"登录按钮"），VLM 返回屏幕坐标 (x, y)
  3. 用 Playwright 的 mouse.click(x, y) 直接点击坐标
  4. 比 selector 匹配更鲁棒（按钮改名/改样式后仍可工作）

降级方案：
  - 无 VLM API 时用 a11y tree 找元素中心坐标（基于 getBoundingClientRect）
  - VLM 出错时自动降级

支持的多模态模型：
  - Qwen2-VL（DashScope 官方）
  - GPT-4o vision
  - Claude 3 vision（任意 OpenAI 兼容 API）
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from typing import Optional, Tuple

from backend.config import settings

logger = logging.getLogger("testforge")


# ============ 视觉定位核心函数 ============

async def locate_element_by_visual(
    page,
    element_description: str,
    timeout: int = 30,
) -> dict:
    """视觉定位：在截图上找到目标元素，返回坐标

    Args:
        page: Playwright page 对象
        element_description: 元素描述，如"登录按钮"、"搜索框"、"Sign In 链接"
        timeout: 视觉模型超时（秒）

    Returns:
        {"found": bool, "x": int, "y": int, "method": "vlm"|"a11y_fallback",
         "confidence": float, "box": [x1,y1,x2,y2], "raw_response": str}
    """
    # 1. 截屏
    try:
        img_bytes = await page.screenshot(full_page=False, type="jpeg", quality=75)
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        return {"found": False, "error": f"截图失败: {e}", "method": "none"}

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    img_w, img_h = viewport["width"], viewport["height"]

    # 2. 尝试 VLM 定位
    vlm_result = await _call_vlm_for_localization(
        img_b64, element_description, img_w, img_h, timeout
    )

    if vlm_result.get("found"):
        return {**vlm_result, "method": "vlm"}

    # 3. 降级：用 a11y tree 找元素（不依赖视觉模型）
    logger.info("VLM 定位失败，降级到 a11y 坐标定位")
    a11y_result = await _locate_via_a11y(page, element_description)
    return {**a11y_result, "method": "a11y_fallback"}


async def click_by_visual(page, element_description: str, timeout: int = 30) -> dict:
    """一站式视觉点击：定位 → 校验 → 点击

    Returns:
        {"success": bool, "x": int, "y": int, "method": str, "error": str}
    """
    loc = await locate_element_by_visual(page, element_description, timeout)
    if not loc.get("found"):
        return {"success": False, "error": loc.get("error", "未找到元素"), "location": loc}

    x, y = loc["x"], loc["y"]
    try:
        await page.mouse.click(x, y)
        return {
            "success": True,
            "x": x, "y": y,
            "method": loc.get("method", "unknown"),
            "confidence": loc.get("confidence", 0.0),
        }
    except Exception as e:
        return {"success": False, "error": f"点击失败: {e}", "location": loc}


# ============ 视觉语言模型调用 ============

VLM_SYSTEM_PROMPT = """你是一个 UI 元素视觉定位助手。用户会给一张网页截图和一个元素描述，
请输出该元素在截图中的**像素坐标**（中心点）。

严格要求：
1. 仔细观察截图，找到用户描述的元素
2. 如果找不到，返回 {"found": false, "reason": "..."}
3. 如果找到，返回 JSON：
   {"found": true, "x": <中心点x像素>, "y": <中心点y像素>, "confidence": 0.0-1.0, "box": [x1,y1,x2,y2]}

只输出 JSON，不要其他文字。"""


async def _call_vlm_for_localization(
    img_b64: str, description: str, img_w: int, img_h: int, timeout: int
) -> dict:
    """调用多模态 LLM 定位元素"""
    api_key = settings.llm_api_key
    api_base = settings.llm_api_base

    if not api_key:
        return {"found": False, "error": "未配置 LLM API Key"}

    # 构造多模态消息
    messages = [
        {"role": "system", "content": VLM_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"请在截图中找到: {description}\n截图尺寸: {img_w}x{img_h}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            ],
        },
    ]

    body = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 300,
    }

    # 优先尝试 DashScope qwen-vl 系列（如果配置了视觉模型）
    vision_models = ["qwen-vl-plus", "qwen-vl-max", "qvq-plus", "gpt-4o", "claude-3"]
    is_vision = any(m in settings.llm_model.lower() for m in vision_models)
    if not is_vision and "vl" not in settings.llm_model.lower():
        # 主模型不是视觉模型，尝试用 qwen-vl-plus 临时切换
        body["model"] = "qwen-vl-plus"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{api_base}/chat/completions"

    try:
        import aiohttp
        async with aiohttp.ClientTimeout(total=timeout):
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=body, headers=headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return {"found": False, "error": f"VLM HTTP {resp.status}: {err[:200]}"}
                    data = await resp.json(content_type=None)
                    text = data["choices"][0]["message"]["content"]
                    return _parse_vlm_response(text, img_w, img_h)
    except Exception as e:
        return {"found": False, "error": f"VLM 调用异常: {type(e).__name__}: {e}"}


def _parse_vlm_response(text: str, img_w: int, img_h: int) -> dict:
    """解析 VLM 返回的 JSON 坐标"""
    text = text.strip()
    # 直接 JSON
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # 提取 ```json ... ```
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(1))
            except Exception:
                return {"found": False, "error": f"VLM 响应解析失败: {text[:200]}"}
        else:
            # 提取第一个 { ... }
            m2 = re.search(r"\{.*?\}", text, re.DOTALL)
            if m2:
                try:
                    obj = json.loads(m2.group(0))
                except Exception:
                    return {"found": False, "error": f"VLM 响应解析失败: {text[:200]}"}
            else:
                return {"found": False, "error": f"VLM 响应无 JSON: {text[:200]}"}

    if not obj.get("found"):
        return {"found": False, "error": obj.get("reason", "VLM 未找到元素")}

    x, y = int(obj.get("x", 0)), int(obj.get("y", 0))
    # 边界裁剪
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))

    return {
        "found": True,
        "x": x, "y": y,
        "box": obj.get("box", [x - 20, y - 20, x + 20, y + 20]),
        "confidence": float(obj.get("confidence", 0.5)),
        "raw_response": text,
    }


# ============ a11y 降级方案 ============

async def _locate_via_a11y(page, description: str) -> dict:
    """无 VLM 时，用 a11y tree + 元素中心坐标定位

    策略：在可访问树中匹配文本/aria-label，返回元素 bounding box 中心
    """
    desc_lower = description.lower().strip()
    desc_keywords = re.findall(r"[\w\u4e00-\u9fa5]+", desc_lower)

    if not desc_keywords:
        return {"found": False, "error": "元素描述无效"}

    try:
        candidates = await page.evaluate("""(keywords) => {
            const results = [];
            const all = document.querySelectorAll('button, a, input, textarea, select, [role="button"], h1, h2, h3, h4, h5, h6, label, span, div');
            for (const el of all) {
                const rect = el.getBoundingClientRect();
                // 跳过不可见元素
                if (rect.width < 5 || rect.height < 5) continue;
                if (rect.right < 0 || rect.bottom < 0) continue;
                if (rect.left > window.innerWidth || rect.top > window.innerHeight) continue;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;

                const text = (el.innerText || el.textContent || '').trim();
                const aria = el.getAttribute('aria-label') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const name = el.getAttribute('name') || '';
                const testid = el.getAttribute('data-testid') || '';
                const id = el.id || '';
                const tag = el.tagName.toLowerCase();
                const type = el.getAttribute('type') || '';

                const searchable = [text, aria, placeholder, name, testid, id, tag, type].join(' ').toLowerCase();
                let score = 0;
                for (const kw of keywords) {
                    if (searchable.includes(kw.toLowerCase())) score += 1;
                }
                if (score > 0) {
                    results.push({
                        score, tag, text: text.slice(0, 60), aria, placeholder, name, testid, id, type,
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2),
                        box: [Math.round(rect.left), Math.round(rect.top), Math.round(rect.right), Math.round(rect.bottom)],
                        visible: true,
                    });
                }
            }
            results.sort((a, b) => b.score - a.score);
            return results.slice(0, 5);
        }""", desc_keywords)
    except Exception as e:
        return {"found": False, "error": f"a11y 扫描失败: {e}"}

    if not candidates:
        return {"found": False, "error": f"a11y 树中未找到匹配 '{description}' 的可见元素"}

    best = candidates[0]
    return {
        "found": True,
        "x": best["x"],
        "y": best["y"],
        "box": best["box"],
        "confidence": min(0.8, best["score"] / len(desc_keywords)),
        "matched_element": {
            "tag": best["tag"],
            "text": best["text"],
            "aria": best["aria"],
            "id": best["id"],
            "testid": best["testid"],
        },
        "alternatives": candidates[1:],
    }


# ============ 智能选择器推荐（结合 a11y 树）============

async def smart_locate(page, target: str, prefer_visual: bool = False) -> dict:
    """智能定位：先尝试 selector → 失败后用 a11y → 最后用视觉

    Args:
        page: Playwright page
        target: selector 或元素描述
        prefer_visual: 优先用视觉（默认 False，先尝试 a11y 因为更便宜）

    Returns:
        {"strategy": "selector"|"a11y"|"visual", "selector": str, "x": int, "y": int}
    """
    # 1. 直接尝试 selector
    if target.startswith("#") or target.startswith(".") or target.startswith("[") or "<" in target:
        try:
            count = await page.locator(target).count()
            if count > 0:
                return {"strategy": "selector", "selector": target}
        except Exception:
            pass

    # 2. 视觉定位
    if prefer_visual:
        vis = await locate_element_by_visual(page, target)
        if vis.get("found"):
            return {
                "strategy": "visual",
                "x": vis["x"], "y": vis["y"],
                "method": vis.get("method", "vlm"),
                "confidence": vis.get("confidence", 0.5),
            }

    # 3. a11y 降级
    a11y = await _locate_via_a11y(page, target)
    if a11y.get("found"):
        return {
            "strategy": "a11y",
            "x": a11y["x"], "y": a11y["y"],
            "matched": a11y.get("matched_element"),
            "confidence": a11y.get("confidence", 0.5),
        }

    return {"strategy": "none", "error": f"无法定位: {target}"}


# ============ 批量标注所有可见元素（VLM 场景理解）============

async def enumerate_visible_elements(page) -> list[dict]:
    """枚举页面上所有可见元素及其位置信息

    用 a11y tree 提取 + 计算坐标，无需调用 VLM
    用于辅助 LLM 决策"页面有哪些可点击元素"
    """
    try:
        elements = await page.evaluate("""() => {
            const results = [];
            const all = document.querySelectorAll('button, a, input, textarea, select, [role="button"]');
            let idx = 0;
            for (const el of all) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 5 || rect.height < 5) continue;
                if (rect.left > window.innerWidth || rect.top > window.innerHeight) continue;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') continue;

                const text = (el.innerText || el.textContent || '').trim().slice(0, 50);
                const tag = el.tagName.toLowerCase();
                const id = el.id || '';
                const testid = el.getAttribute('data-testid') || '';
                const name = el.getAttribute('name') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const aria = el.getAttribute('aria-label') || '';
                const type = el.getAttribute('type') || '';

                idx += 1;
                results.push({
                    index: idx,
                    tag, id, testid, name, type, placeholder, aria, text,
                    selector: id ? '#' + id : testid ? '[data-testid="' + testid + '"]' :
                              (text ? tag + ':has-text("' + text.slice(0, 20) + '")' : ''),
                    x: Math.round(rect.left + rect.width / 2),
                    y: Math.round(rect.top + rect.height / 2),
                });
                if (results.length >= 50) break;
            }
            return results;
        }""")
        return elements
    except Exception as e:
        logger.warning("枚举可见元素失败: %s", e)
        return []
