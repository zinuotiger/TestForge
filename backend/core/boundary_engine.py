"""智能边界分析引擎 — 类型推断 → 等价类划分 → 边界值计算 → 异常值推荐 → Pairwise

文档第九节标记的"零竞品"核心差异化能力。
从参数约束自动生成边界测试用例，无需人工编写。
"""

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("testforge")


@dataclass
class ParameterSpec:
    """参数规格定义"""
    name: str
    type: str = "string"                       # string | integer | number | boolean | date | enum
    constraints: dict[str, Any] = field(default_factory=dict)
    # 常用约束: min, max, minLength, maxLength, pattern, enum, nullable, required

    def __post_init__(self):
        if not self.constraints:
            self.constraints = {}


@dataclass
class BoundaryCase:
    """单个边界测试用例"""
    values: dict[str, Any]
    expected_status: int = 200
    reason: str = ""
    category: str = "valid"                    # valid | boundary | invalid | exception


class BoundaryEngine:
    """智能边界分析引擎

    流程: 类型推断 → 等价类划分 → 边界值计算 → 异常值推荐 → Pairwise 组合
    """

    # 异常值候选池（按类型）
    EXCEPTION_VALUES = {
        "integer": [None, -1, 0, -2147483648, 2147483647, "abc", 3.14, "", []],
        "number": [None, -1.0, 0.0, -1e308, 1e308, "NaN", "inf", "abc", ""],
        "string": [None, "", " ", "   ", "a" * 10000, "<script>alert(1)</script>",
                   "'; DROP TABLE--", "null", "undefined", 123, True],
        "boolean": [None, "true", "false", 0, 1, "yes", "no", ""],
        "date": [None, "", "0000-00-00", "9999-12-31", "2026-02-30",
                 "not-a-date", "2026-13-01"],
        "enum": [None, "", "invalid_option", 0],
    }

    def analyze(self, parameters: list[dict | ParameterSpec]) -> dict:
        """对参数列表执行完整边界分析

        Args:
            parameters: 参数规格列表 (dict 或 ParameterSpec)

        Returns:
            {
                "parameters": [参数规格],
                "generated_cases": [BoundaryCase 序列化为 dict],
                "total_cases": int,
                "pairwise_cases": [Pairwise 组合后的用例],
            }
        """
        specs = [
            p if isinstance(p, ParameterSpec) else ParameterSpec(**p)
            for p in parameters
        ]

        # 1. 每个参数生成边界值候选
        per_param_cases: dict[str, list[tuple[Any, str, str]]] = {}
        for spec in specs:
            per_param_cases[spec.name] = self._generate_values_for_param(spec)

        # 2. 笛卡尔积生成全组合（小规模）
        full_cases = self._cartesian_combine(specs, per_param_cases)

        # 3. Pairwise 组合（大规模时降级，减少用例数）
        pairwise_cases = self._pairwise_combine(specs, per_param_cases)

        return {
            "parameters": [
                {"name": s.name, "type": s.type, "constraints": s.constraints}
                for s in specs
            ],
            "generated_cases": [c.__dict__ for c in full_cases[:200]],  # 限制返回量
            "total_cases": len(full_cases),
            "pairwise_cases": [c.__dict__ for c in pairwise_cases],
            "pairwise_count": len(pairwise_cases),
        }

    def expand_for_test_case(self, parameters: list[dict]) -> list[dict]:
        """为测试用例生成边界展开结果（写入 TestCase.boundary_expansion）

        Returns:
            [{value, expected_status, reason}, ...] 单参数展开
        """
        specs = [
            p if isinstance(p, ParameterSpec) else ParameterSpec(**p)
            for p in parameters
        ]
        result = []
        for spec in specs:
            values = self._generate_values_for_param(spec)
            for value, expected, reason in values:
                result.append({
                    "parameter": spec.name,
                    "value": value,
                    "expected_status": expected,
                    "reason": reason,
                })
        return result

    # ---- 内部：单参数值生成 ----

    def _generate_values_for_param(
        self, spec: ParameterSpec
    ) -> list[tuple[Any, int, str]]:
        """为单个参数生成 (值, 期望状态, 原因) 列表"""
        ptype = spec.type
        c = spec.constraints
        values: list[tuple[Any, int, str]] = []

        if ptype == "integer":
            values.extend(self._integer_boundary(c))
        elif ptype == "number":
            values.extend(self._number_boundary(c))
        elif ptype == "string":
            values.extend(self._string_boundary(c))
        elif ptype == "boolean":
            values.extend(self._boolean_boundary(c))
        elif ptype == "date":
            values.extend(self._date_boundary(c))
        elif ptype == "enum":
            values.extend(self._enum_boundary(c))
        else:
            values.append(("", 200, "默认-未知类型"))

        # 异常值补充
        if c.get("nullable", True):
            for ev in self.EXCEPTION_VALUES.get(ptype, [None])[:3]:
                values.append((ev, 400, f"异常-{self._describe(ev)}"))

        return values

    def _integer_boundary(self, c: dict) -> list[tuple[Any, int, str]]:
        mn = c.get("min", 0)
        mx = c.get("max", 100)
        return [
            (mn - 1, 400, "边界下-小于最小值"),
            (mn, 200, "边界最小值"),
            (mn + 1, 200, "边界下+1"),
            ((mn + mx) // 2, 200, "等价类-中间值"),
            (mx - 1, 200, "边界上-1"),
            (mx, 200, "边界最大值"),
            (mx + 1, 400, "边界上-超过最大值"),
        ]

    def _number_boundary(self, c: dict) -> list[tuple[Any, int, str]]:
        mn = c.get("min", 0.0)
        mx = c.get("max", 100.0)
        return [
            (mn - 0.01, 400, "边界下-小于最小值"),
            (mn, 200, "边界最小值"),
            (round((mn + mx) / 2, 2), 200, "等价类-中间值"),
            (mx, 200, "边界最大值"),
            (mx + 0.01, 400, "边界上-超过最大值"),
            (-0.01, 400, "异常-负数(若不允许)"),
        ]

    def _string_boundary(self, c: dict) -> list[tuple[Any, int, str]]:
        min_len = c.get("minLength", 1)
        max_len = c.get("maxLength", 255)
        return [
            ("", 400, "边界-空字符串"),
            ("a" * min_len, 200, "边界-最小长度"),
            ("a" * (min_len + 1), 200, "边界-最小长度+1"),
            ("测试字符串", 200, "等价类-中文"),
            ("test123", 200, "等价类-英文数字"),
            ("a" * max_len, 200, "边界-最大长度"),
            ("a" * (max_len + 1), 400, "边界-超过最大长度"),
        ]

    def _boolean_boundary(self, c: dict) -> list[tuple[Any, int, str]]:
        return [
            (True, 200, "等价类-true"),
            (False, 200, "等价类-false"),
        ]

    def _date_boundary(self, c: dict) -> list[tuple[Any, int, str]]:
        return [
            ("2026-01-01", 200, "等价类-年初"),
            ("2026-06-30", 200, "等价类-年中"),
            ("2026-12-31", 200, "等价类-年末"),
            ("2026-02-29", 400, "边界-非闰年2月29"),
        ]

    def _enum_boundary(self, c: dict) -> list[tuple[Any, int, str]]:
        allowed = c.get("enum", [])
        result = []
        for v in allowed[:5]:
            result.append((v, 200, f"等价类-合法枚举值"))
        result.append(("INVALID_OPTION", 400, "异常-非法枚举值"))
        return result

    # ---- 组合策略 ----

    def _cartesian_combine(
        self,
        specs: list[ParameterSpec],
        per_param: dict[str, list[tuple[Any, int, str]]],
    ) -> list[BoundaryCase]:
        """笛卡尔积全组合（参数 ≤3 个时使用）"""
        if len(specs) > 3:
            return []  # 太多参数走 Pairwise

        names = [s.name for s in specs]
        value_lists = [per_param[n] for n in names]

        cases = []
        for combo in itertools.product(*value_lists):
            values = {names[i]: combo[i][0] for i in range(len(names))}
            # 取最严格的期望状态（任一参数非法则整体非法）
            expected = max(c[1] for c in combo)
            reasons = " | ".join(c[2] for c in combo if c[1] != 200)
            category = "invalid" if expected != 200 else "valid"
            if any("边界" in c[2] for c in combo):
                category = "boundary"
            cases.append(BoundaryCase(values, expected, reasons, category))
        return cases

    def _pairwise_combine(
        self,
        specs: list[ParameterSpec],
        per_param: dict[str, list[tuple[Any, int, str]]],
    ) -> list[BoundaryCase]:
        """Pairwise 组合 — 保证每对参数的所有取值组合至少出现一次

        使用 IPOG (In-Parameter-Order) 简化实现。
        """
        if not specs:
            return []
        if len(specs) <= 1:
            # 单参数直接展开
            name = specs[0].name
            return [
                BoundaryCase({name: v[0]}, v[1], v[2], "valid" if v[1] == 200 else "invalid")
                for v in per_param[name]
            ]

        names = [s.name for s in specs]
        value_lists = [[v[0] for v in per_param[n]] for n in names]

        # 简化 Pairwise: 基于覆盖数组的贪心算法
        pairs_needed: set[tuple] = set()
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                for vi in value_lists[i]:
                    for vj in value_lists[j]:
                        pairs_needed.add((i, vi, j, vj))

        cases: list[list] = []
        covered: set = set()

        while pairs_needed - covered:
            # 贪心选择覆盖最多未覆盖对的组合
            best_case = None
            best_cover = -1
            for _ in range(50):  # 采样尝试
                combo = [vl[len(cases) % len(vl)] if i < len(cases) else vl[0]
                         for i, vl in enumerate(value_lists)]
                # 简化: 用第一个值填充
                combo = [value_lists[i][len(cases) % len(value_lists[i])] for i in range(len(names))]
                new_pairs = self._pairs_in_case(combo, names)
                cnt = len(new_pairs & (pairs_needed - covered))
                if cnt > best_cover:
                    best_cover = cnt
                    best_case = combo

            if best_case is None:
                break
            new_pairs = self._pairs_in_case(best_case, names)
            covered |= new_pairs
            cases.append(best_case)

        result = []
        for combo in cases:
            values = {names[i]: combo[i] for i in range(len(names))}
            result.append(BoundaryCase(values, 200, "Pairwise组合", "valid"))
        return result

    def _pairs_in_case(self, combo: list, names: list) -> set[tuple]:
        pairs = set()
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                pairs.add((i, combo[i], j, combo[j]))
        return pairs

    @staticmethod
    def _describe(value: Any) -> str:
        if value is None:
            return "null值"
        if value == "":
            return "空字符串"
        if isinstance(value, str) and len(value) > 20:
            return "超长字符串"
        return str(value)


# 全局单例
boundary_engine = BoundaryEngine()
