"""五策略路由器 — 按进化闭环推荐权重动态排序策略"""

import asyncio
import logging
from backend.models import TestCase
from backend.generator.template_engine import match_template
from backend.generator.property_generator import generate_property_tests
from backend.generator.ai_generator import generate_tests as ai_generate
from backend.generator.search_generator import SearchGenerator
from backend.generator.traffic_generator import TrafficGenerator

from backend.core.self_evolution import evolution_loop

logger = logging.getLogger("testforge")


def _get_dynamic_strategy_order():
    """从进化闭环读取策略权重，动态排序策略。

    返回值按进化权重降序排列，权重越高越优先执行。
    如果进化引擎无数据，回退到默认固定顺序。
    """
    try:
        strategies = evolution_loop.get_recommended_strategies()
        if not strategies:
            raise ValueError("No strategy data yet")

        ordered = []
        for s in strategies:
            name = s["name"]
            handler = STRATEGY_HANDLERS.get(name)
            if handler:
                ordered.append((name, handler))
        if ordered:
            return ordered
    except Exception as e:
        logger.debug("Reading evolution weights failed, using default order: %s", e)

    # Fallback: fixed default order
    return DEFAULT_ORDER


# Strategy handlers keyed by strategy name
STRATEGY_HANDLERS = {
    "template": lambda code, lang, fn: match_template(code, fn),
    "property": lambda code, lang, fn: generate_property_tests(code, lang),
    "ai": lambda code, lang, fn: ai_generate(code, lang, fn),
    "search": lambda code, lang, fn: SearchGenerator().generate(code, lang, fn),
    "traffic": lambda code, lang, fn: TrafficGenerator().generate(code, lang, fn),
}

# Default fallback order (template -> property -> AI -> search -> traffic)
DEFAULT_ORDER = [
    ("template", STRATEGY_HANDLERS["template"]),
    ("property", STRATEGY_HANDLERS["property"]),
    ("ai", STRATEGY_HANDLERS["ai"]),
    ("search", STRATEGY_HANDLERS["search"]),
    ("traffic", STRATEGY_HANDLERS["traffic"]),
]


async def route_generation(
    source_code: str,
    language: str = "python",
    function_name: str = "",
) -> list[TestCase]:
    """智能路由: 按进化闭环推荐权重动态排序策略"""

    results: list[TestCase] = []
    strategy_order = _get_dynamic_strategy_order()

    for strategy_name, handler in strategy_order:
        try:
            result = handler(source_code, language, function_name)
            if asyncio.iscoroutine(result):
                cases = await result
            else:
                cases = result
            if cases:
                results.extend(cases)
                record_strategy(strategy_name, len(cases))
                asyncio.ensure_future(
                    evolution_loop.on_strategy_called(strategy_name, len(cases))
                )
        except Exception as e:
            logger.warning("策略 %s 生成失败: %s", strategy_name, e)

    # 去重
    seen = set()
    unique = []
    for c in results:
        if c.name not in seen:
            seen.add(c.name)
            unique.append(c)

    return unique


# 策略统计 (用于自进化闭环)
strategy_stats = {
    "template": {"calls": 0, "cases": 0},
    "property": {"calls": 0, "cases": 0},
    "ai": {"calls": 0, "cases": 0},
    "search": {"calls": 0, "cases": 0},
    "traffic": {"calls": 0, "cases": 0},
}


def record_strategy(strategy: str, case_count: int):
    if strategy in strategy_stats:
        strategy_stats[strategy]["calls"] += 1
        strategy_stats[strategy]["cases"] += case_count
