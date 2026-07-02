"""多 Agent 协作框架 — 消息传递 + 记忆系统 + 角色专业化

架构:
  OrchestratorAgent (编排者)
    ├── AnalystAgent    (代码分析专家)
    ├── GeneratorAgent  (测试生成专家)
    ├── ExecutorAgent   (测试执行专家)
    └── ReviewerAgent   (质量审查专家)

核心概念:
  - AgentMessage: Agent 间结构化通信
  - AgentMemory: 短期（工作记忆）+ 长期（跨会话）
  - BaseAgent: 所有 Agent 的基类（LLM 调用 + 工具执行 + 反思）
  - AgentState: Agent 状态机（idle/thinking/acting/waiting/done/error）
  - AgentRole: 角色枚举

协作模式:
  1. 编排者分解任务 → 分配给专业 Agent
  2. Agent 间通过消息队列通信
  3. Reviewer 审查结果 → 不通过则反馈给 Generator 重试（反思自纠）
  4. 全程可观测（前端实时展示协作过程）
"""

import json
import time
import uuid
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from backend.config import settings

logger = logging.getLogger("testforge")


# ============ Agent 角色定义 ============

class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"    # 编排者：任务分解 + 协调
    ANALYST = "analyst"              # 分析师：代码结构分析
    GENERATOR = "generator"          # 生成者：测试用例生成
    EXECUTOR = "executor"            # 执行者：测试执行
    REVIEWER = "reviewer"            # 审查者：质量审查 + 反思


class AgentState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"            # LLM 推理中
    ACTING = "acting"                # 执行工具中
    WAITING = "waiting"              # 等待其他 Agent 响应
    DONE = "done"
    ERROR = "error"


# ============ Agent 间通信 ============

@dataclass
class AgentMessage:
    """Agent 间结构化消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender: AgentRole = AgentRole.ORCHESTRATOR
    receiver: AgentRole = AgentRole.ORCHESTRATOR  # "all" 表示广播
    content: str = ""                               # 消息内容
    data: dict = field(default_factory=dict)        # 结构化数据
    msg_type: str = "task"                           # task | result | feedback | query | broadcast
    timestamp: float = field(default_factory=time.time)
    parent_id: str = ""                              # 关联的消息 ID（用于响应链）

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender.value,
            "receiver": self.receiver.value if isinstance(self.receiver, AgentRole) else self.receiver,
            "content": self.content,
            "data": self.data,
            "msg_type": self.msg_type,
            "timestamp": self.timestamp,
            "parent_id": self.parent_id,
        }


# ============ Agent 记忆系统 ============

@dataclass
class MemoryItem:
    """单条记忆"""
    content: str
    memory_type: str = "observation"    # observation | reflection | plan | fact
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class AgentMemory:
    """Agent 记忆系统

    短期记忆: 当前任务的工作记忆（有限容量，FIFO）
    长期记忆: 跨任务的知识积累（如已分析的代码模式、常见 bug）
    """

    def __init__(self, short_term_capacity: int = 20):
        self._short_term: list[MemoryItem] = []
        self._long_term: list[MemoryItem] = []
        self._capacity = short_term_capacity

    def add_short_term(self, content: str, memory_type: str = "observation", **metadata):
        """添加短期记忆"""
        item = MemoryItem(content=content, memory_type=memory_type, metadata=metadata)
        self._short_term.append(item)
        if len(self._short_term) > self._capacity:
            self._short_term.pop(0)  # FIFO 淘汰

    def add_long_term(self, content: str, memory_type: str = "fact", **metadata):
        """添加长期记忆"""
        self._long_term.append(MemoryItem(content=content, memory_type=memory_type, metadata=metadata))

    def get_short_term_context(self, max_items: int = 10) -> str:
        """获取短期记忆上下文（用于 LLM prompt）"""
        items = self._short_term[-max_items:]
        return "\n".join(f"[{item.memory_type}] {item.content}" for item in items)

    def get_long_term_context(self, max_items: int = 5) -> str:
        """获取长期记忆上下文"""
        items = self._long_term[-max_items:]
        return "\n".join(f"[{item.memory_type}] {item.content}" for item in items)

    def reflect(self) -> list[str]:
        """从短期记忆中提取反思（简化版：提取关键观察）"""
        reflections = []
        for item in self._short_term:
            if item.memory_type == "observation" and ("失败" in item.content or "错误" in item.content):
                reflections.append(f"从失败中学习: {item.content}")
        # 将反思存入长期记忆
        for r in reflections:
            self.add_long_term(r, "reflection")
        return reflections

    def clear_short_term(self):
        self._short_term.clear()

    @property
    def stats(self) -> dict:
        return {
            "short_term_count": len(self._short_term),
            "long_term_count": len(self._long_term),
        }


# ============ Agent 基类 ============

class BaseAgent(ABC):
    """Agent 基类 — 所有专业 Agent 继承此类

    核心能力:
      1. LLM 推理（支持 Function Calling）
      2. 工具执行
      3. 记忆管理
      4. 消息收发
      5. 反思与自纠
    """

    def __init__(
        self,
        role: AgentRole,
        name: str,
        description: str = "",
        max_iterations: int = 5,
        tools: list[dict] = None,
    ):
        self.role = role
        self.name = name
        self.description = description
        self.max_iterations = max_iterations
        self.tools = tools or []
        self.state = AgentState.IDLE
        self.memory = AgentMemory()
        self.messages_received: list[AgentMessage] = []
        self.messages_sent: list[AgentMessage] = []
        self.actions_log: list[dict] = []        # 执行日志（供前端展示）
        self._on_message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """设置消息回调（供 Orchestrator 接收）"""
        self._on_message_callback = callback

    async def send_message(self, receiver: AgentRole, content: str, data: dict = None, msg_type: str = "result") -> AgentMessage:
        """向其他 Agent 发送消息"""
        msg = AgentMessage(
            sender=self.role,
            receiver=receiver,
            content=content,
            data=data or {},
            msg_type=msg_type,
        )
        self.messages_sent.append(msg)
        self._log_action("send_message", f"→ {receiver.value}: {content[:100]}")
        if self._on_message_callback:
            await self._on_message_callback(msg)
        return msg

    async def receive_message(self, msg: AgentMessage):
        """接收消息"""
        self.messages_received.append(msg)
        self.memory.add_short_term(
            f"收到来自 {msg.sender.value} 的消息: {msg.content}",
            "observation",
        )
        self._log_action("receive_message", f"← {msg.sender.value}: {msg.content[:100]}")

    def _log_action(self, action: str, detail: str):
        """记录执行日志"""
        log_entry = {
            "agent": self.name,
            "role": self.role.value,
            "action": action,
            "detail": detail,
            "state": self.state.value,
            "timestamp": time.time(),
        }
        self.actions_log.append(log_entry)
        logger.info("[Agent:%s] %s: %s", self.role.value, action, detail)

    async def think(self, system_prompt: str, user_message: str) -> dict:
        """LLM 推理（ReAct: Thought）"""
        self.state = AgentState.THINKING
        self._log_action("think", "LLM 推理中...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # 注入记忆上下文
        short_term = self.memory.get_short_term_context()
        if short_term:
            messages.insert(1, {"role": "system", "content": f"工作记忆:\n{short_term}"})

        try:
            import litellm
            kwargs = {
                "model": f"{settings.llm_provider}/{settings.llm_model}",
                "messages": messages,
                "api_key": settings.llm_api_key,
                "api_base": settings.llm_api_base,
                "temperature": 0.2,
            }
            if self.tools:
                kwargs["tools"] = self.tools
                kwargs["tool_choice"] = "auto"

            response = await litellm.acompletion(**kwargs)
            result = response.choices[0].message.model_dump()

            self.memory.add_short_term(f"思考: {result.get('content', '')[:200]}", "observation")
            return result
        except Exception as e:
            self.state = AgentState.ERROR
            self._log_action("think_error", str(e))
            raise

    async def think_json(self, system_prompt: str, user_message: str) -> dict:
        """LLM 推理并返回 JSON（用于结构化输出）"""
        self.state = AgentState.THINKING
        self._log_action("think_json", "LLM 推理中（JSON 模式）...")

        messages = [
            {"role": "system", "content": system_prompt + "\n\n你必须返回有效的 JSON，不要包含 markdown 代码块标记。"},
            {"role": "user", "content": user_message},
        ]

        short_term = self.memory.get_short_term_context()
        if short_term:
            messages.insert(1, {"role": "system", "content": f"工作记忆:\n{short_term}"})

        try:
            import litellm
            response = await litellm.acompletion(
                model=f"{settings.llm_provider}/{settings.llm_model}",
                messages=messages,
                api_key=settings.llm_api_key,
                api_base=settings.llm_api_base,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            # 清理可能的 markdown 标记
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)
            self.memory.add_short_term(f"思考(JSON): {json.dumps(result, ensure_ascii=False)[:200]}", "observation")
            return result
        except json.JSONDecodeError as e:
            self.state = AgentState.ERROR
            self._log_action("think_json_error", f"JSON 解析失败: {e}")
            # 降级：返回空结果
            return {}
        except Exception as e:
            self.state = AgentState.ERROR
            self._log_action("think_json_error", str(e))
            raise

    @abstractmethod
    async def execute(self, task: AgentMessage) -> AgentMessage:
        """执行任务（子类必须实现）

        Args:
            task: 来自 Orchestrator 的任务消息

        Returns:
            执行结果消息
        """
        ...

    def get_status(self) -> dict:
        """获取 Agent 状态（供前端展示）"""
        return {
            "name": self.name,
            "role": self.role.value,
            "description": self.description,
            "state": self.state.value,
            "memory": self.memory.stats,
            "messages_received": len(self.messages_received),
            "messages_sent": len(self.messages_sent),
            "actions_count": len(self.actions_log),
            "recent_actions": self.actions_log[-5:],
        }

    def reset(self):
        """重置 Agent 状态"""
        self.state = AgentState.IDLE
        self.memory.clear_short_term()
        self.messages_received.clear()
        self.messages_sent.clear()
        self.actions_log.clear()
