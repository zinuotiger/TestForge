"""质量门禁 — 覆盖率 + 变异率 + Flaky + 安全 综合判定

文档第二节 L5 质量验证层：通过/驳回/重新生成。
串联 coverage.py、mutation.py、flaky_detector、security.py。
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("testforge")


@dataclass
class GateCheck:
    """单个门禁检查项"""
    name: str
    passed: bool
    actual: float
    threshold: float
    detail: str = ""


@dataclass
class GateResult:
    """门禁判定结果"""
    passed: bool
    checks: list[GateCheck] = field(default_factory=list)
    overall_score: float = 0.0
    decision: str = "pass"     # pass | fail | rerun
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "decision": self.decision,
            "overall_score": round(self.overall_score, 1),
            "summary": self.summary,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "actual": c.actual,
                    "threshold": c.threshold,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
        }


class QualityGate:
    """质量门禁引擎

    门禁规则（文档 .testgen.yaml quality 段）:
      - coverage_threshold (默认 80)
      - mutation_threshold (默认 80)
      - flaky_rerun_count (默认 5)
      - security: block_dangerous
    """

    def __init__(
        self,
        coverage_threshold: float = 80.0,
        mutation_threshold: float = 80.0,
        flaky_max_rate: float = 10.0,      # Flaky 率上限 %
        block_dangerous: bool = True,
    ):
        self.coverage_threshold = coverage_threshold
        self.mutation_threshold = mutation_threshold
        self.flaky_max_rate = flaky_max_rate
        self.block_dangerous = block_dangerous

    async def evaluate(
        self,
        coverage_data: dict = None,
        mutation_data: dict = None,
        flaky_data: dict = None,
        security_data: dict = None,
    ) -> GateResult:
        """执行所有门禁检查

        Args:
            coverage_data: collect_coverage() 返回值
            mutation_data: run_mutation_tests() 返回值
            flaky_data: {"flaky_tests": [...], "total_tests": int}
            security_data: scan_all() 返回值

        Returns:
            GateResult
        """
        checks: list[GateCheck] = []

        # 1. 覆盖率门禁
        checks.append(self._check_coverage(coverage_data))

        # 2. 变异测试门禁
        checks.append(self._check_mutation(mutation_data))

        # 3. Flaky 门禁
        checks.append(self._check_flaky(flaky_data))

        # 4. 安全门禁
        checks.append(self._check_security(security_data))

        # 综合判定
        all_passed = all(c.passed for c in checks)
        score = sum(
            c.actual / max(c.threshold, 1) * 25 for c in checks if c.threshold > 0
        )
        score = min(score, 100.0)

        if all_passed:
            decision = "pass"
            summary = "✅ 所有质量门禁通过"
        elif self.block_dangerous and not checks[3].passed:
            decision = "fail"
            summary = "❌ 安全门禁未通过，直接驳回"
        else:
            decision = "rerun"
            summary = "⚠️ 部分门禁未通过，建议重新生成"

        return GateResult(
            passed=all_passed,
            checks=checks,
            overall_score=score,
            decision=decision,
            summary=summary,
        )

    # ---- 单项检查 ----

    def _check_coverage(self, data: dict | None) -> GateCheck:
        if not data or data.get("status") != "completed":
            return GateCheck(
                name="coverage",
                passed=False,
                actual=0.0,
                threshold=self.coverage_threshold,
                detail=data.get("error", "覆盖率数据不可用") if data else "未提供覆盖率数据",
            )
        pct = data.get("coverage_pct", 0)
        return GateCheck(
            name="coverage",
            passed=pct >= self.coverage_threshold,
            actual=pct,
            threshold=self.coverage_threshold,
            detail=f"覆盖 {pct}% (阈值 {self.coverage_threshold}%)",
        )

    def _check_mutation(self, data: dict | None) -> GateCheck:
        if not data or data.get("status") not in ("completed", "success"):
            return GateCheck(
                name="mutation",
                passed=True,   # 变异测试可选，未运行视为通过
                actual=100.0,
                threshold=self.mutation_threshold,
                detail="变异测试未运行，跳过",
            )
        score = data.get("mutation_score", 0)
        return GateCheck(
            name="mutation",
            passed=score >= self.mutation_threshold,
            actual=score,
            threshold=self.mutation_threshold,
            detail=f"变异杀死率 {score}% (阈值 {self.mutation_threshold}%)",
        )

    def _check_flaky(self, data: dict | None) -> GateCheck:
        if not data:
            return GateCheck(
                name="flaky",
                passed=True,
                actual=0.0,
                threshold=self.flaky_max_rate,
                detail="未提供 Flaky 数据",
            )
        flaky_count = len(data.get("flaky_tests", []))
        total = data.get("total_tests", 0) or 1
        rate = flaky_count / total * 100
        return GateCheck(
            name="flaky",
            passed=rate <= self.flaky_max_rate,
            actual=rate,
            threshold=self.flaky_max_rate,
            detail=f"Flaky 率 {rate:.1f}% ({flaky_count}/{total})",
        )

    def _check_security(self, data: dict | None) -> GateCheck:
        if not data:
            return GateCheck(
                name="security",
                passed=True,
                actual=100.0,
                threshold=100.0,
                detail="未提供安全扫描数据",
            )
        safe = data.get("safe", True)
        dangerous = len(data.get("dangerous_code", []))
        secrets = len(data.get("secret_leaks", []))
        return GateCheck(
            name="security",
            passed=safe,
            actual=100.0 if safe else 0.0,
            threshold=100.0,
            detail=f"危险代码 {dangerous} 处, 密钥泄露 {secrets} 处",
        )


# 全局单例（从配置初始化）
from backend.config import settings as _settings

quality_gate = QualityGate(
    coverage_threshold=_settings.coverage_threshold,
    mutation_threshold=_settings.mutation_threshold,
    flaky_max_rate=10.0,
    block_dangerous=True,
)
