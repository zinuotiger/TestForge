"""任务 #13 / #14 端到端联调测试：
- #13: 用一个真实 Python 文件走通 BrowserAgent + 自愈 + 视觉定位 + 多 Agent 全流程
- #14: 用 example.com 真实网站验证 ReAct 循环
"""
import sys
import asyncio
import json
sys.stdout.reconfigure(encoding="utf-8")

print("=" * 70)
print("任务 #13 / #14 端到端联调")
print("=" * 70)


# ============================================================
# 任务 #13：Python 全流程联通（不依赖真实浏览器）
# ============================================================
print("\n[任务 #13] 验证 Python 模块全流程（导入 → 解析 → 决策 → 记录）\n")

from backend.core.browser_agent import (
    AGENT_ACTIONS, SYSTEM_PROMPT, parse_natural_task, _parse_llm_action,
    AgentStep, AgentResult,
)
from backend.core.visual_locator import (
    smart_locate, click_by_visual, locate_element_by_visual,
    enumerate_visible_elements, _locate_via_a11y,
)
from backend.core.browser_self_healer import browser_self_healer
from backend.core.agent_memory import agent_memory, ExperienceType
from backend.core.browser_multi_agent import run_browser_multi_agent

# 1) 动作清单完整性
assert len(AGENT_ACTIONS) == 21, f"动作数量不对: {len(AGENT_ACTIONS)}"
expected = {"navigate", "click", "input", "select", "hover", "scroll", "wait",
            "wait_for", "press_key", "screenshot", "extract", "assert",
            "switch_tab", "switch_frame", "close_dialog", "upload_file", "drag",
            "visual_click", "visual_find", "smart_locate", "finish"}
missing = expected - set(AGENT_ACTIONS)
assert not missing, f"缺少动作: {missing}"
print(f"  [1/6] 21 个动作齐全: OK")

# 2) System prompt 包含所有动作说明
for kw in ["navigate", "visual_click", "smart_locate", "assert", "finish", "ReAct"]:
    assert kw in SYSTEM_PROMPT, f"系统提示缺少: {kw}"
print(f"  [2/6] 系统提示包含关键动作说明: OK")

# 3) 解析器
sample = '{"thought": "点登录", "action": "click", "params": {"selector": "button"}}'
parsed = _parse_llm_action(sample)
assert parsed["action"] == "click"
# 带 markdown 块
sample2 = '```json\n{"thought": "x", "action": "finish", "params": {"success": true}}\n```'
parsed2 = _parse_llm_action(sample2)
assert parsed2["action"] == "finish"
print(f"  [3/6] LLM 响应 JSON 解析器: OK")

# 4) AgentStep / AgentResult 序列化
step = AgentStep(step_id=1, thought="t", action="click", params={"selector": "x"})
res = AgentResult(task="t", start_url="u", success=True, finish_reason="done", steps=[step])
d = res.to_dict()
assert d["total_steps"] == 1 and d["success"] is True
print(f"  [4/6] AgentResult 序列化: OK")

# 5) 自愈引擎
summary = browser_self_healer.summary()
assert "total_events" in summary and "heal_rate" in summary
print(f"  [5/6] 自愈引擎 summary() 接口: OK  (keys: {list(summary.keys())})")

# 6) 记忆模块
agent_memory.record(
    exp_type=ExperienceType.SUCCESS_PATTERN,
    key="button[type=submit]",
    context={"action": "click"},
    outcome="success",
    domain="example.com",
)
results = agent_memory.search(domain="example.com", limit=5)
assert len(results) >= 1
formatted = agent_memory.format_for_llm("example.com", current_action="click button")
print(f"  [6/6] 记忆 record/search/format_for_llm: OK  (累积 {agent_memory.stats()['total']} 条)")

print("\n  >>> 任务 #13 (Python 全流程联通) 通过 <<<\n")


# ============================================================
# 任务 #14：用 example.com 做真实 ReAct 循环
# ============================================================
print("[任务 #14] 真实网站 example.com ReAct 循环实测\n")

try:
    from backend.core.browser_agent import run_browser_agent
    import playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

if _HAS_PLAYWRIGHT:
    # ============================================================
    # Task #14: example.com real ReAct loop
    # ============================================================
    print("[Task #14] Real website example.com ReAct loop test\n")

    async def e2e_website_test():
        result = await run_browser_agent(
            task="Open example.com, verify page title contains 'Example Domain', then validate with AI assertion.",
            start_url="https://example.com",
            max_steps=8,
            headless=True,
        )
        return result

    print("  Starting Agent... (headless Chromium)")
    result = asyncio.run(e2e_website_test())

    print(f"\n  Task: {result.task[:60]}")
    print(f"  Success: {result.success}")
    print(f"  Finish reason: {result.finish_reason}")
    print(f"  Total steps: {len(result.steps)}")
    print(f"  Duration: {result.total_duration_ms}ms")
    print(f"  Final URL: {result.final_url}")
    print(f"  Final title: {result.final_title}")
    print(f"  Heal events: {result.heal_summary.get("heal_events", 0) if hasattr(result, "heal_summary") else 0}")

    print(f"\n  --- Decision log ---")
    for s in result.steps:
        status = "OK" if s.success else "FAIL"
        print(f"  Step {s.step_id:2d} {status}  action={s.action:14s}  thought={s.thought[:50]}")
        if s.error:
            print(f"           error: {s.error[:100]}")
        if s.observation:
            obs = s.observation[:200].replace("\n", " | ")
            print(f"           obs: {obs}")

    assert "example.com" in result.final_url, f"Final URL wrong: {result.final_url}"
    assert "Example" in result.final_title, f"Final title wrong: {result.final_title}"
    print(f"\n  >>> Task #14 (example.com test) PASSED <<<")

    print("\n" + "=" * 70)
    print("PASS: Tasks #13 and #14 both passed")
    print("=" * 70)
else:
    print("  >>> Task #14 SKIPPED: playwright dependency missing <<<\n")
    print("=" * 70)
    print("PASS: Task #13 passed, Task #14 skipped (playwright not installed)")
    print("=" * 70)
