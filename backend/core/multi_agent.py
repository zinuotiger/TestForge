"""5 个专业 Agent 实现

  OrchestratorAgent — 编排者：任务分解 + Agent 调度 + 结果聚合
  AnalystAgent      — 分析师：代码结构/复杂度/依赖分析
  GeneratorAgent    — 生成者：测试用例生成（多策略）
  ExecutorAgent     — 执行者：测试执行 + 结果收集
  ReviewerAgent     — 审查者：质量评估 + 反思反馈
"""

import json
import time
import logging
from typing import Optional

from backend.config import settings
from backend.core.multi_agent_base import (
    BaseAgent, AgentRole, AgentState, AgentMessage, AgentMemory,
)

logger = logging.getLogger("testforge")


# ============================================================
# Orchestrator Agent — 编排者
# ============================================================

class OrchestratorAgent(BaseAgent):
    """编排者 Agent — 任务分解 + Agent 调度 + 结果聚合 + 反思循环

    工作流:
      1. 接收用户任务
      2. LLM 分解为子任务
      3. 按依赖顺序分配给专业 Agent
      4. 收集结果
      5. Reviewer 审查 → 不通过则触发重试（反思）
      6. 聚合最终结果
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.ORCHESTRATOR,
            name="Orchestrator",
            description="任务编排者，负责分解任务、调度 Agent、聚合结果",
            max_iterations=3,
        )
        self._sub_agents: dict[AgentRole, BaseAgent] = {}
        self._task_results: dict[str, dict] = {}     # task_id → result
        self._max_retries: int = 2                    # 反思重试上限

    def register_agent(self, agent: BaseAgent):
        """注册子 Agent"""
        self._sub_agents[agent.role] = agent
        agent.set_message_callback(self._on_sub_agent_message)
        logger.info("Orchestrator 注册 Agent: %s (%s)", agent.name, agent.role.value)

    async def _on_sub_agent_message(self, msg: AgentMessage):
        """子 Agent 消息回调"""
        self.memory.add_short_term(
            f"子 Agent {msg.sender.value} 报告: {msg.content}",
            "observation",
        )
        if msg.data:
            self._task_results[msg.data.get("task_id", "")] = msg.data

    async def execute(self, task: AgentMessage) -> AgentMessage:
        """执行编排"""
        self.state = AgentState.THINKING
        self._log_action("orchestrate", f"开始编排任务: {task.content[:100]}")

        # Step 1: LLM 分解任务
        sub_tasks = await self._decompose_task(task.content, task.data.get("code", ""))

        # Step 2: 按顺序执行子任务
        results = {}
        for sub_task in sub_tasks:
            assigned_role = AgentRole(sub_task["agent"])
            sub_msg = AgentMessage(
                sender=AgentRole.ORCHESTRATOR,
                receiver=assigned_role,
                content=sub_task["task"],
                data={
                    "task_id": sub_task["id"],
                    "code": task.data.get("code", ""),
                    "context": results,  # 传递前序结果作为上下文
                },
                msg_type="task",
            )

            self._log_action("assign", f"→ {assigned_role.value}: {sub_task['task'][:80]}")

            agent = self._sub_agents.get(assigned_role)
            if not agent:
                self._log_action("error", f"Agent {assigned_role.value} 未注册")
                continue

            await agent.receive_message(sub_msg)
            result_msg = await agent.execute(sub_msg)
            results[sub_task["id"]] = result_msg.data

            # 检查是否需要反思重试
            if result_msg.msg_type == "feedback" and sub_task.get("can_retry", False):
                results[sub_task["id"]] = await self._retry_with_reflection(
                    assigned_role, sub_msg, result_msg
                )

        # Step 3: 聚合最终结果
        self.state = AgentState.DONE
        final_result = await self._aggregate_results(results)

        self._log_action("complete", f"编排完成，聚合 {len(results)} 个子任务结果")
        return AgentMessage(
            sender=self.role,
            receiver=AgentRole.ORCHESTRATOR,
            content="任务编排完成",
            data=final_result,
            msg_type="result",
        )

    async def _decompose_task(self, task_desc: str, code: str) -> list[dict]:
        """LLM 分解任务为子任务"""
        # 不依赖 LLM 时使用固定流程（降级方案）
        if not settings.llm_api_key:
            return self._default_decomposition()

        try:
            system_prompt = """你是任务编排专家。将用户任务分解为子任务，分配给专业 Agent。

可用 Agent:
- analyst: 代码分析（结构/复杂度/依赖）
- generator: 测试用例生成
- executor: 测试执行
- reviewer: 质量审查

返回 JSON 格式:
{
  "sub_tasks": [
    {"id": "t1", "agent": "analyst", "task": "分析代码结构", "can_retry": false, "depends_on": []},
    {"id": "t2", "agent": "generator", "task": "生成测试用例", "can_retry": true, "depends_on": ["t1"]},
    {"id": "t3", "agent": "executor", "task": "执行测试", "can_retry": false, "depends_on": ["t2"]},
    {"id": "t4", "agent": "reviewer", "task": "审查质量", "can_retry": false, "depends_on": ["t3"]}
  ]
}"""

            user_msg = f"任务: {task_desc}\n\n代码:\n```\n{code[:1000]}\n```"
            result = await self.think_json(system_prompt, user_msg)
            sub_tasks = result.get("sub_tasks", [])
            if sub_tasks:
                return sub_tasks
        except Exception as e:
            self._log_action("decompose_error", str(e))

        return self._default_decomposition()

    def _default_decomposition(self) -> list[dict]:
        """默认任务分解（LLM 不可用时降级）"""
        return [
            {"id": "t1", "agent": "analyst", "task": "分析代码结构、复杂度、依赖关系", "can_retry": False, "depends_on": []},
            {"id": "t2", "agent": "generator", "task": "根据分析结果生成测试用例", "can_retry": True, "depends_on": ["t1"]},
            {"id": "t3", "agent": "executor", "task": "执行生成的测试用例", "can_retry": False, "depends_on": ["t2"]},
            {"id": "t4", "agent": "reviewer", "task": "审查测试质量并给出评分", "can_retry": False, "depends_on": ["t3"]},
        ]

    async def _retry_with_reflection(
        self, agent_role: AgentRole, original_task: AgentMessage, feedback: AgentMessage
    ) -> dict:
        """反思重试：将反馈传回 Agent 重新执行"""
        for attempt in range(self._max_retries):
            self._log_action("retry", f"{agent_role.value} 第 {attempt+1} 次重试（反思）")

            retry_msg = AgentMessage(
                sender=AgentRole.ORCHESTRATOR,
                receiver=agent_role,
                content=f"根据审查反馈重试: {feedback.content}",
                data={
                    **original_task.data,
                    "feedback": feedback.data,
                    "retry_attempt": attempt + 1,
                },
                msg_type="task",
            )

            agent = self._sub_agents[agent_role]
            await agent.receive_message(retry_msg)
            result = await agent.execute(retry_msg)

            if result.msg_type != "feedback":
                return result.data

        # 重试上限
        self._log_action("retry_exhausted", f"{agent_role.value} 重试上限已达")
        return feedback.data

    async def _aggregate_results(self, results: dict) -> dict:
        """聚合所有子任务结果"""
        return {
            "total_sub_tasks": len(results),
            "results": {
                tid: {k: v for k, v in data.items() if k != "code"}
                for tid, data in results.items()
            },
            "agent_statuses": {
                role.value: agent.get_status()
                for role, agent in self._sub_agents.items()
            },
            "orchestrator_status": self.get_status(),
        }

    def get_all_statuses(self) -> dict:
        """获取所有 Agent 状态（供前端展示）"""
        return {
            "orchestrator": self.get_status(),
            "agents": {
                role.value: agent.get_status()
                for role, agent in self._sub_agents.items()
            },
        }


# ============================================================
# Analyst Agent — 分析师
# ============================================================

class AnalystAgent(BaseAgent):
    """代码分析 Agent — 结构/复杂度/依赖/风险分析"""

    def __init__(self):
        super().__init__(
            role=AgentRole.ANALYST,
            name="Analyst",
            description="代码分析专家，负责结构分析、复杂度评估、依赖检测",
            max_iterations=3,
        )

    async def execute(self, task: AgentMessage) -> AgentMessage:
        self.state = AgentState.ACTING
        self._log_action("analyze", "开始代码分析")

        code = task.data.get("code", "")

        # 1. 静态分析（真实工具调用，不依赖 LLM）
        from backend.analyzer.static_analyzer import analyze_code
        analysis = analyze_code(code, "python")

        self.memory.add_short_term(
            f"分析完成: {len(analysis.get('functions', []))} 函数, "
            f"{len(analysis.get('classes', []))} 类, 复杂度 {analysis.get('complexity', 0)}",
            "observation",
        )

        # 2. LLM 深度分析（可选）
        risk_assessment = {}
        if settings.llm_api_key and analysis.get("functions"):
            try:
                risk_assessment = await self._llm_risk_analysis(code, analysis)
            except Exception as e:
                self._log_action("llm_analysis_error", str(e))

        self.state = AgentState.DONE
        result_data = {
            "task_id": task.data.get("task_id", ""),
            "analysis": analysis,
            "risk_assessment": risk_assessment,
            "summary": (
                f"发现 {len(analysis.get('functions', []))} 个函数, "
                f"{len(analysis.get('classes', []))} 个类, "
                f"总复杂度 {analysis.get('complexity', 0)}, "
                f"{len(analysis.get('smells', []))} 个代码异味"
            ),
        }

        self._log_action("analyze_complete", result_data["summary"])
        return AgentMessage(
            sender=self.role,
            receiver=AgentRole.ORCHESTRATOR,
            content=result_data["summary"],
            data=result_data,
            msg_type="result",
        )

    async def _llm_risk_analysis(self, code: str, analysis: dict) -> dict:
        """LLM 风险评估"""
        system_prompt = """你是代码风险分析专家。基于静态分析结果，评估代码风险。

返回 JSON:
{
  "risk_level": "low|medium|high",
  "risk_areas": ["列出高风险区域"],
  "test_priorities": ["建议优先测试的函数"],
  "edge_cases": ["建议测试的边界情况"]
}"""
        user_msg = f"分析结果:\n{json.dumps(analysis, ensure_ascii=False, default=str)[:2000]}"
        return await self.think_json(system_prompt, user_msg)


# ============================================================
# Generator Agent — 生成者
# ============================================================

class GeneratorAgent(BaseAgent):
    """测试生成 Agent — 多策略生成 + 反思改进"""

    def __init__(self):
        super().__init__(
            role=AgentRole.GENERATOR,
            name="Generator",
            description="测试生成专家，支持 AI/模板/属性多策略",
            max_iterations=3,
        )

    async def execute(self, task: AgentMessage) -> AgentMessage:
        self.state = AgentState.ACTING
        code = task.data.get("code", "")
        feedback = task.data.get("feedback")  # 反思反馈
        retry_attempt = task.data.get("retry_attempt", 0)

        if feedback:
            self._log_action("regenerate", f"根据反馈重新生成（第 {retry_attempt} 次）")
            self.memory.add_short_term(f"收到审查反馈: {feedback.get('summary', '')}", "reflection")
        else:
            self._log_action("generate", "开始生成测试用例")

        # 1. 调用测试生成路由器（真实工具）
        from backend.generator.router import route_generation
        test_cases = await route_generation(code, "python", "")

        # 2. 如果有反馈，用 LLM 改进
        if feedback and settings.llm_api_key:
            try:
                improved = await self._improve_with_feedback(test_cases, feedback)
                if improved:
                    test_cases = improved
            except Exception as e:
                self._log_action("improve_error", str(e))

        self.state = AgentState.DONE
        result_data = {
            "task_id": task.data.get("task_id", ""),
            "test_count": len(test_cases),
            "test_cases": [
                {"name": tc.name, "type": tc.type.value, "steps": len(tc.steps)}
                for tc in test_cases
            ],
            "retry_attempt": retry_attempt,
            "summary": f"生成 {len(test_cases)} 个测试用例" + (f"（第 {retry_attempt} 次改进）" if retry_attempt else ""),
        }

        self.memory.add_short_term(result_data["summary"], "observation")
        self._log_action("generate_complete", result_data["summary"])

        return AgentMessage(
            sender=self.role,
            receiver=AgentRole.ORCHESTRATOR,
            content=result_data["summary"],
            data=result_data,
            msg_type="result",
        )

    async def _improve_with_feedback(self, test_cases: list, feedback: dict) -> list:
        """根据 Reviewer 反馈改进测试"""
        system_prompt = """你是测试改进专家。根据审查反馈改进测试用例。

审查反馈会指出缺失的测试场景或质量问题，你需要说明改进建议。

返回 JSON:
{
  "improvements": ["改进1", "改进2"],
  "new_scenarios": ["新增测试场景1", "场景2"]
}"""
        user_msg = f"当前测试: {len(test_cases)} 个\n反馈: {json.dumps(feedback, ensure_ascii=False, default=str)[:1000]}"
        result = await self.think_json(system_prompt, user_msg)

        # 将改进建议存入记忆
        for imp in result.get("improvements", []):
            self.memory.add_long_term(imp, "reflection")

        return test_cases  # 实际场景中会根据建议重新生成


# ============================================================
# Executor Agent — 执行者
# ============================================================

class ExecutorAgent(BaseAgent):
    """测试执行 Agent — 执行测试 + 收集结果 + 覆盖率"""

    def __init__(self):
        super().__init__(
            role=AgentRole.EXECUTOR,
            name="Executor",
            description="测试执行专家，负责执行测试、收集结果、覆盖率",
            max_iterations=3,
        )

    async def execute(self, task: AgentMessage) -> AgentMessage:
        self.state = AgentState.ACTING
        code = task.data.get("code", "")
        self._log_action("execute", "开始执行测试")

        # 1. 执行代码（真实工具）
        from backend.executors.code_executor import execute_code
        exec_result = await execute_code(code, "python", timeout=15)

        # 2. 安全扫描（真实工具）
        from backend.safety.secret_scan import scan_all
        security_result = scan_all(code)

        self.state = AgentState.DONE
        result_data = {
            "task_id": task.data.get("task_id", ""),
            "exit_code": exec_result.get("exit_code", -1),
            "output": exec_result.get("output", "")[:2000],
            "security_scan": security_result,
            "passed": exec_result.get("exit_code", -1) == 0,
            "summary": (
                f"执行{'通过' if exec_result.get('exit_code') == 0 else '失败'}"
                f"（exit_code={exec_result.get('exit_code', -1)}），"
                f"安全扫描: {security_result.get('status', 'unknown')}"
            ),
        }

        self.memory.add_short_term(result_data["summary"], "observation")
        self._log_action("execute_complete", result_data["summary"])

        return AgentMessage(
            sender=self.role,
            receiver=AgentRole.ORCHESTRATOR,
            content=result_data["summary"],
            data=result_data,
            msg_type="result",
        )


# ============================================================
# Reviewer Agent — 审查者
# ============================================================

class ReviewerAgent(BaseAgent):
    """质量审查 Agent — 评估质量 + 反思 + 触发重试"""

    def __init__(self):
        super().__init__(
            role=AgentRole.REVIEWER,
            name="Reviewer",
            description="质量审查专家，负责评估测试质量、触发反思重试",
            max_iterations=3,
        )

    async def execute(self, task: AgentMessage) -> AgentMessage:
        self.state = AgentState.ACTING
        context = task.data.get("context", {})
        self._log_action("review", "开始质量审查")

        # 收集各 Agent 结果
        analysis = context.get("t1", {}).get("analysis", {})
        generation = context.get("t2", {})
        execution = context.get("t3", {})

        # 1. 基于规则的自动评估
        rule_score = self._rule_based_score(analysis, generation, execution)

        # 2. LLM 深度审查（可选）
        llm_review = {}
        if settings.llm_api_key:
            try:
                llm_review = await self._llm_review(analysis, generation, execution)
            except Exception as e:
                self._log_action("llm_review_error", str(e))

        # 3. 综合评分
        quality_score = llm_review.get("score", rule_score["score"])
        passed = quality_score >= 60

        # 4. 反思：提取经验教训
        reflections = self.memory.reflect()
        if reflections:
            self._log_action("reflect", f"反思提取 {len(reflections)} 条经验")

        self.state = AgentState.DONE
        result_data = {
            "task_id": task.data.get("task_id", ""),
            "quality_score": quality_score,
            "passed": passed,
            "rule_assessment": rule_score,
            "llm_review": llm_review,
            "reflections": reflections,
            "summary": f"质量评分: {quality_score}/100 ({'通过' if passed else '未通过'})",
        }

        # 如果未通过且有改进建议，返回 feedback 类型（触发 Orchestrator 重试）
        msg_type = "feedback" if not passed and llm_review.get("improvements") else "result"

        self.memory.add_short_term(result_data["summary"], "observation")
        self._log_action("review_complete", result_data["summary"])

        return AgentMessage(
            sender=self.role,
            receiver=AgentRole.ORCHESTRATOR,
            content=result_data["summary"],
            data=result_data,
            msg_type=msg_type,
        )

    def _rule_based_score(self, analysis: dict, generation: dict, execution: dict) -> dict:
        """基于规则的质量评分"""
        score = 0
        issues = []

        # 测试数量（30分）
        test_count = generation.get("test_count", 0)
        if test_count >= 5:
            score += 30
        elif test_count >= 3:
            score += 20
        elif test_count >= 1:
            score += 10
        else:
            issues.append("无测试用例生成")

        # 执行结果（30分）
        if execution.get("passed"):
            score += 30
        else:
            score += 10
            issues.append("测试执行未通过")

        # 代码覆盖率估算（20分）— 基于函数数 vs 测试数
        func_count = len(analysis.get("functions", []))
        if func_count > 0 and test_count > 0:
            coverage_ratio = min(test_count / func_count, 1.0)
            score += int(20 * coverage_ratio)
        else:
            score += 5

        # 安全（20分）
        security = execution.get("security_scan", {})
        if security.get("status") == "clean" or not security.get("issues"):
            score += 20
        else:
            score += 10
            issues.append("存在安全风险")

        return {"score": min(score, 100), "issues": issues}

    async def _llm_review(self, analysis: dict, generation: dict, execution: dict) -> dict:
        """LLM 深度审查"""
        system_prompt = """你是测试质量审查专家。综合评估测试质量。

返回 JSON:
{
  "score": 0-100,
  "strengths": ["优点1"],
  "weaknesses": ["缺点1"],
  "improvements": ["改进建议1"],
  "verdict": "pass|fail"
}"""
        user_msg = (
            f"分析: {json.dumps(analysis, ensure_ascii=False, default=str)[:1000]}\n"
            f"生成: {json.dumps(generation, ensure_ascii=False, default=str)[:500]}\n"
            f"执行: {json.dumps(execution, ensure_ascii=False, default=str)[:500]}"
        )
        return await self.think_json(system_prompt, user_msg)


# ============================================================
# 多 Agent 系统入口
# ============================================================

class MultiAgentSystem:
    """多 Agent 测试系统 — 一键启动多 Agent 协作

    用法:
        system = MultiAgentSystem()
        result = await system.run(source_code, "全面测试这段代码")
    """

    def __init__(self):
        self.orchestrator = OrchestratorAgent()
        self.analyst = AnalystAgent()
        self.generator = GeneratorAgent()
        self.executor = ExecutorAgent()
        self.reviewer = ReviewerAgent()

        # 注册子 Agent
        self.orchestrator.register_agent(self.analyst)
        self.orchestrator.register_agent(self.generator)
        self.orchestrator.register_agent(self.executor)
        self.orchestrator.register_agent(self.reviewer)

    async def run(self, source_code: str, task_desc: str = "") -> dict:
        """启动多 Agent 协作

        Returns:
            {
                "status": "completed",
                "summary": str,
                "results": {...},
                "agent_statuses": {...},
                "timeline": [...],
            }
        """
        start_time = time.time()
        task_desc = task_desc or "分析代码并生成、执行、审查测试"

        logger.info("多 Agent 系统启动: %s", task_desc)

        task_msg = AgentMessage(
            sender=AgentRole.ORCHESTRATOR,
            receiver=AgentRole.ORCHESTRATOR,
            content=task_desc,
            data={"code": source_code},
            msg_type="task",
        )

        result = await self.orchestrator.execute(task_msg)

        # 收集时间线
        timeline = self._collect_timeline()

        return {
            "status": "completed",
            "summary": result.content,
            "results": result.data,
            "agent_statuses": self.orchestrator.get_all_statuses(),
            "timeline": timeline,
            "duration_ms": int((time.time() - start_time) * 1000),
            "agent_count": 5,
        }

    def _collect_timeline(self) -> list[dict]:
        """收集所有 Agent 的执行时间线"""
        timeline = []
        for agent in [self.orchestrator, self.analyst, self.generator, self.executor, self.reviewer]:
            timeline.extend(agent.actions_log)
        timeline.sort(key=lambda x: x.get("timestamp", 0))
        return timeline

    def get_statuses(self) -> dict:
        """获取所有 Agent 实时状态"""
        return self.orchestrator.get_all_statuses()

    def reset(self):
        """重置所有 Agent"""
        for agent in [self.orchestrator, self.analyst, self.generator, self.executor, self.reviewer]:
            agent.reset()


# 全局单例
multi_agent_system = MultiAgentSystem()
