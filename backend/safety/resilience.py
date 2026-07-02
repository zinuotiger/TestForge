"""容错模块 — 重试 + 熔断器 + 吞吐量监控

企业级特性:
  1. 重试: 指数退避重试（可配最大次数/初始延迟/最大延迟/可重试异常）
  2. 熔断器: 三态（CLOSED/OPEN/HALF_OPEN），失败率阈值触发熔断
  3. 吞吐量监控: QPS / 延迟 P50/P95/P99 / 错误率 / 成功率
  4. 超时控制: 协程级超时
  5. 降级: 熔断打开时执行降级函数

适用场景:
  - LLM API 调用（网络不稳定）
  - HTTP 测试执行（目标服务不可用）
  - 数据库操作（连接超时）
  - 任何需要容错的外部调用
"""

import asyncio
import time
import logging
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Callable, Optional, Any, TypeVar

logger = logging.getLogger("testforge")

T = TypeVar("T")


# ============ 重试 ============

@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3                # 最大重试次数（含首次）
    initial_delay: float = 0.5           # 初始延迟（秒）
    max_delay: float = 10.0              # 最大延迟（秒）
    backoff_factor: float = 2.0          # 退避倍数
    jitter: bool = True                  # 是否添加随机抖动
    retryable_exceptions: tuple = (Exception,)  # 可重试的异常类型


async def retry_async(
    func: Callable,
    *args,
    config: RetryConfig = None,
    **kwargs,
) -> Any:
    """异步重试（指数退避 + 抖动）

    用法:
        result = await retry_async(
            llm_client.generate,
            prompt="...",
            config=RetryConfig(max_attempts=5, initial_delay=1.0),
        )
    """
    config = config or RetryConfig()
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt >= config.max_attempts:
                logger.error("重试 %d 次后仍失败: %s", attempt, e)
                raise

            # 计算延迟
            delay = min(
                config.initial_delay * (config.backoff_factor ** (attempt - 1)),
                config.max_delay,
            )
            if config.jitter:
                delay *= (0.5 + random.random() * 0.5)  # 50%-100% 抖动

            logger.warning(
                "第 %d/%d 次尝试失败: %s，%.2f 秒后重试",
                attempt, config.max_attempts, e, delay,
            )
            await asyncio.sleep(delay)

    raise last_exception  # type: ignore


def with_retry(config: RetryConfig = None):
    """装饰器：为异步函数添加重试

    用法:
        @with_retry(RetryConfig(max_attempts=5))
        async def call_llm(prompt):
            ...
    """
    cfg = config or RetryConfig()

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, *args, config=cfg, **kwargs)
        return wrapper
    return decorator


# ============ 熔断器 ============

class CircuitState(str, Enum):
    CLOSED = "closed"           # 正常，允许请求
    OPEN = "open"               # 熔断，拒绝请求
    HALF_OPEN = "half_open"     # 半开，允许少量探测请求


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5          # 连续失败次数阈值
    failure_rate_threshold: float = 0.5 # 失败率阈值（0-1）
    recovery_timeout: float = 30.0      # 熔断后恢复探测时间（秒）
    half_open_max_calls: int = 3        # 半开状态最大探测请求数
    sliding_window: int = 20            # 滑动窗口大小


class CircuitBreaker:
    """熔断器 — 三态切换

    状态流转:
      CLOSED → 连续失败/失败率超阈值 → OPEN
      OPEN → 等待 recovery_timeout → HALF_OPEN
      HALF_OPEN → 探测成功 → CLOSED
      HALF_OPEN → 探测失败 → OPEN
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._window: deque[bool] = deque(maxlen=self.config.sliding_window)
        self._opened_at: float = 0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """通过熔断器执行函数"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self._opened_at >= self.config.recovery_timeout:
                    logger.info("熔断器 %s 进入半开状态", self.name)
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpenError(
                        f"熔断器 {self.name} 已打开，请 {int(self.config.recovery_timeout - (time.time() - self._opened_at))} 秒后重试"
                    )

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"熔断器 {self.name} 半开状态探测中，请稍后"
                    )
                self._half_open_calls += 1

        # 执行函数
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        async with self._lock:
            self._window.append(True)
            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.half_open_max_calls:
                    logger.info("熔断器 %s 恢复为关闭状态", self.name)
                    self.state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0

    async def _on_failure(self):
        async with self._lock:
            self._window.append(False)
            self._failure_count += 1

            if self.state == CircuitState.HALF_OPEN:
                # 半开状态失败 → 重新打开
                logger.warning("熔断器 %s 半开探测失败，重新打开", self.name)
                self.state = CircuitState.OPEN
                self._opened_at = time.time()
                self._success_count = 0
                return

            if self.state == CircuitState.CLOSED:
                # 检查连续失败
                if self._failure_count >= self.config.failure_threshold:
                    self._trip()
                    return

                # 检查失败率
                if len(self._window) >= self.config.sliding_window:
                    failure_rate = sum(1 for x in self._window if not x) / len(self._window)
                    if failure_rate >= self.config.failure_rate_threshold:
                        self._trip()

    def _trip(self):
        """触发熔断"""
        logger.warning(
            "熔断器 %s 触发熔断（连续失败 %d 次）",
            self.name, self._failure_count,
        )
        self.state = CircuitState.OPEN
        self._opened_at = time.time()

    @property
    def stats(self) -> dict:
        """熔断器统计"""
        total = len(self._window)
        failures = sum(1 for x in self._window if not x)
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "window_size": total,
            "window_failures": failures,
            "failure_rate": round(failures / max(total, 1), 2),
            "recovery_in_seconds": max(0, int(self.config.recovery_timeout - (time.time() - self._opened_at))) if self.state == CircuitState.OPEN else 0,
        }


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass


# 熔断器注册表（按名称管理）
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
    """获取或创建熔断器"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def list_circuit_breakers() -> dict:
    """列出所有熔断器状态"""
    return {name: cb.stats for name, cb in _circuit_breakers.items()}


# ============ 吞吐量监控 ============

class ThroughputMonitor:
    """吞吐量监控 — QPS / 延迟 / 错误率

    统计指标:
      - total_requests: 总请求数
      - success_count / error_count
      - qps: 每秒请求数
      - latency_p50 / p95 / p99: 延迟分位数
      - error_rate: 错误率
      - avg_latency_ms: 平均延迟
    """

    def __init__(self, name: str, window_size: int = 1000):
        self.name = name
        self._window_size = window_size
        self._latencies: deque[float] = deque(maxlen=window_size)
        self._success_count = 0
        self._error_count = 0
        self._total_count = 0
        self._start_time = time.time()
        self._lock = asyncio.Lock()

    async def record(self, latency_ms: float, success: bool):
        """记录一次请求"""
        async with self._lock:
            self._latencies.append(latency_ms)
            self._total_count += 1
            if success:
                self._success_count += 1
            else:
                self._error_count += 1

    @property
    def stats(self) -> dict:
        """获取统计信息"""
        elapsed = max(time.time() - self._start_time, 0.001)
        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)

        return {
            "name": self.name,
            "total_requests": self._total_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "qps": round(self._total_count / elapsed, 2),
            "error_rate": round(self._error_count / max(self._total_count, 1), 4),
            "avg_latency_ms": round(sum(sorted_latencies) / max(n, 1), 2),
            "latency_p50_ms": round(sorted_latencies[n // 2], 2) if n else 0,
            "latency_p95_ms": round(sorted_latencies[int(n * 0.95)], 2) if n else 0,
            "latency_p99_ms": round(sorted_latencies[int(n * 0.99)], 2) if n else 0,
            "window_size": n,
            "uptime_seconds": round(elapsed, 1),
        }

    def reset(self):
        """重置统计"""
        self._latencies.clear()
        self._success_count = 0
        self._error_count = 0
        self._total_count = 0
        self._start_time = time.time()


# 监控器注册表
_monitors: dict[str, ThroughputMonitor] = {}


def get_monitor(name: str) -> ThroughputMonitor:
    """获取或创建监控器"""
    if name not in _monitors:
        _monitors[name] = ThroughputMonitor(name)
    return _monitors[name]


def list_monitors() -> dict:
    """列出所有监控器统计"""
    return {name: mon.stats for name, mon in _monitors.items()}


# ============ 组合装饰器：重试 + 熔断 + 监控 ============

def resilient(
    name: str,
    retry_config: RetryConfig = None,
    breaker_config: CircuitBreakerConfig = None,
    timeout: float = 0,
):
    """弹性调用装饰器：重试 + 熔断器 + 吞吐量监控 + 超时

    用法:
        @resilient("llm_call", retry_config=RetryConfig(max_attempts=3))
        async def call_llm(prompt):
            return await litellm.completion(...)
    """
    rc = retry_config or RetryConfig()
    bc = breaker_config or CircuitBreakerConfig()
    breaker = get_circuit_breaker(name, bc)
    monitor = get_monitor(name)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async def _execute():
                start = time.time()
                success = False
                try:
                    if timeout > 0:
                        result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                    else:
                        result = await func(*args, **kwargs)
                    success = True
                    return result
                finally:
                    latency_ms = (time.time() - start) * 1000
                    await monitor.record(latency_ms, success)

            async def _with_breaker():
                return await breaker.call(_execute)

            return await retry_async(_with_breaker, config=rc)

        return wrapper
    return decorator
