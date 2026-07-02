"""测试债务量化 —— 健康度评分"""


class HealthScorer:
    """测试债务量化 + 健康度评分"""

    def score(self, test_stats: dict) -> dict:
        """
        输入: {
            total_tests, skipped, todo_count,
            coverage_pct, mutation_score, flaky_count
        }
        """
        total = max(test_stats.get("total_tests", 1), 1)

        # 1. 覆盖率质量 (40%)
        coverage = test_stats.get("coverage_pct", 0)
        mutation = test_stats.get("mutation_score", 0)
        quality_score = (coverage * 0.6 + mutation * 0.4) / 100
        quality_weight = 0.40

        # 2. Flaky 率 (30%)
        flaky = test_stats.get("flaky_count", 0)
        flaky_rate = flaky / total
        flaky_score = max(0, 1 - flaky_rate / 0.05)  # 5% 为阈值
        flaky_weight = 0.30

        # 3. 维护成本 (30%)
        skipped = test_stats.get("skipped", 0)
        todo = test_stats.get("todo_count", 0)
        maint_rate = (skipped + todo) / total
        maint_score = max(0, 1 - maint_rate / 0.10)  # 10% 为阈值
        maint_weight = 0.30

        # 综合健康度
        health = round(
            (quality_score * quality_weight +
             flaky_score * flaky_weight +
             maint_score * maint_weight) * 100
        )

        # 还债建议
        suggestions = []
        if coverage < 80:
            suggestions.append({
                "priority": "P0" if coverage < 60 else "P1",
                "action": "提升覆盖率",
                "detail": f"当前 {coverage}%，目标 ≥80%",
            })
        if test_stats.get("mutation_score", 0) < 80:
            suggestions.append({
                "priority": "P1",
                "action": "提高变异杀死率",
                "detail": f"当前 {test_stats.get('mutation_score', 0)}%，目标 ≥80%",
            })
        if flaky > 0:
            suggestions.append({
                "priority": "P0" if flaky > 0 else "P2",
                "action": "修复 Flaky 测试",
                "detail": f"发现 {flaky} 个 Flaky 测试",
            })
        if skipped + todo > total * 0.1:
            suggestions.append({
                "priority": "P1",
                "action": "清理跳过/TODO测试",
                "detail": f"跳过 {skipped} + TODO {todo}，占比 {(skipped+todo)/total*100:.0f}%",
            })

        return {
            "health_score": health,
            "grade": self._grade(health),
            "breakdown": {
                "coverage_quality": round(quality_score * 100),
                "flaky_health": round(flaky_score * 100),
                "maintainability": round(maint_score * 100),
            },
            "suggestions": sorted(suggestions, key=lambda s: s["priority"]),
            "debt_indicators": {
                "skipped_tests": skipped,
                "todo_tests": todo,
                "flaky_tests": flaky,
                "coverage_trend": "stable",
            },
        }

    @staticmethod
    def _grade(score: int) -> str:
        if score >= 90: return "A"
        if score >= 75: return "B"
        if score >= 60: return "C"
        return "D"


# 全局单例
health_scorer = HealthScorer()
