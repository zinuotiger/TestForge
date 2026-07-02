"""Token 用量追踪器 — 记录每次 LLM 调用的 token 消耗与成本

文档第二十一节成本估算 + 横切面 C 自进化。
按 provider/model/场景 维度统计，支持月预算告警。
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("testforge")


# 各模型定价（美元/1K token），参考 2026 年公开定价
# 输入/输出 分别计价
MODEL_PRICING = {
    # 阿里云 DashScope
    "qwen-plus": {"input": 0.004, "output": 0.012, "currency": "CNY", "rate_to_usd": 0.14},
    "qwen-turbo": {"input": 0.002, "output": 0.006, "currency": "CNY", "rate_to_usd": 0.14},
    "qwen-max": {"input": 0.020, "output": 0.060, "currency": "CNY", "rate_to_usd": 0.14},
    "qwen3-32b": {"input": 0.002, "output": 0.006, "currency": "CNY", "rate_to_usd": 0.14},
    # DeepSeek
    "deepseek-chat": {"input": 0.001, "output": 0.002, "currency": "USD", "rate_to_usd": 1},
    "deepseek-coder": {"input": 0.001, "output": 0.002, "currency": "USD", "rate_to_usd": 1},
    # OpenAI
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006, "currency": "USD", "rate_to_usd": 1},
    "gpt-4o": {"input": 0.0025, "output": 0.01, "currency": "USD", "rate_to_usd": 1},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03, "currency": "USD", "rate_to_usd": 1},
    # Ollama 本地（免费）
    "qwen3-coder:7b": {"input": 0, "output": 0, "currency": "USD", "rate_to_usd": 1, "local": True},
    "codellama:7b": {"input": 0, "output": 0, "currency": "USD", "rate_to_usd": 1, "local": True},
    "llama3:8b": {"input": 0, "output": 0, "currency": "USD", "rate_to_usd": 1, "local": True},
}


@dataclass
class UsageRecord:
    """单次 LLM 调用用量记录"""
    timestamp: str
    provider: str               # dashscope | deepseek | openai | ollama
    model: str
    scene: str                  # code_gen | design | analyze | test
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error: str = ""


class TokenTracker:
    """Token 用量追踪器（内存统计，可选持久化到 SQLite）"""

    def __init__(self, monthly_budget_usd: float = 50.0):
        self._records: list[UsageRecord] = []
        self._monthly_budget = monthly_budget_usd
        self._max_records = 5000          # 内存上限，超出滚动丢弃

    def record(
        self,
        provider: str,
        model: str,
        scene: str = "code_gen",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        success: bool = True,
        error: str = "",
    ) -> UsageRecord:
        """记录一次 LLM 调用的 token 用量

        Args:
            provider: 提供商
            model: 模型名
            scene: 调用场景
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            latency_ms: 耗时
            success: 是否成功
            error: 错误信息

        Returns:
            UsageRecord
        """
        total = prompt_tokens + completion_tokens
        cost = self._calc_cost(model, prompt_tokens, completion_tokens)

        record = UsageRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            provider=provider,
            model=model,
            scene=scene,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
            success=success,
            error=error,
        )

        self._records.append(record)
        # 滚动丢弃旧记录
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

        # 预算告警
        monthly_cost = self._monthly_cost()
        if monthly_cost > self._monthly_budget * 0.8:
            logger.warning(
                "⚠️ LLM 月度成本 %.2f USD 已达预算 %.2f 的 %.0f%%",
                monthly_cost, self._monthly_budget,
                monthly_cost / self._monthly_budget * 100,
            )

        return record

    def _calc_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """计算单次调用成本（美元）"""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("qwen-plus"))
        input_cost = prompt_tokens / 1000 * pricing["input"]
        output_cost = completion_tokens / 1000 * pricing["output"]
        total_local = input_cost + output_cost
        return total_local * pricing.get("rate_to_usd", 1)

    # ---- 统计查询 ----

    def get_summary(self) -> dict:
        """获取总体统计摘要"""
        if not self._records:
            return self._empty_summary()

        total_prompt = sum(r.prompt_tokens for r in self._records)
        total_completion = sum(r.completion_tokens for r in self._records)
        total_tokens = total_prompt + total_completion
        total_cost = sum(r.cost_usd for r in self._records)
        success_count = sum(1 for r in self._records if r.success)
        avg_latency = sum(r.latency_ms for r in self._records) / len(self._records)

        monthly_cost = self._monthly_cost()
        budget_used_pct = round(monthly_cost / self._monthly_budget * 100, 1)

        return {
            "total_calls": len(self._records),
            "success_calls": success_count,
            "failed_calls": len(self._records) - success_count,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "monthly_cost_usd": round(monthly_cost, 4),
            "monthly_budget_usd": self._monthly_budget,
            "budget_used_pct": budget_used_pct,
            "budget_remaining_usd": round(max(0, self._monthly_budget - monthly_cost), 4),
            "avg_latency_ms": round(avg_latency, 0),
            "budget_alert": budget_used_pct >= 80,
        }

    def get_by_model(self) -> list[dict]:
        """按模型分组统计"""
        groups: dict[str, list[UsageRecord]] = {}
        for r in self._records:
            key = r.model
            groups.setdefault(key, []).append(r)

        result = []
        for model, records in groups.items():
            result.append({
                "model": model,
                "provider": records[0].provider,
                "calls": len(records),
                "prompt_tokens": sum(r.prompt_tokens for r in records),
                "completion_tokens": sum(r.completion_tokens for r in records),
                "total_tokens": sum(r.total_tokens for r in records),
                "cost_usd": round(sum(r.cost_usd for r in records), 4),
                "avg_latency_ms": round(sum(r.latency_ms for r in records) / len(records), 0),
                "is_local": MODEL_PRICING.get(model, {}).get("local", False),
            })
        result.sort(key=lambda x: -x["cost_usd"])
        return result

    def get_by_scene(self) -> list[dict]:
        """按调用场景分组统计"""
        groups: dict[str, list[UsageRecord]] = {}
        for r in self._records:
            groups.setdefault(r.scene, []).append(r)

        result = []
        for scene, records in groups.items():
            result.append({
                "scene": scene,
                "calls": len(records),
                "total_tokens": sum(r.total_tokens for r in records),
                "cost_usd": round(sum(r.cost_usd for r in records), 4),
            })
        result.sort(key=lambda x: -x["cost_usd"])
        return result

    def get_by_provider(self) -> list[dict]:
        """按提供商分组统计"""
        groups: dict[str, list[UsageRecord]] = {}
        for r in self._records:
            groups.setdefault(r.provider, []).append(r)

        result = []
        for provider, records in groups.items():
            result.append({
                "provider": provider,
                "calls": len(records),
                "total_tokens": sum(r.total_tokens for r in records),
                "cost_usd": round(sum(r.cost_usd for r in records), 4),
            })
        result.sort(key=lambda x: -x["cost_usd"])
        return result

    def get_daily_trend(self, days: int = 30) -> list[dict]:
        """按天聚合趋势"""
        daily: dict[str, dict] = {}
        for r in self._records:
            day = r.timestamp[:10]
            if day not in daily:
                daily[day] = {"date": day, "calls": 0, "tokens": 0, "cost": 0.0}
            daily[day]["calls"] += 1
            daily[day]["tokens"] += r.total_tokens
            daily[day]["cost"] += r.cost_usd

        trend = sorted(daily.values(), key=lambda x: x["date"])[-days:]
        for d in trend:
            d["cost"] = round(d["cost"], 4)
        return trend

    def get_recent_records(self, limit: int = 50) -> list[dict]:
        """获取最近调用记录"""
        return [asdict(r) for r in self._records[-limit:][::-1]]

    def get_model_pricing(self) -> dict:
        """获取模型定价表"""
        return MODEL_PRICING

    def set_budget(self, budget_usd: float):
        """设置月度预算"""
        self._monthly_budget = budget_usd
        logger.info("LLM 月度预算已更新: %.2f USD", budget_usd)

    def reset(self):
        """清空所有记录"""
        self._records.clear()
        logger.info("Token 用量记录已清空")

    # ---- 内部 ----

    def _monthly_cost(self) -> float:
        """计算本月成本"""
        now_month = datetime.now(timezone.utc).strftime("%Y-%m")
        return sum(
            r.cost_usd for r in self._records
            if r.timestamp.startswith(now_month)
        )

    def _empty_summary(self) -> dict:
        return {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0,
            "monthly_cost_usd": 0,
            "monthly_budget_usd": self._monthly_budget,
            "budget_used_pct": 0,
            "budget_remaining_usd": self._monthly_budget,
            "avg_latency_ms": 0,
            "budget_alert": False,
        }


# 全局单例
token_tracker = TokenTracker(monthly_budget_usd=50.0)
