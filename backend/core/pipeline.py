"""Pipeline engine"""

import asyncio
import logging
import time
import uuid
from enum import Enum
from typing import Callable, Optional

try:
    import psutil
    _has_psutil = True
except ImportError:
    _has_psutil = False

logger = logging.getLogger("testforge")

# Lazy import for evolution loop -- avoids circular import
def _get_evolution_loop():
    """Lazy-load the evolution loop singleton."""
    return __import__("backend.core.self_evolution", fromlist=["evolution_loop"]).evolution_loop


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineEngine:
    """Test pipeline orchestration engine."""

    def __init__(self):
        self._subscribers: dict[str, Callable] = {}
        self._paused = False
        self._cancelled = False
        self._current_stage: Optional[str] = None
        self._stage_history: list[dict] = []
        self._lock = asyncio.Lock()

    def start(self):
        self._cancelled = False
        self._paused = False

    def stop(self):
        self._cancelled = True

    def pause(self):
        self._paused = True
        self._emit("pipeline_paused", {})

    def resume(self):
        self._paused = False
        self._emit("pipeline_resumed", {})

    def cancel(self):
        self._cancelled = True
        self._emit("pipeline_cancelled", {})

    def skip_stage(self, stage_id: str):
        self._emit("stage_skipped", {"stage_id": stage_id})

    def subscribe(self, callback: Callable) -> str:
        sid = str(uuid.uuid4())[:8]
        self._subscribers[sid] = callback
        return sid

    def unsubscribe(self, sid: str):
        self._subscribers.pop(sid, None)

    def subscriber_count(self) -> int:
        """Current subscriber count (for metrics/readiness probes)."""
        return len(self._subscribers)

    async def _emit(self, event_type: str, data: dict):
        """Push event to all subscribers."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        for cb in self._subscribers.values():
            try:
                await cb(event)
            except Exception as e:
                logger.warning("Subscriber callback error: %s", e)

    async def run_stage(self, stage_id: str, stage_name: str, coro):
        """Execute a single pipeline stage with lifecycle events."""
        self._current_stage = stage_id
        start = time.time()

        await self._emit("stage_start", {
            "stage_id": stage_id,
            "name": stage_name,
        })

        # Wait if paused
        while self._paused and not self._cancelled:
            await asyncio.sleep(0.1)

        if self._cancelled:
            await self._emit("stage_cancelled", {"stage_id": stage_id})
            return

        try:
            result = await coro
            elapsed = time.time() - start

            await self._emit("stage_complete", {
                "stage_id": stage_id,
                "name": stage_name,
                "duration_s": round(elapsed, 2),
                "result": "pass",
            })

            self._stage_history.append({
                "stage_id": stage_id,
                "status": StageStatus.PASSED,
                "duration_s": elapsed,
            })

            return result

        except Exception as e:
            elapsed = time.time() - start

            await self._emit("stage_error", {
                "stage_id": stage_id,
                "name": stage_name,
                "error": str(e),
                "duration_s": round(elapsed, 2),
            })

            self._stage_history.append({
                "stage_id": stage_id,
                "status": StageStatus.FAILED,
                "error": str(e),
            })

            raise

    async def run_evolution_cycle(self, results: list, project_id: str = "default") -> dict:
        """Run full evolution cycle after test execution.

        Records strategy calls, updates strategy weights via Thompson sampling,
        builds knowledge base from execution patterns, and returns updated weights.
        Called automatically after each test execution completes.
        """
        try:
            ev = _get_evolution_loop()
            ev.set_project(project_id)

            # Record strategy calls for each result
            for r in results:
                strategy = r.get("strategy", "template")
                await ev.on_strategy_called(
                    strategy,
                    case_count=1,
                    duration_ms=r.get("duration_ms", 0),
                )

            # Run full execution-complete cycle (updates weights + builds knowledge)
            outcome = await ev.on_execution_complete(results)
            return outcome
        except Exception as e:
            logger.exception("Evolution cycle failed: %s", e)
            return {"error": str(e)}

    async def run_evolution_analysis(self, project_id: str = "default") -> dict:
        """Periodic analysis: gather evolution report and health metrics.

        Designed for background scheduler execution (e.g., every 5-15 minutes).
        """
        try:
            ev = _get_evolution_loop()
            ev.set_project(project_id)
            return ev.get_evolution_report()
        except Exception as e:
            logger.exception("Evolution analysis failed: %s", e)
            return {"error": str(e)}

    async def emit_progress(self, stage_id: str, progress_pct: float, sub_step: str = ""):
        """Push intra-stage progress."""
        await self._emit("stage_progress", {
            "stage_id": stage_id,
            "progress_pct": progress_pct,
            "sub_step": sub_step,
        })

    async def emit_resource_snapshot(self):
        """Push resource usage snapshot."""
        if not _has_psutil:
            return
        await self._emit("resource_snapshot", {
            "cpu_pct": round(psutil.cpu_percent(), 1),
            "mem_gb": round(psutil.virtual_memory().used / 1e9, 2),
            "disk_pct": round(psutil.disk_usage("/").percent, 1),
        })

    async def emit_test_result(self, stage_id: str, test_name: str, status: str, duration_ms: int):
        """Push individual test result."""
        await self._emit("test_result", {
            "stage_id": stage_id,
            "test_name": test_name,
            "status": status,
            "duration_ms": duration_ms,
        })

    async def emit_alert(self, severity: str, message: str, stage_id: str = ""):
        """Push alert notification."""
        await self._emit("alert", {
            "severity": severity,
            "message": message,
            "stage_id": stage_id,
        })

    async def emit_gate_result(self, gate_name: str, passed: bool, checks: dict):
        """Push quality gate result."""
        await self._emit("gate_result", {
            "gate": gate_name,
            "passed": passed,
            "checks": checks,
        })


# Global singleton
pipeline_engine = PipelineEngine()
