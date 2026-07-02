"""多 Agent 协作 — 浏览器测试专用版本（分析-执行-验证）

针对图片中"多 Agent 协作（分析-执行-验证）"需求：
  - Analyst Agent  分析网站结构和目标，输出执行计划
  - Executor Agent 调用 BrowserAgent 执行每步
  - Verifier Agent 验证执行结果（多维度核对）

现有 multi_agent.py 专注于代码测试生成，不适用于浏览器操控；
本模块专注于浏览器端到端测试的多 Agent 协作。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from backend.config import settings
from backend.core.browser_agent import _call_llm, _parse_llm_action, AGENT_ACTIONS, SYSTEM_PROMPT
from backend.core.visual_locator import locate_element_by_visual

logger = logging.getLogger("testforge")


@dataclass
class AnalystPlan:
    """分析师输出的执行计划"""
    task: str
    domain: str
    objectives: list[str] = field(default_factory=list)         # 测试目标
    preconditions: list[str] = field(default_factory=list)      # 前置条件
    steps: list[dict] = field(default_factory=list)              # 执行步骤
    risks: list[str] = field(default_factory=list)                # 风险点
    estimated_difficulty: str = "medium"                          # easy/medium/hard

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "domain": self.domain,
            "objectives": self.objectives,
            "preconditions": self.preconditions,
            "steps": self.steps,
            "risks": self.risks,
            "estimated_difficulty": self.estimated_difficulty,
            "step_count": len(self.steps),
        }


@dataclass
class ExecutorResult:
    """执行者结果"""
    success: bool
    steps_executed: int
    steps_passed: int
    steps_failed: int
    final_url: str
    final_title: str
    screenshots: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "steps_executed": self.steps_executed,
            "steps_passed": self.steps_passed,
            "steps_failed": self.steps_failed,
            "final_url": self.final_url,
            "final_title": self.final_title,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
        }


@dataclass
class VerifierVerdict:
    """验证者裁决"""
    overall_passed: bool
    confidence: float
    checks: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_passed": self.overall_passed,
            "confidence": self.confidence,
            "checks": self.checks,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


class AnalystAgent:
    """分析师 — 分析任务和网站，输出执行计划"""

    SYSTEM_PROMPT = """你是测试分析师。用户的任务是用浏览器自动完成某个网站操作（如登录、下单、搜索）。

请分析任务并输出：
{
  "domain": "<网站域名，从start_url提取>",
  "objectives": ["目标1", "目标2", ...],
  "preconditions": ["前置条件1", ...],
  "steps": [
    {"action": "navigate/click/input/...", "params": {...}, "description": "...", "expected_outcome": "..."}
  ],
  "risks": ["可能的风险点1（如元素名称变化、需验证码、需登录等）"],
  "estimated_difficulty": "easy/medium/hard"
}

策略：
- 步骤要细粒度（navigate→wait→input→click→assert）
- selector 优先用 #id、[data-testid]、[name]，次选 text 匹配
- 关键操作后必须用 assert 验证
- 估计难度：easy=纯展示页，medium=需登录或交互，hard=验证码/复杂流程

只输出 JSON。"""

    async def analyze(self, task: str, start_url: str) -> AnalystPlan:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""任务：{task}
起始 URL：{start_url}

请分析并输出执行计划：""",
            },
        ]
        try:
            text = await _call_llm(messages, max_tokens=1500, temperature=0.2)
            obj = _parse_llm_action(text)
            domain = obj.get("domain", "")
            if not domain and start_url:
                # 从 URL 提取域名
                from urllib.parse import urlparse
                domain = urlparse(start_url).netloc
            return AnalystPlan(
                task=task,
                domain=domain or "",
                objectives=obj.get("objectives", []),
                preconditions=obj.get("preconditions", []),
                steps=obj.get("steps", []),
                risks=obj.get("risks", []),
                estimated_difficulty=obj.get("estimated_difficulty", "medium"),
            )
        except Exception as e:
            logger.warning("分析失败: %s", e)
            # 兜底：单步 navigate
            return AnalystPlan(
                task=task,
                domain="",
                steps=[{"action": "navigate", "params": {"url": start_url}, "description": f"打开 {start_url}"}],
            )


class ExecutorAgent:
    """执行者 — 调用 BrowserAgent 执行计划"""

    async def execute(self, plan: AnalystPlan, max_steps: int = 12) -> ExecutorResult:
        from backend.core.browser_agent import run_browser_agent

        # 把分析师计划转成自然语言任务给 BrowserAgent
        composed_task = plan.task
        if plan.objectives:
            composed_task += f"\n\n目标：\n" + "\n".join(f"- {o}" for o in plan.objectives)

        result = await run_browser_agent(
            task=composed_task,
            start_url=plan.steps[0].get("params", {}).get("url", "") if plan.steps and plan.steps[0].get("action") == "navigate" else "",
            max_steps=max_steps,
        )

        errors = [s.error for s in result.steps if not s.success and s.error]
        return ExecutorResult(
            success=result.success,
            steps_executed=len(result.steps),
            steps_passed=sum(1 for s in result.steps if s.success),
            steps_failed=sum(1 for s in result.steps if not s.success),
            final_url=result.final_url,
            final_title=result.final_title,
            screenshots=[s.screenshot_b64 for s in result.steps if s.screenshot_b64],
            errors=errors,
            duration_ms=result.total_duration_ms,
        )


class VerifierAgent:
    """验证者 — 多维度核对执行结果"""

    SYSTEM_PROMPT = """你是测试验证专家。请基于任务目标，验证执行结果是否达成。

对每项目标给出检查结果：
{
  "checks": [
    {"objective": "目标1", "passed": true/false, "evidence": "观察到的证据", "confidence": 0.0-1.0}
  ],
  "overall_passed": true/false,
  "confidence": 0.0-1.0,
  "issues": ["问题1", "问题2"],
  "suggestions": ["改进建议1", ...]
}

判断标准：
- 页面是否到达预期 URL
- 关键元素是否出现
- 是否有错误提示
- 整体流程是否顺畅

只输出 JSON。"""

    async def verify(
        self,
        plan: AnalystPlan,
        exec_result: ExecutorResult,
    ) -> VerifierVerdict:
        # 构造验证输入
        exec_summary = f"""执行结果：
- 成功: {exec_result.success}
- 通过: {exec_result.steps_passed}/{exec_result.steps_executed}
- 最终 URL: {exec_result.final_url}
- 最终标题: {exec_result.final_title}
- 错误: {exec_result.errors[:3]}
- 耗时: {exec_result.duration_ms}ms"""

        objectives_text = "\n".join(f"- {o}" for o in plan.objectives) or "- 完成整体任务"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""任务：{plan.task}

测试目标：
{objectives_text}

{exec_summary}

请验证：""",
            },
        ]
        try:
            text = await _call_llm(messages, max_tokens=1000, temperature=0.0)
            obj = _parse_llm_action(text)
            return VerifierVerdict(
                overall_passed=bool(obj.get("overall_passed", False)),
                confidence=float(obj.get("confidence", 0.5)),
                checks=obj.get("checks", []),
                issues=obj.get("issues", []),
                suggestions=obj.get("suggestions", []),
            )
        except Exception as e:
            logger.warning("验证失败: %s", e)
            return VerifierVerdict(
                overall_passed=exec_result.success,
                confidence=0.5,
                issues=[f"验证异常: {e}"],
            )


# ============ 多 Agent 协作主流程 ============

@dataclass
class MultiAgentReport:
    """多 Agent 协作完整报告"""
    plan: AnalystPlan
    execution: ExecutorResult
    verification: VerifierVerdict
    total_duration_ms: int = 0
    agent_timeline: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "plan": self.plan.to_dict(),
            "execution": self.execution.to_dict(),
            "verification": self.verification.to_dict(),
            "total_duration_ms": self.total_duration_ms,
            "agent_timeline": self.agent_timeline,
            "summary": {
                "analyst": f"识别 {len(self.plan.objectives)} 个目标, 计划 {len(self.plan.steps)} 步, 难度 {self.plan.estimated_difficulty}",
                "executor": f"执行 {self.execution.steps_executed} 步, 通过 {self.execution.steps_passed}, 失败 {self.execution.steps_failed}",
                "verifier": f"整体{'通过' if self.verification.overall_passed else '不通过'}, 置信度 {self.verification.confidence:.0%}",
            },
        }


async def run_browser_multi_agent(
    task: str,
    start_url: str = "",
    max_steps: int = 12,
) -> MultiAgentReport:
    """多 Agent 协作：分析 → 执行 → 验证"""
    t0 = time.time()
    timeline = []

    # 1. Analyst 分析
    analyst = AnalystAgent()
    t1 = time.time()
    plan = await analyst.analyze(task, start_url)
    timeline.append({
        "agent": "Analyst",
        "duration_ms": int((time.time() - t1) * 1000),
        "output": plan.to_dict(),
    })

    # 2. Executor 执行
    executor = ExecutorAgent()
    t2 = time.time()
    exec_result = await executor.execute(plan, max_steps=max_steps)
    timeline.append({
        "agent": "Executor",
        "duration_ms": int((time.time() - t2) * 1000),
        "output": exec_result.to_dict(),
    })

    # 3. Verifier 验证
    verifier = VerifierAgent()
    t3 = time.time()
    verdict = await verifier.verify(plan, exec_result)
    timeline.append({
        "agent": "Verifier",
        "duration_ms": int((time.time() - t3) * 1000),
        "output": verdict.to_dict(),
    })

    return MultiAgentReport(
        plan=plan,
        execution=exec_result,
        verification=verdict,
        total_duration_ms=int((time.time() - t0) * 1000),
        agent_timeline=timeline,
    )
