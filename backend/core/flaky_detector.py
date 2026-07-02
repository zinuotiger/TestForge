"""Flaky detector -- Bayesian statistics + auto-isolation"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("testforge")

# Lazy import for evolution loop -- avoids circular import
def _get_evolution_loop():
    return __import__("backend.core.self_evolution", fromlist=["evolution_loop"]).evolution_loop


class FlakyDetector:
    """Flaky test detector based on Bayesian statistics."""

    def __init__(self, window_size: int = 10, threshold: float = 0.3, rerun_count: int = 3):
        self.window_size = window_size
        self.threshold = threshold
        self.rerun_count = rerun_count
        self._history: dict[str, list[dict]] = {}

    def record(self, test_name: str, passed: bool, duration_ms: int = 0):
        """Record a single test run result."""
        if test_name not in self._history:
            self._history[test_name] = []
        self._history[test_name].append({
            "passed": passed,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        })
        # Keep window size bounded
        if len(self._history[test_name]) > self.window_size * 3:
            self._history[test_name] = self._history[test_name][-self.window_size * 3:]

    def record_run(self, test_name: str, passed: bool, duration_ms: int = 0):
        """Alias for record -- provided for backward compatibility."""
        self.record(test_name, passed, duration_ms)

    def detect(self, test_name: str) -> dict:
        """Detect whether a test is flaky."""
        history = self._history.get(test_name, [])
        if len(history) < self.rerun_count:
            return {"test": test_name, "is_flaky": False, "flaky_score": 0.0, "confidence": "insufficient_data"}

        recent = history[-self.window_size:]

        # Count pass/fail transitions
        transitions = 0
        for i in range(1, len(recent)):
            if recent[i]["passed"] != recent[i - 1]["passed"]:
                transitions += 1

        # Bayesian estimation of flaky probability
        alpha = 2  # Prior: believe the test is stable
        beta = 8   # Prior: believe the test is stable
        alpha += transitions
        beta += len(recent) - transitions

        flaky_score = alpha / (alpha + beta)
        confidence = 1.0 - (1.0 / (1 + transitions))

        is_flaky = flaky_score > self.threshold and confidence > 0.5

        return {
            "test": test_name,
            "is_flaky": is_flaky,
            "flaky_score": round(flaky_score, 3),
            "confidence": round(confidence, 3),
            "transitions": transitions,
            "window_size": len(recent),
        }

    def classify(self, test_name: str) -> str:
        """Classify the root cause of flakiness."""
        history = self._history.get(test_name, [])
        if len(history) < 5:
            return "unknown"

        recent = history[-self.rerun_count:]
        durations = [r["duration_ms"] for r in recent]

        # Timing dependency: high duration variance
        if len(durations) >= 3:
            avg = sum(durations) / len(durations)
            variance = sum((d - avg) ** 2 for d in durations) / len(durations)
            if variance > avg * avg * 0.5:
                return "timing_dependency"

        # Environment dependency: alternating pass/fail
        pattern = "".join("P" if r["passed"] else "F" for r in recent)
        if "PFPF" in pattern or "FPFP" in pattern:
            return "environment_dependency"

        # Data dependency: passes then fails
        if pattern.startswith("PPP") and "F" in pattern:
            return "data_dependency"

        return "assertion_instability"

    def scan_all(self) -> list[dict]:
        """Scan all tracked tests."""
        results = []
        for test_name in self._history:
            result = self.detect(test_name)
            result["root_cause"] = self.classify(test_name)
            if result["is_flaky"]:
                results.append(result)
        return sorted(results, key=lambda x: -x["flaky_score"])


# Global singleton
flaky_detector = FlakyDetector()


async def report_flaky_to_evolution(detector=None):
    """Report flaky detection results to evolution loop for external callers."""
    d = detector or flaky_detector
    results = d.scan_all()
    if not results:
        return
    try:
        ev = _get_evolution_loop()
        for r in results:
            await ev.on_flaky_detected(r["test"], r["flaky_score"], r.get("root_cause", "unknown"))
    except Exception:
        pass
