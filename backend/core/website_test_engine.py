"""网站综合测试引擎 — 功能测试 / 压力测试 / 边界测试 / 回归测试 / 功能分析

测试类型:
  1. 功能测试 (functional)  — 验证页面/链接/表单/SEO/安全等核心功能
  2. 压力测试 (stress)      — 并发请求，测量 QPS / 延迟 P50/P95/P99 / 错误率
  3. 边界测试 (boundary)    — 超长URL / 特殊字符 / 空值 / 大请求体 等边界场景
  4. 回归测试 (regression)  — 与基线结果对比，检测页面/链接/状态码变化
  5. 功能分析 (feature_analysis) — 自动分析并描述网站具备哪些功能
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from backend.core.web_crawler import CrawlResult, crawl_website
from backend.core.web_auto_tester import (
    AutoTestResult, CheckItem, WebsiteTestCase,
    auto_test_website, _generate_and_run_test_cases, _generate_form_sample,
)

logger = logging.getLogger("testforge")


# ============ 数据结构 ============

@dataclass
class StressResult:
    """压力测试结果"""
    url: str
    concurrency: int = 0          # 并发数
    total_requests: int = 0       # 总请求数
    success_count: int = 0        # 成功数
    failed_count: int = 0         # 失败数
    duration_ms: int = 0          # 总耗时
    qps: float = 0.0             # 每秒请求数
    latencies: list[float] = field(default_factory=list)  # 每个请求延迟(ms)
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min_latency: float = 0.0
    max_latency: float = 0.0
    avg_latency: float = 0.0
    error_rate: float = 0.0       # 错误率 0-1
    status_codes: dict = field(default_factory=dict)  # {200: 95, 500: 5}

    def to_dict(self) -> dict:
        return {
            "url": self.url, "concurrency": self.concurrency,
            "total_requests": self.total_requests,
            "success_count": self.success_count, "failed_count": self.failed_count,
            "duration_ms": self.duration_ms, "qps": round(self.qps, 2),
            "p50": round(self.p50, 2), "p95": round(self.p95, 2), "p99": round(self.p99, 2),
            "min_latency": round(self.min_latency, 2), "max_latency": round(self.max_latency, 2),
            "avg_latency": round(self.avg_latency, 2),
            "error_rate": round(self.error_rate, 4),
            "status_codes": self.status_codes,
        }


@dataclass
class WebsiteFeature:
    """网站功能描述项"""
    name: str                     # 功能名称
    category: str                 # 分类：navigation / form / content / api / media / seo / security
    description: str              # 功能描述
    evidence: str = ""            # 证据（URL/示例）
    status: str = "detected"      # detected / missing / warning

    def to_dict(self) -> dict:
        return {
            "name": self.name, "category": self.category,
            "description": self.description, "evidence": self.evidence,
            "status": self.status,
        }


@dataclass
class ComprehensiveTestResult:
    """综合测试结果"""
    start_url: str
    # 各类测试结果
    functional: Optional[dict] = None        # 功能测试结果（AutoTestResult.to_dict()）
    stress: Optional[dict] = None            # 压力测试结果
    boundary: Optional[dict] = None          # 边界测试结果
    regression: Optional[dict] = None        # 回归测试结果
    features: list[dict] = field(default_factory=list)  # 网站功能分析
    # 汇总
    summary: dict = field(default_factory=dict)
    duration_ms: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "start_url": self.start_url,
            "functional": self.functional,
            "stress": self.stress,
            "boundary": self.boundary,
            "regression": self.regression,
            "features": self.features,
            "summary": self.summary,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


# ============ 压力测试 ============

async def run_stress_test(
    url: str,
    *,
    concurrency: int = 10,
    total_requests: int = 100,
    timeout: int = 10,
) -> StressResult:
    """对指定URL执行压力测试

    Args:
        url: 目标URL
        concurrency: 并发数
        total_requests: 总请求数
        timeout: 单请求超时秒数
    """
    result = StressResult(url=url, concurrency=concurrency, total_requests=total_requests)
    start = time.time()

    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    connector = aiohttp.TCPConnector(limit=concurrency, ssl=False)
    headers = {"User-Agent": "TestForgeStress/1.0"}

    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    status_codes: dict[int, int] = {}

    async def _one_request(session: aiohttp.ClientSession):
        async with semaphore:
            t0 = time.time()
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    await resp.read()
                    elapsed = (time.time() - t0) * 1000
                    latencies.append(elapsed)
                    status_codes[resp.status] = status_codes.get(resp.status, 0) + 1
                    return resp.status < 400
            except asyncio.TimeoutError:
                latencies.append((time.time() - t0) * 1000)
                return False
            except Exception:
                latencies.append((time.time() - t0) * 1000)
                return False

    async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector, headers=headers) as session:
        # 先发一个预热请求
        try:
            async with session.get(url, allow_redirects=True) as resp:
                await resp.read()
        except Exception:
            pass

        tasks = [_one_request(session) for _ in range(total_requests)]
        outcomes = await asyncio.gather(*tasks)

    result.success_count = sum(1 for o in outcomes if o)
    result.failed_count = total_requests - result.success_count
    result.duration_ms = int((time.time() - start) * 1000)
    result.latencies = sorted(latencies)
    result.status_codes = status_codes

    # 计算统计指标
    if latencies:
        n = len(latencies)
        result.min_latency = latencies[0]
        result.max_latency = latencies[-1]
        result.avg_latency = sum(latencies) / n
        result.p50 = latencies[int(n * 0.50)]
        result.p95 = latencies[int(n * 0.95)] if n > 1 else latencies[0]
        result.p99 = latencies[min(int(n * 0.99), n - 1)] if n > 1 else latencies[0]

    elapsed_sec = max(result.duration_ms / 1000, 0.001)
    result.qps = total_requests / elapsed_sec
    result.error_rate = result.failed_count / total_requests if total_requests else 0

    logger.info(
        "压力测试完成: %s | 并发%d 总%d | 成功%d 失败%d | QPS%.1f P95%.0fms 错误率%.1f%%",
        url, concurrency, total_requests, result.success_count, result.failed_count,
        result.qps, result.p95, result.error_rate * 100,
    )
    return result


# ============ 边界测试 ============

# 边界测试用例的payload生成器
_BOUNDARY_PAYLOADS = [
    # 超长URL
    {"name": "超长URL路径", "method": "GET", "url_suffix": "/" + "a" * 2000,
     "expected": "服务端不崩溃（返回4xx或正常）", "category": "boundary"},
    # 特殊字符
    {"name": "URL包含特殊字符", "method": "GET", "url_suffix": "/<script>alert(1)</script>",
     "expected": "不执行XSS，返回4xx或转义", "category": "boundary"},
    {"name": "URL包含SQL注入字符", "method": "GET", "url_suffix": "/?id=1' OR '1'='1",
     "expected": "不执行SQL，返回正常或4xx", "category": "boundary"},
    {"name": "URL包含空字节", "method": "GET", "url_suffix": "/%00",
     "expected": "不崩溃，返回4xx或正常", "category": "boundary"},
    # 不存在的路径
    {"name": "访问不存在的路径", "method": "GET", "url_suffix": "/this-page-does-not-exist-99999",
     "expected": "返回404，不返回500", "category": "boundary"},
    # 大请求体（POST）
    {"name": "POST超大请求体", "method": "POST", "url_suffix": "", "body": "X" * 100000,
     "expected": "服务端拒绝或处理，不崩溃", "category": "boundary"},
    # 空请求体
    {"name": "POST空请求体", "method": "POST", "url_suffix": "", "body": "",
     "expected": "服务端正常处理或返回4xx", "category": "boundary"},
    # 错误的Content-Type
    {"name": "POST错误Content-Type", "method": "POST", "url_suffix": "", "body": "not json",
     "headers": {"Content-Type": "application/json"},
     "expected": "返回4xx错误，不崩溃", "category": "boundary"},
]


async def run_boundary_tests(urls, *, timeout: int = 10) -> dict:
    """对指定URL执行边界测试

    Args:
        urls: 单个URL字符串或URL列表
        timeout: 单请求超时秒数
    """
    if isinstance(urls, str):
        urls = [urls]

    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    headers_default = {"User-Agent": "TestForgeBoundary/1.0"}

    all_test_cases: list[WebsiteTestCase] = []
    per_page_results: list[dict] = []
    global_case_idx = 0

    def _next_id():
        nonlocal global_case_idx
        global_case_idx += 1
        return f"BT-{global_case_idx:04d}"

    async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector, headers=headers_default) as session:
        for base_url in urls:
            page_cases = 0
            page_passed = 0
            for payload in _BOUNDARY_PAYLOADS:
                target_url = base_url.rstrip("/") + payload.get("url_suffix", "")
                req_headers = payload.get("headers", {})
                t0 = time.time()
                try:
                    if payload["method"] == "GET":
                        async with session.get(target_url, allow_redirects=False, headers=req_headers) as resp:
                            status = resp.status
                            await resp.read()
                    else:
                        body = payload.get("body", "")
                        async with session.post(target_url, data=body, allow_redirects=False, headers=req_headers) as resp:
                            status = resp.status
                            await resp.read()
                    elapsed = int((time.time() - t0) * 1000)
                    passed = status < 500
                    page_cases += 1
                    if passed:
                        page_passed += 1
                    all_test_cases.append(WebsiteTestCase(
                        id=_next_id(),
                        name=payload["name"],
                        category="boundary",
                        method=payload["method"],
                        url=target_url[:200],
                        expected=payload["expected"],
                        actual=f"HTTP {status}",
                        passed=passed,
                        status_code=status,
                        duration_ms=elapsed,
                        page_url=base_url,
                        detail="服务器未崩溃" if passed else "服务器返回5xx，可能存在稳定性问题",
                    ))
                except asyncio.TimeoutError:
                    page_cases += 1
                    all_test_cases.append(WebsiteTestCase(
                        id=_next_id(), name=payload["name"], category="boundary",
                        method=payload["method"], url=target_url[:200],
                        expected=payload["expected"], actual="请求超时",
                        passed=False, error="timeout",
                        page_url=base_url,
                        detail="服务器响应超时，可能存在性能问题",
                    ))
                except Exception as e:
                    page_cases += 1
                    all_test_cases.append(WebsiteTestCase(
                        id=_next_id(), name=payload["name"], category="boundary",
                        method=payload["method"], url=target_url[:200],
                        expected=payload["expected"], actual=f"请求异常: {e}",
                        passed=False, error=str(e)[:200],
                        page_url=base_url,
                    ))
            per_page_results.append({
                "url": base_url,
                "total": page_cases,
                "passed": page_passed,
                "failed": page_cases - page_passed,
                "pass_rate": round(page_passed / page_cases * 100, 1) if page_cases else 0,
            })

    total = len(all_test_cases)
    passed = sum(1 for tc in all_test_cases if tc.passed)
    failed = total - passed

    return {
        "test_cases": [tc.to_dict() for tc in all_test_cases],
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "per_page": per_page_results,    }

# ============ ???? ============

_BASELINE_DIR = "website_baselines"

async def run_regression_test(url: str, crawl: CrawlResult) -> dict:
    """回归测试 — 与基线对比检测变化

    基线保存在 website_baselines/<域名hash>.json
    """
    import hashlib
    domain = urlparse(url).netloc
    domain_hash = hashlib.md5(domain.encode()).hexdigest()[:12]
    baseline_path = os.path.join(_BASELINE_DIR, f"{domain_hash}.json")
    os.makedirs(_BASELINE_DIR, exist_ok=True)

    # 当前快照
    current = {
        "url": url,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "page_count": len(crawl.pages),
        "pages": [{"url": p.url, "status": p.status, "title": p.title} for p in crawl.pages],
        "total_links": crawl.total_links,
        "broken_links_count": len(crawl.broken_links),
        "forms_count": sum(len(p.forms) for p in crawl.pages),
    }

    # 加载基线
    baseline = None
    if os.path.exists(baseline_path):
        try:
            with open(baseline_path, "r", encoding="utf-8") as f:
                baseline = json.load(f)
        except Exception:
            baseline = None

    changes: list[dict] = []
    if baseline:
        # 对比页面数量
        if current["page_count"] != baseline.get("page_count", 0):
            changes.append({
                "type": "page_count_changed",
                "description": f"页面数量从 {baseline.get('page_count', 0)} 变为 {current['page_count']}",
                "severity": "info",
            })
        # 对比链接数量
        if current["total_links"] != baseline.get("total_links", 0):
            changes.append({
                "type": "link_count_changed",
                "description": f"链接数量从 {baseline.get('total_links', 0)} 变为 {current['total_links']}",
                "severity": "info",
            })
        # 对比死链数量
        if current["broken_links_count"] != baseline.get("broken_links_count", 0):
            changes.append({
                "type": "broken_link_changed",
                "description": f"死链数量从 {baseline.get('broken_links_count', 0)} 变为 {current['broken_links_count']}",
                "severity": "warning" if current["broken_links_count"] > baseline.get("broken_links_count", 0) else "info",
            })
        # 对比表单数量
        if current["forms_count"] != baseline.get("forms_count", 0):
            changes.append({
                "type": "form_count_changed",
                "description": f"表单数量从 {baseline.get('forms_count', 0)} 变为 {current['forms_count']}",
                "severity": "info",
            })
        # 对比页面状态码变化
        baseline_pages = {p["url"]: p["status"] for p in baseline.get("pages", [])}
        for p in current["pages"]:
            old_status = baseline_pages.get(p["url"])
            if old_status is not None and old_status != p["status"]:
                changes.append({
                    "type": "status_changed",
                    "description": f"页面 {p['url'][:80]} 状态码从 {old_status} 变为 {p['status']}",
                    "severity": "warning",
                })
        # 新增页面
        for p in current["pages"]:
            if p["url"] not in baseline_pages:
                changes.append({
                    "type": "page_added",
                    "description": f"新增页面: {p['title'] or p['url'][:80]}",
                    "severity": "info",
                })
        # 消失页面
        current_urls = {p["url"] for p in current["pages"]}
        for p in baseline.get("pages", []):
            if p["url"] not in current_urls:
                changes.append({
                    "type": "page_removed",
                    "description": f"页面已移除: {p.get('title', p['url'][:80])}",
                    "severity": "warning",
                })
    else:
        changes.append({
            "type": "baseline_created",
            "description": "首次测试，已创建基线快照，后续测试将与此基线对比",
            "severity": "info",
        })

    # 保存当前快照为基线
    try:
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("保存基线失败: %s", e)

    return {
        "has_baseline": baseline is not None,
        "baseline_path": baseline_path,
        "current_snapshot": current,
        "changes": changes,
        "change_count": len(changes),
        "regression_count": sum(1 for c in changes if c["severity"] == "warning"),
    }


# ============ 网站功能分析 ============

def analyze_website_features(crawl: CrawlResult) -> list[WebsiteFeature]:
    """分析网站具备哪些功能，生成功能描述列表"""
    features: list[WebsiteFeature] = []

    # 1. 导航功能
    if crawl.pages:
        features.append(WebsiteFeature(
            name="多页面网站",
            category="navigation",
            description=f"网站包含 {len(crawl.pages)} 个页面，支持页面间导航",
            evidence=f"首页: {crawl.pages[0].title or crawl.pages[0].url}",
        ))

    total_internal = sum(len(p.internal_links) for p in crawl.pages)
    total_external = sum(len(p.external_links) for p in crawl.pages)
    if total_internal > 0:
        features.append(WebsiteFeature(
            name="内部链接导航",
            category="navigation",
            description=f"网站共有 {total_internal} 个内部链接，支持站内页面跳转",
        ))
    if total_external > 0:
        features.append(WebsiteFeature(
            name="外部链接引用",
            category="navigation",
            description=f"网站引用了 {total_external} 个外部链接",
        ))

    # 2. 表单功能
    all_forms = []
    for p in crawl.pages:
        all_forms.extend(p.forms)
    if all_forms:
        form_types = []
        for f in all_forms:
            field_names = " ".join(fld["name"].lower() for fld in f.fields)
            if "search" in field_names or "q" in field_names:
                form_types.append("搜索")
            elif "email" in field_names or "password" in field_names:
                form_types.append("登录/注册")
            elif "message" in field_names or "comment" in field_names:
                form_types.append("留言/评论")
            elif "name" in field_names and "email" in field_names:
                form_types.append("联系表单")
            else:
                form_types.append("数据提交")
        unique_types = list(set(form_types))
        features.append(WebsiteFeature(
            name="表单交互",
            category="form",
            description=f"网站包含 {len(all_forms)} 个表单，支持 {', '.join(unique_types)} 等功能",
            evidence=f"表单提交方式: {', '.join(set(f.method for f in all_forms))}",
        ))

    # 3. 内容功能
    total_images = sum(len(p.images) for p in crawl.pages)
    total_scripts = sum(len(p.scripts) for p in crawl.pages)
    total_styles = sum(len(p.styles) for p in crawl.pages)

    if total_images > 0:
        features.append(WebsiteFeature(
            name="图片展示",
            category="media",
            description=f"网站包含 {total_images} 张图片，支持视觉内容展示",
        ))
    if total_scripts > 0:
        features.append(WebsiteFeature(
            name="JavaScript交互",
            category="content",
            description=f"网站加载了 {total_scripts} 个脚本，支持动态交互功能",
        ))
    if total_styles > 0:
        features.append(WebsiteFeature(
            name="样式美化",
            category="content",
            description=f"网站引用了 {total_styles} 个样式表，支持页面美化",
        ))

    # 4. SEO功能
    pages_with_title = sum(1 for p in crawl.pages if p.title)
    pages_with_h1 = sum(1 for p in crawl.pages if p.h1)
    pages_with_desc = sum(1 for p in crawl.pages if p.meta_description)

    if pages_with_title:
        features.append(WebsiteFeature(
            name="页面标题",
            category="seo",
            description=f"{pages_with_title}/{len(crawl.pages)} 个页面设置了标题",
        ))
    if pages_with_h1:
        features.append(WebsiteFeature(
            name="H1标题结构",
            category="seo",
            description=f"{pages_with_h1}/{len(crawl.pages)} 个页面包含H1标签",
        ))
    if pages_with_desc:
        features.append(WebsiteFeature(
            name="Meta描述",
            category="seo",
            description=f"{pages_with_desc}/{len(crawl.pages)} 个页面设置了meta description",
        ))
    else:
        features.append(WebsiteFeature(
            name="Meta描述",
            category="seo",
            description="网站未设置meta description，影响搜索引擎收录",
            status="missing",
        ))

    # 5. 安全功能
    https_pages = sum(1 for p in crawl.pages if p.url.startswith("https://"))
    if https_pages == len(crawl.pages) and crawl.pages:
        features.append(WebsiteFeature(
            name="HTTPS加密",
            category="security",
            description="网站全部页面使用HTTPS加密传输",
            status="detected",
        ))
    elif https_pages > 0:
        features.append(WebsiteFeature(
            name="HTTPS加密",
            category="security",
            description=f"{https_pages}/{len(crawl.pages)} 个页面使用HTTPS",
            status="warning",
        ))
    else:
        features.append(WebsiteFeature(
            name="HTTPS加密",
            category="security",
            description="网站未使用HTTPS，存在安全风险",
            status="missing",
        ))

    # 6. 性能特征
    avg_response = sum(p.response_time_ms for p in crawl.pages) / len(crawl.pages) if crawl.pages else 0
    if avg_response > 0:
        perf_status = "detected" if avg_response < 1500 else "warning"
        features.append(WebsiteFeature(
            name="响应性能",
            category="content",
            description=f"平均响应时间 {avg_response:.0f}ms",
            status=perf_status,
        ))

    return features


# ============ 综合测试入口 ============

async def run_comprehensive_test(
    start_url: str,
    *,
    run_functional: bool = True,
    run_stress: bool = True,
    run_boundary: bool = True,
    run_regression: bool = True,
    run_feature_analysis: bool = True,
    use_browser: bool = False,
    crawl_depth: int = 1,
    max_pages: int = 10,
    stress_concurrency: int = 10,
    stress_total: int = 50,
    timeout: int = 10,
) -> ComprehensiveTestResult:
    """执行综合网站测试

    Args:
        start_url: 目标网站URL
        run_functional: 是否执行功能测试
        run_stress: 是否执行压力测试
        run_boundary: 是否执行边界测试
        run_regression: 是否执行回归测试
        run_feature_analysis: 是否执行功能分析
    """
    start = time.time()
    result = ComprehensiveTestResult(start_url=start_url)

    try:
        # 先爬取网站（所有测试共享爬取结果）
        logger.info("综合测试开始: %s", start_url)
        crawl: CrawlResult = await crawl_website(
            start_url, max_depth=crawl_depth, max_pages=max_pages,
            max_concurrency=5, timeout=timeout,
            use_browser=use_browser,
        )

        # 1. 功能测试
        if run_functional:
            logger.info("[1/5] 执行功能测试...")
            functional_result = await auto_test_website(
                start_url, crawl_depth=crawl_depth, max_pages=max_pages,
                max_concurrency=5, timeout=timeout, test_forms=True,
            )
            # 复用已有爬取结果，避免重复爬取
            functional_result.crawl = crawl.to_dict()
            functional_result.pages_tested = len(crawl.pages)
            # 生成并执行测试用例
            timeout_cfg = aiohttp.ClientTimeout(total=timeout)
            connector = aiohttp.TCPConnector(limit=5, ssl=False)
            headers = {"User-Agent": "TestForgeBot/1.0"}
            async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector, headers=headers) as session:
                await _generate_and_run_test_cases(crawl, session, functional_result)
            functional_result.test_total = len(functional_result.test_cases)
            functional_result.test_passed = sum(1 for tc in functional_result.test_cases if tc.passed)
            functional_result.test_failed = functional_result.test_total - functional_result.test_passed
            result.functional = functional_result.to_dict()
            logger.info("[1/5] 功能测试完成: %d 用例", functional_result.test_total)

        # 收集内部页面 URL（用于边界测试和压力测试）
        internal_page_urls: list[str] = []
        for page in crawl.pages:
            if page.url != start_url and page.status < 400:
                internal_page_urls.append(page.url)
        test_urls = [start_url] + internal_page_urls[:5]  # 首页 + 最多5个内部页面
        logger.info("发现 %d 个内部页面，将测试 %d 个页面", len(internal_page_urls), len(test_urls))

        # 2. 压力测试（首页 + 内部页面）
        if run_stress:
            logger.info("[2/5] 执行压力测试...")
            all_stress_results: list[dict] = []
            for test_url in test_urls:
                stress_result = await run_stress_test(
                    test_url, concurrency=stress_concurrency,
                    total_requests=stress_total, timeout=timeout,
                )
                all_stress_results.append(stress_result.to_dict())
            result.stress = all_stress_results[0] if all_stress_results else {}
            if len(all_stress_results) > 1:
                result.stress["internal_pages"] = all_stress_results[1:]
            logger.info("[2/5] 压力测试完成: %d 个页面", len(all_stress_results))

        # 3. 边界测试（首页 + 内部页面）
        if run_boundary:
            logger.info("[3/5] 执行边界测试 (%d 个页面)...", len(test_urls))
            boundary_result = await run_boundary_tests(test_urls, timeout=timeout)
            result.boundary = boundary_result
            logger.info("[3/5] 边界测试完成: %d/%d 通过 (覆盖 %d 页面)",
                         boundary_result["passed"], boundary_result["total"], len(test_urls))

        # 4. 回归测试
        if run_regression:
            logger.info("[4/5] 执行回归测试...")
            regression_result = await run_regression_test(start_url, crawl)
            result.regression = regression_result
            logger.info("[4/5] 回归测试完成: %d 项变化", regression_result["change_count"])

        # 5. 功能分析
        if run_feature_analysis:
            logger.info("[5/5] 执行功能分析...")
            features = analyze_website_features(crawl)
            result.features = [f.to_dict() for f in features]
            logger.info("[5/5] 功能分析完成: 识别 %d 项功能", len(features))

        # 汇总
        summary = {
            "url": start_url,
            "pages_tested": len(crawl.pages),
            "duration_ms": int((time.time() - start) * 1000),
        }
        if result.functional:
            summary["functional_score"] = result.functional.get("score", 0)
            summary["functional_pass_rate"] = (
                round(result.functional.get("test_passed", 0) /
                      max(result.functional.get("test_total", 1), 1) * 100, 1)
            )
        if result.stress:
            summary["stress_qps"] = result.stress.get("qps", 0)
            summary["stress_p95"] = result.stress.get("p95", 0)
            summary["stress_error_rate"] = result.stress.get("error_rate", 0)
        if result.boundary:
            summary["boundary_pass_rate"] = result.boundary.get("pass_rate", 0)
        if result.regression:
            summary["regression_changes"] = result.regression.get("change_count", 0)
        if result.features:
            summary["feature_count"] = len(result.features)
            summary["features_detected"] = sum(1 for f in result.features if f.get("status") == "detected")
            summary["features_missing"] = sum(1 for f in result.features if f.get("status") == "missing")

        # 综合评分
        score = 100
        if result.functional:
            score = min(score, result.functional.get("score", 100))
        if result.stress:
            if result.stress.get("error_rate", 0) > 0.1:
                score -= 20
            if result.stress.get("p95", 0) > 3000:
                score -= 10
        if result.boundary:
            score -= (100 - result.boundary.get("pass_rate", 100)) * 0.2
        if result.regression:
            score -= result.regression.get("regression_count", 0) * 5
        summary["overall_score"] = max(0, min(100, int(score)))

        result.summary = summary
        result.duration_ms = int((time.time() - start) * 1000)
        logger.info("综合测试完成: %s | 总分 %d | 耗时 %dms",
                     start_url, summary["overall_score"], result.duration_ms)

    except Exception as e:
        logger.error("综合测试失败: %s", e)
        result.error = str(e)

    return result
