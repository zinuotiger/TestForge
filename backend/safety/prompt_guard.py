"""Prompt 注入防护 — LLM 输入/输出安全过滤

文档第二节横切面 A 安全：Prompt注入防护。
防止用户输入绕过系统提示、泄露系统信息、执行越权操作。
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("testforge")


@dataclass
class GuardResult:
    """防护检测结果"""
    safe: bool
    risk_level: str        # safe | low | medium | high | critical
    blocked_patterns: list[str] = None
    sanitized_input: str = ""
    reason: str = ""


# 已知的 Prompt 注入模式
INJECTION_PATTERNS = [
    # 直接指令覆盖
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions", "指令覆盖"),
    (r"(?i)disregard\s+(all\s+)?(previous|prior)\s+", "指令覆盖"),
    (r"(?i)forget\s+(everything|all\s+previous)", "指令覆盖"),
    (r"(?i)your\s+(new\s+)?instructions?\s+(is|are)", "指令覆盖"),
    (r"(?i)system\s*[:：]\s*", "系统提示伪造"),
    (r"(?i)<\|im_start\|>", "特殊标记注入"),
    (r"(?i)<\|system\|>", "特殊标记注入"),
    # 角色扮演绕过
    (r"(?i)pretend\s+(you\s+are|to\s+be)\s+(a|an)\s+", "角色扮演绕过"),
    (r"(?i)act\s+as\s+(if\s+you\s+(were|are)\s+)?(a|an)\s+", "角色扮演绕过"),
    (r"(?i)you\s+are\s+(now\s+)?(DAN|developer\s+mode|jailbreak)", "越狱模式"),
    # 信息泄露
    (r"(?i)(show|reveal|print|output)\s+(me\s+)?(your\s+)?(system\s+)?prompt", "提示泄露"),
    (r"(?i)(what|how)\s+(is|are)\s+your\s+(instructions?|rules?|guidelines?)", "提示泄露"),
    (r"(?i)repeat\s+(everything|all\s+your\s+instructions)", "提示泄露"),
    # 越权操作
    (r"(?i)(execute|run|eval)\s+(shell|bash|command|python)", "越权执行"),
    (r"(?i)access\s+(the\s+)?(file\s*system|database|secrets?)", "越权访问"),
    (r"(?i)(delete|remove|drop)\s+(all|every)\s+(file|table|record)", "越权破坏"),
    # 编码绕过
    (r"(?i)base64\s*[:：]\s*[A-Za-z0-9+/=]{20,}", "Base64 编码绕过"),
    (r"\\x[0-9a-fA-F]{2}\\x[0-9a-fA-F]{2}", "十六进制编码绕过"),
]

# 输出过滤模式（防止 LLM 泄露系统信息）
OUTPUT_BLOCK_PATTERNS = [
    r"(?i)as\s+an?\s+ai\s+(language\s+)?model.*i\s+(cannot|can'?t|won'?t)",
    r"(?i)my\s+(system\s+)?prompt\s+(is|was|says)",
    r"(?i)<\|im_start\|>",
    r"(?i)<\|system\|>",
]


class PromptGuard:
    """Prompt 注入防护引擎"""

    def __init__(self, max_input_length: int = 32000):
        self.max_input_length = max_input_length

    def check_input(self, user_input: str) -> GuardResult:
        """检测用户输入是否含注入

        Args:
            user_input: 用户输入文本

        Returns:
            GuardResult
        """
        if not user_input:
            return GuardResult(True, "safe", [], "", "空输入")

        # 长度限制
        if len(user_input) > self.max_input_length:
            return GuardResult(
                False, "high", ["input_too_long"],
                user_input[:self.max_input_length],
                f"输入过长 ({len(user_input)} > {self.max_input_length})",
            )

        blocked = []
        reasons = []
        for pattern, desc in INJECTION_PATTERNS:
            if re.search(pattern, user_input):
                blocked.append(desc)
                reasons.append(f"匹配模式: {desc}")

        if not blocked:
            return GuardResult(True, "safe", [], user_input, "输入安全")

        # 风险等级判定
        risk = self._assess_risk(blocked)
        sanitized = self._sanitize(user_input, blocked)

        return GuardResult(
            safe=risk not in ("high", "critical"),
            risk_level=risk,
            blocked_patterns=blocked,
            sanitized_input=sanitized,
            reason="; ".join(reasons),
        )

    def check_output(self, llm_output: str) -> GuardResult:
        """检测 LLM 输出是否泄露系统信息"""
        if not llm_output:
            return GuardResult(True, "safe", [], "", "空输出")

        blocked = []
        for pattern in OUTPUT_BLOCK_PATTERNS:
            if re.search(pattern, llm_output):
                blocked.append("输出泄露模式")

        if not blocked:
            return GuardResult(True, "safe", [], llm_output, "输出安全")

        sanitized = self._sanitize_output(llm_output)
        return GuardResult(
            safe=False,
            risk_level="medium",
            blocked_patterns=blocked,
            sanitized_input=sanitized,
            reason="LLM 输出含敏感模式，已过滤",
        )

    def sanitize(self, user_input: str) -> str:
        """便捷方法：直接返回净化后的输入"""
        result = self.check_input(user_input)
        return result.sanitized_input if result.safe else user_input

    # ---- 内部 ----

    def _assess_risk(self, blocked: list[str]) -> str:
        """根据命中的模式数量和类型评估风险"""
        critical_patterns = {"越狱模式", "越权执行", "越权破坏", "越权访问"}
        # 指令覆盖和提示泄露属于高危注入意图
        high_patterns = {"指令覆盖", "提示泄露", "系统提示伪造", "特殊标记注入"}
        if any(p in critical_patterns for p in blocked):
            return "critical"
        if any(p in high_patterns for p in blocked):
            return "high"
        if len(blocked) >= 3:
            return "high"
        if len(blocked) >= 2:
            return "medium"
        return "low"

    def _sanitize(self, text: str, blocked: list[str]) -> str:
        """净化输入：移除/替换注入模式"""
        sanitized = text
        for pattern, _ in INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
        return sanitized

    def _sanitize_output(self, text: str) -> str:
        """净化输出"""
        sanitized = text
        for pattern in OUTPUT_BLOCK_PATTERNS:
            sanitized = re.sub(pattern, "[已过滤]", sanitized, flags=re.IGNORECASE)
        return sanitized


# 全局单例
prompt_guard = PromptGuard()
