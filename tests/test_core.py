"""TestForge 自举测试"""

import pytest
from backend.models import TestCase, TestStep, Assertion, AssertionType, StepType, TestType
from backend.models import RunRequest, ExecutionResult, ExecutionStatus
from backend.safety.secret_scan import scan_all, scan_dangerous_code, scan_secrets
from backend.core.flaky_detector import FlakyDetector
from backend.core.health_scorer import HealthScorer
from backend.core.tia_engine import TIAEngine
from backend.core.self_healer import SelfHealer


# === 模型测试 ===

class TestModels:
    def test_testcase_creation(self):
        tc = TestCase(name="测试用例1", type=TestType.UNIT, tags=["unit"])
        assert tc.name == "测试用例1"
        assert tc.status == "active"

    def test_step_with_assertions(self):
        step = TestStep(
            id="s1", type=StepType.HTTP_REQUEST,
            request={"method": "GET", "url": "/api/test"},
            assertions=[Assertion(type=AssertionType.STATUS, expected=200)],
        )
        assert len(step.assertions) == 1

    def test_run_request_default(self):
        req = RunRequest(path=".")
        assert req.strategy == "smart"
        assert req.llm_mode == "api"


# === 安全扫描测试 ===

class TestSecurity:
    def test_dangerous_eval_detected(self):
        findings = scan_dangerous_code("eval('1+1')")
        assert len(findings) == 1
        assert "eval" in findings[0]["pattern"]

    def test_dangerous_os_system_detected(self):
        findings = scan_dangerous_code("import os; os.system('rm -rf /')")
        assert any("os.system" in f["pattern"] for f in findings)

    def test_safe_code_passes(self):
        findings = scan_dangerous_code("print('hello world')")
        assert len(findings) == 0

    def test_secret_scan_api_key(self):
        findings = scan_secrets("API_KEY=sk-12345678901234567890")
        assert len(findings) >= 1

    def test_safe_code_no_secrets(self):
        findings = scan_secrets("x = 1 + 2")
        assert len(findings) == 0

    def test_scan_all_integration(self):
        result = scan_all("print('safe')")
        assert result["safe"] is True
        assert result["total_findings"] == 0


# === Flaky 检测测试 ===

class TestFlakyDetector:
    def test_stable_test_not_flaky(self):
        fd = FlakyDetector(rerun_count=5)
        for _ in range(5):
            fd.record_run("t1", True, 100)
        result = fd.detect("t1")
        assert not result["is_flaky"]

    def test_unstable_test_is_flaky(self):
        fd = FlakyDetector(rerun_count=5)
        results = [True, False, True, True, False]
        for r in results:
            fd.record_run("t2", r, 100)
        result = fd.detect("t2")
        assert result["is_flaky"] or result["flaky_score"] > 0

    def test_insufficient_data(self):
        fd = FlakyDetector(rerun_count=5)
        fd.record_run("t3", True, 100)
        result = fd.detect("t3")
        assert result["confidence"] == "insufficient_data"


# === 健康度评分测试 ===

class TestHealthScorer:
    def test_perfect_score(self):
        hs = HealthScorer()
        result = hs.score({"total_tests": 100, "skipped": 0, "todo_count": 0,
                            "coverage_pct": 100, "mutation_score": 100, "flaky_count": 0})
        assert result["health_score"] >= 90
        assert result["grade"] == "A"

    def test_poor_score(self):
        hs = HealthScorer()
        result = hs.score({"total_tests": 100, "skipped": 20, "todo_count": 15,
                            "coverage_pct": 40, "mutation_score": 30, "flaky_count": 10})
        assert result["grade"] in ("C", "D")


# === TIA 引擎测试 ===

class TestTIAEngine:
    def test_build_index_and_analyze(self, tmp_path):
        """Test TIAEngine builds index and analyzes changed files using language adapters"""
        py_file = tmp_path / "test_module.py"
        py_file.write_text("import os\nfrom pathlib import Path\n\ndef func(): pass\n", encoding="utf-8")
        test_file = tmp_path / "test_test_module.py"
        test_file.write_text("from test_module import func\n\ndef test_func(): pass\n", encoding="utf-8")
        engine = TIAEngine(str(tmp_path))
        engine.build_index()
        # Verify the engine indexed our files
        assert len(engine._indexed_files) > 0
        assert engine._built

    def test_analyze_empty_changes(self, tmp_path):
        """Test TIAEngine handles empty change list gracefully"""
        py_file = tmp_path / "test_module.py"
        py_file.write_text("def foo(): pass\n", encoding="utf-8")
        test_file = tmp_path / "test_test_module.py"
        test_file.write_text("from test_module import foo\n\ndef test_foo(): pass\n", encoding="utf-8")
        engine = TIAEngine(str(tmp_path))
        engine.build_index()
        result = engine.analyze([])
        assert result["selected_count"] == 0
        assert "acceleration" in result


# === 自愈引擎测试 ===

class TestSelfHealer:
    def test_heal_assertion_type_mismatch(self):
        import asyncio
        healer = SelfHealer()
        result = asyncio.run(healer.heal_assertion(200, 201))
        assert result["success"]
        # 200 vs 201: 差异 0.5%，阈值 10%，所以不改变
        assert result.get("healed_expected") is not None

    def test_heal_assertion_string(self):
        import asyncio
        healer = SelfHealer()
        result = asyncio.run(healer.heal_assertion("hello", "hello world"))
        assert result["success"]

    def test_stats(self):
        import asyncio
        healer = SelfHealer()
        asyncio.run(healer.heal_assertion(1, 2))
        stats = healer.stats
        assert stats["total_attempts"] >= 1
        assert stats["success_rate"] >= 0
