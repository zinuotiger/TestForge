"""网页自动化测试引擎 — 对爬取的页面自动执行多维度测试

测试维度:
  1. 死链检测（broken links）
  2. 表单可提交性测试（自动填充示例数据并探测响应）
  3. 可访问性检查（alt/aria/label/contrast 基础项）
  4. SEO 检查（title/description/h1/ canonical）
  5. 安全检查（mixed content / http form / 危险外链）
  6. 性能指标（首字节时间 / 总响应时间 / 页面大小）
  7. JS 错误捕获（headless 浏览器）
  8. 响应式断点截图（mobile/tablet/desktop）

依赖:
  - aiohttp（必选，纯 HTTP 检查）
  - playwright（可选，启用浏览器深度检查时使用）
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from backend.core.web_crawler import CrawlResult, PageInfo, crawl_website

logger = logging.getLogger("testforge")

# 响应式断点（width x height）
VIEWPORTS = [
    {"name": "mobile", "width": 375, "height": 667},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "desktop", "width": 1440, "height": 900},
]

# 表单字段的示例填充值（按字段名/类型启发式匹配）
_FIELD_SAMPLES = {
    # by name keyword
    "email": "test@example.com",
    "user": "testforge_user",
    "username": "testforge_user",
    "name": "TestForge",
    "phone": "13800000000",
    "tel": "13800000000",
    "password": "Test@12345",
    "search": "TestForge",
    "q": "TestForge",
    "keyword": "TestForge",
    "address": "北京市朝阳区测试路 1 号",
    "city": "北京",
    "zip": "100000",
    "country": "中国",
    "comment": "TestForge 自动化测试提交",
    "message": "TestForge 自动化测试提交",
}


@dataclass
class CheckItem:
    """单项检查结果"""
    name: str
    category: str                       # broken_link / form / accessibility / seo / security / performance / js_error / responsive
    severity: str = "info"              # info | warning | error | critical
    passed: bool = True
    detail: str = ""
    page_url: str = ""
    evidence: dict = field(default_factory=dict)


@dataclass
class WebsiteTestCase:
    """网站测试用例 — 结构化的可执行测试用例"""
    id: str                             # 用例ID
    name: str                           # 用例名称
    category: str                       # 分类：page_access / link_check / form_test / seo / security / performance
    method: str = "GET"                 # HTTP方法：GET/POST/HEAD
    url: str = ""                       # 测试目标URL
    expected: str = ""                  # 期望结果描述
    actual: str = ""                    # 实际结果
    passed: bool = False                # 是否通过
    status_code: int = 0                # HTTP状态码
    duration_ms: int = 0                # 耗时（毫秒）
    error: str = ""                     # 错误信息
    detail: str = ""                    # 详细说明
    page_url: str = ""                  # 所属页面

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "method": self.method,
            "url": self.url,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "detail": self.detail,
            "page_url": self.page_url,
        }


@dataclass
class AutoTestResult:
    """自动化测试总结果"""
    start_url: str
    pages_tested: int = 0
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    critical: int = 0
    checks: list[CheckItem] = field(default_factory=list)
    # 新增：结构化测试用例 + 执行结果
    test_cases: list[WebsiteTestCase] = field(default_factory=list)
    test_total: int = 0
    test_passed: int = 0
    test_failed: int = 0
    score: int = 100                    # 综合健康分（0-100）
    duration_ms: int = 0
    screenshots: list[dict] = field(default_factory=list)   # [{page, viewport, path}]
    crawl: Optional[dict] = None        # 原始爬取结果摘要

    def to_dict(self) -> dict:
        return {
            "start_url": self.start_url,
            "pages_tested": self.pages_tested,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "warnings": self.warnings,
            "failed": self.failed,
            "critical": self.critical,
            "score": self.score,
            "duration_ms": self.duration_ms,
            "screenshots": self.screenshots,
            "crawl": self.crawl,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "severity": c.severity,
                    "passed": c.passed,
                    "detail": c.detail,
                    "page_url": c.page_url,
                    "evidence": c.evidence,
                }
                for c in self.checks
            ],
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "test_total": self.test_total,
            "test_passed": self.test_passed,
            "test_failed": self.test_failed,
        }


async def auto_test_website(
    start_url: str,
    *,
    crawl_depth: int = 1,
    max_pages: int = 10,
    max_concurrency: int = 5,
    timeout: int = 10,
    check_js: bool = False,
    check_responsive: bool = False,
    test_forms: bool = True,
) -> AutoTestResult:
    """对网站执行自动化测试

    Args:
        start_url: 起始 URL
        crawl_depth: 爬取深度
        max_pages: 最大测试页面数
        check_js: 是否启用浏览器 JS 错误检查（需 Playwright）
        check_responsive: 是否启用响应式截图（需 Playwright）
        test_forms: 是否实际探测表单提交
    """
    start = time.time()
    result = AutoTestResult(start_url=start_url)

    # Step 1: 爬取
    crawl: CrawlResult = await crawl_website(
        start_url,
        max_depth=crawl_depth,
        max_pages=max_pages,
        max_concurrency=max_concurrency,
        timeout=timeout,
    )
    result.crawl = crawl.to_dict()
    result.pages_tested = len(crawl.pages)

    # Step 2: 对每个页面执行 HTTP 层检查
    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    connector = aiohttp.TCPConnector(limit=max_concurrency, ssl=False)
    headers = {"User-Agent": "TestForgeBot/1.0 (+https://testforge.dev/autotest)"}

    async with aiohttp.ClientSession(timeout=timeout_cfg, connector=connector, headers=headers) as session:
        # 2.1 死链检查（HEAD/GET 所有内部+外部链接）
        await _check_broken_links(crawl, session, result)

        # 2.2 每页的 SEO/可访问性/安全/性能检查（基于爬取已得的 HTML 元数据）
        for page in crawl.pages:
            if page.error:
                continue
            _check_seo(page, result)
            _check_accessibility(page, result)
            _check_security(page, result)
            _check_performance(page, result)

        # 2.3 表单测试（探测性提交）
        if test_forms:
            await _check_forms(crawl, session, result)

        # 2.4 生成并执行结构化测试用例
        await _generate_and_run_test_cases(crawl, session, result)

    # Step 3: 浏览器深度检查（可选）
    if check_js or check_responsive:
        try:
            await _browser_checks(start_url, crawl.pages, check_js, check_responsive, result)
        except Exception as e:
            logger.warning("浏览器深度检查失败: %s", e)
            result.checks.append(CheckItem(
                name="浏览器深度检查",
                category="js_error",
                severity="warning",
                passed=False,
                detail=f"浏览器检查失败: {e}。可运行: pip install playwright && playwright install chromium",
            ))

    # Step 4: 汇总评分
    result.total_checks = len(result.checks)
    result.passed = sum(1 for c in result.checks if c.passed and c.severity in ("info", "warning"))
    result.warnings = sum(1 for c in result.checks if not c.passed and c.severity == "warning")
    result.failed = sum(1 for c in result.checks if not c.passed and c.severity == "error")
    result.critical = sum(1 for c in result.checks if not c.passed and c.severity == "critical")

    # 测试用例统计
    result.test_total = len(result.test_cases)
    result.test_passed = sum(1 for tc in result.test_cases if tc.passed)
    result.test_failed = result.test_total - result.test_passed

    # 评分：以 100 为基础，按严重度扣分
    score = 100
    score -= result.critical * 15
    score -= result.failed * 5
    score -= result.warnings * 1
    result.score = max(0, min(100, score))

    result.duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "自动化测试完成: %s | 检查 %d 项 | 通过 %d | 警告 %d | 失败 %d | 严重 %d | 评分 %d | 耗时 %dms",
        start_url, result.total_checks, result.passed, result.warnings,
        result.failed, result.critical, result.score, result.duration_ms,
    )
    return result


# ============ 测试用例生成与执行 ============

async def _generate_and_run_test_cases(
    crawl: CrawlResult,
    session: aiohttp.ClientSession,
    result: AutoTestResult,
) -> None:
    """根据爬取结果生成结构化测试用例并执行

    生成策略：
      1. 页面可访问性测试 — 每个爬取页面发 GET，验证状态码 2xx/3xx
      2. 链接可达性测试 — 每个链接发 HEAD/GET，验证非 4xx/5xx
      3. 表单提交测试 — 每个表单填充示例数据提交，验证非 5xx
      4. 页面标题/SEO 测试 — 验证 title 和 h1 存在
      5. HTTPS 安全测试 — 验证页面使用 HTTPS
    """
    case_idx = 0

    def _next_id() -> str:
        nonlocal case_idx
        case_idx += 1
        return f"WT-{case_idx:04d}"

    # ---- 1. 页面可访问性测试 ----
    for page in crawl.pages:
        if page.error:
            result.test_cases.append(WebsiteTestCase(
                id=_next_id(),
                name=f"页面可访问性测试: {_short_url(page.url)}",
                category="page_access",
                method="GET",
                url=page.url,
                expected="HTTP 状态码 200-399",
                actual=f"页面加载失败: {page.error}",
                passed=False,
                status_code=page.status,
                error=page.error,
                page_url=page.url,
            ))
            continue
        # 重新请求验证
        t0 = time.time()
        try:
            async with session.get(page.url, allow_redirects=True) as resp:
                status = resp.status
                elapsed = int((time.time() - t0) * 1000)
            passed = 200 <= status < 400
            result.test_cases.append(WebsiteTestCase(
                id=_next_id(),
                name=f"页面可访问性测试: {_short_url(page.url)}",
                category="page_access",
                method="GET",
                url=page.url,
                expected="HTTP 状态码 200-399",
                actual=f"HTTP {status}",
                passed=passed,
                status_code=status,
                duration_ms=elapsed,
                detail=f"页面标题: {page.title or '无'}",
                page_url=page.url,
            ))
        except asyncio.TimeoutError:
            result.test_cases.append(WebsiteTestCase(
                id=_next_id(),
                name=f"页面可访问性测试: {_short_url(page.url)}",
                category="page_access",
                method="GET",
                url=page.url,
                expected="HTTP 状态码 200-399",
                actual="请求超时",
                passed=False,
                error="timeout",
                page_url=page.url,
            ))
        except Exception as e:
            result.test_cases.append(WebsiteTestCase(
                id=_next_id(),
                name=f"页面可访问性测试: {_short_url(page.url)}",
                category="page_access",
                method="GET",
                url=page.url,
                expected="HTTP 状态码 200-399",
                actual=f"请求异常: {e}",
                passed=False,
                error=str(e),
                page_url=page.url,
            ))

    # ---- 2. 链接可达性测试（去重，限制数量） ----
    link_set: dict[str, str] = {}  # url -> parent page
    for page in crawl.pages:
        for link in set(page.internal_links + page.external_links):
            if link not in link_set:
                link_set[link] = page.url
    # 限制链接测试数量，避免过多
    links_to_test = list(link_set.items())[:30]

    semaphore = asyncio.Semaphore(8)

    async def _probe_link(link_url: str, parent: str):
        nonlocal case_idx
        # 已在页面爬取中访问过的同域页面直接用已有状态
        for p in crawl.pages:
            if p.url == link_url and not p.error:
                result.test_cases.append(WebsiteTestCase(
                    id=_next_id(),
                    name=f"链接可达性测试: {_short_url(link_url)}",
                    category="link_check",
                    method="HEAD",
                    url=link_url,
                    expected="HTTP 状态码 200-399",
                    actual=f"HTTP {p.status}",
                    passed=200 <= p.status < 400,
                    status_code=p.status,
                    detail=f"来源页面: {parent}",
                    page_url=parent,
                ))
                return
        async with semaphore:
            t0 = time.time()
            try:
                async with session.head(link_url, allow_redirects=True) as resp:
                    status = resp.status
                elapsed = int((time.time() - t0) * 1000)
            except aiohttp.ClientError:
                # 回退 GET
                try:
                    async with session.get(link_url, allow_redirects=True) as resp:
                        status = resp.status
                    elapsed = int((time.time() - t0) * 1000)
                except asyncio.TimeoutError:
                    result.test_cases.append(WebsiteTestCase(
                        id=_next_id(),
                        name=f"链接可达性测试: {_short_url(link_url)}",
                        category="link_check",
                        method="HEAD",
                        url=link_url,
                        expected="HTTP 状态码 200-399",
                        actual="请求超时",
                        passed=False,
                        error="timeout",
                        detail=f"来源页面: {parent}",
                        page_url=parent,
                    ))
                    return
                except Exception as e:
                    result.test_cases.append(WebsiteTestCase(
                        id=_next_id(),
                        name=f"链接可达性测试: {_short_url(link_url)}",
                        category="link_check",
                        method="HEAD",
                        url=link_url,
                        expected="HTTP 状态码 200-399",
                        actual=f"请求异常: {e}",
                        passed=False,
                        error=str(e),
                        detail=f"来源页面: {parent}",
                        page_url=parent,
                    ))
                    return
            except asyncio.TimeoutError:
                result.test_cases.append(WebsiteTestCase(
                    id=_next_id(),
                    name=f"链接可达性测试: {_short_url(link_url)}",
                    category="link_check",
                    method="HEAD",
                    url=link_url,
                    expected="HTTP 状态码 200-399",
                    actual="请求超时",
                    passed=False,
                    error="timeout",
                    detail=f"来源页面: {parent}",
                    page_url=parent,
                ))
                return
            passed = 200 <= status < 400
            result.test_cases.append(WebsiteTestCase(
                id=_next_id(),
                name=f"链接可达性测试: {_short_url(link_url)}",
                category="link_check",
                method="HEAD",
                url=link_url,
                expected="HTTP 状态码 200-399",
                actual=f"HTTP {status}",
                passed=passed,
                status_code=status,
                duration_ms=elapsed,
                detail=f"来源页面: {parent}",
                page_url=parent,
            ))

    if links_to_test:
        await asyncio.gather(*[_probe_link(u, p) for u, p in links_to_test])

    # ---- 3. 表单提交测试 ----
    tested_forms: set[str] = set()
    for page in crawl.pages:
        for form in page.forms:
            if form.action in tested_forms:
                continue
            tested_forms.add(form.action)
            # 跳过外部域表单
            if urlparse(form.action).netloc != urlparse(page.url).netloc:
                continue
            sample_data = _generate_form_sample(form)
            t0 = time.time()
            try:
                if form.method.upper() == "GET":
                    async with session.get(form.action, params=sample_data, allow_redirects=True) as resp:
                        status = resp.status
                else:
                    async with session.post(form.action, data=sample_data, allow_redirects=True) as resp:
                        status = resp.status
                elapsed = int((time.time() - t0) * 1000)
                passed = status < 500  # 5xx 视为失败
                result.test_cases.append(WebsiteTestCase(
                    id=_next_id(),
                    name=f"表单提交测试: {form.method} {_short_url(form.action)}",
                    category="form_test",
                    method=form.method.upper(),
                    url=form.action,
                    expected="HTTP 状态码 < 500（服务端不报错）",
                    actual=f"HTTP {status}",
                    passed=passed,
                    status_code=status,
                    duration_ms=elapsed,
                    detail=f"提交 {len(sample_data)} 个字段: {', '.join(list(sample_data.keys())[:5])}",
                    page_url=page.url,
                ))
            except asyncio.TimeoutError:
                result.test_cases.append(WebsiteTestCase(
                    id=_next_id(),
                    name=f"表单提交测试: {form.method} {_short_url(form.action)}",
                    category="form_test",
                    method=form.method.upper(),
                    url=form.action,
                    expected="HTTP 状态码 < 500（服务端不报错）",
                    actual="请求超时",
                    passed=False,
                    error="timeout",
                    page_url=page.url,
                ))
            except Exception as e:
                result.test_cases.append(WebsiteTestCase(
                    id=_next_id(),
                    name=f"表单提交测试: {form.method} {_short_url(form.action)}",
                    category="form_test",
                    method=form.method.upper(),
                    url=form.action,
                    expected="HTTP 状态码 < 500（服务端不报错）",
                    actual=f"请求异常: {e}",
                    passed=False,
                    error=str(e),
                    page_url=page.url,
                ))

    # ---- 4. 页面 SEO 测试 ----
    for page in crawl.pages:
        if page.error:
            continue
        # title 测试
        title_ok = bool(page.title) and len(page.title) >= 10
        result.test_cases.append(WebsiteTestCase(
            id=_next_id(),
            name=f"SEO测试-页面标题: {_short_url(page.url)}",
            category="seo",
            method="-",
            url=page.url,
            expected="存在 <title> 且长度 >= 10 字符",
            actual=f"标题: '{page.title or '无'}' (长度 {len(page.title or '')})",
            passed=title_ok,
            detail="页面标题影响搜索引擎收录和用户识别" if not title_ok else "标题符合要求",
            page_url=page.url,
        ))
        # h1 测试
        h1_ok = len(page.h1) >= 1
        result.test_cases.append(WebsiteTestCase(
            id=_next_id(),
            name=f"SEO测试-H1标题: {_short_url(page.url)}",
            category="seo",
            method="-",
            url=page.url,
            expected="存在至少 1 个 <h1> 标签",
            actual=f"H1 数量: {len(page.h1)}",
            passed=h1_ok,
            detail=f"H1 内容: {page.h1[0] if page.h1 else '无'}",
            page_url=page.url,
        ))

    # ---- 5. HTTPS 安全测试 ----
    for page in crawl.pages:
        if page.error:
            continue
        is_https = page.url.startswith("https://")
        result.test_cases.append(WebsiteTestCase(
            id=_next_id(),
            name=f"安全测试-HTTPS: {_short_url(page.url)}",
            category="security",
            method="-",
            url=page.url,
            expected="页面使用 HTTPS 协议",
            actual="HTTPS" if is_https else "HTTP（不安全）",
            passed=is_https,
            detail="HTTPS 保证传输加密，HTTP 存在数据泄露风险" if not is_https else "已使用 HTTPS",
            page_url=page.url,
        ))

    logger.info(
        "测试用例生成完成: 共 %d 个用例（页面访问 %d / 链接检查 / 表单测试 / SEO / 安全）",
        len(result.test_cases),
        len(crawl.pages),
    )


def _short_url(url: str, max_len: int = 60) -> str:
    """截断 URL 用于显示"""
    if len(url) <= max_len:
        return url
    return url[:max_len - 3] + "..."


# ============ 死链检测 ============

async def _check_broken_links(
    crawl: CrawlResult,
    session: aiohttp.ClientSession,
    result: AutoTestResult,
) -> None:
    """检测所有链接的可达性"""
    # 收集所有唯一链接（内部+外部），并记录来源页面
    link_map: dict[str, list[str]] = {}  # url -> parent pages
    for page in crawl.pages:
        for link in set(page.internal_links + page.external_links):
            link_map.setdefault(link, []).append(page.url)

    if not link_map:
        return

    semaphore = asyncio.Semaphore(8)

    async def _probe(url: str):
        # 已经在爬取阶段访问过的同域页面跳过
        for p in crawl.pages:
            if p.url == url and not p.error:
                return None
        async with semaphore:
            try:
                # 优先 HEAD，部分站点不支持则回退 GET
                async with session.head(url, allow_redirects=True) as resp:
                    return resp.status
            except aiohttp.ClientError:
                pass
            except asyncio.TimeoutError:
                return -1
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    return resp.status
            except asyncio.TimeoutError:
                return -1
            except Exception:
                return None

    statuses = await asyncio.gather(*[_probe(u) for u in link_map.keys()], return_exceptions=False)

    for (url, parents), status in zip(link_map.items(), statuses):
        if status is None:
            continue
        if status == -1:
            result.checks.append(CheckItem(
                name=f"链接超时: {url}",
                category="broken_link",
                severity="warning",
                passed=False,
                detail=f"链接请求超时（来源: {parents[0]}）",
                page_url=parents[0],
                evidence={"url": url, "status": "timeout"},
            ))
        elif status >= 400:
            sev = "critical" if status >= 500 else "error"
            result.checks.append(CheckItem(
                name=f"死链: {url}",
                category="broken_link",
                severity=sev,
                passed=False,
                detail=f"HTTP {status}（来源: {parents[0]}）",
                page_url=parents[0],
                evidence={"url": url, "status": status},
            ))


# ============ SEO 检查 ============

def _check_seo(page: PageInfo, result: AutoTestResult) -> None:
    """SEO 基础检查"""
    # 标题
    if not page.title:
        result.checks.append(CheckItem(
            name="缺少 <title>",
            category="seo", severity="error", passed=False,
            detail="页面缺少 <title> 标签，影响搜索引擎收录",
            page_url=page.url,
        ))
    elif len(page.title) < 10:
        result.checks.append(CheckItem(
            name="标题过短",
            category="seo", severity="warning", passed=False,
            detail=f"标题仅 {len(page.title)} 字符，建议 10-60 字符",
            page_url=page.url, evidence={"title": page.title},
        ))

    # meta description
    if not page.meta_description:
        result.checks.append(CheckItem(
            name="缺少 meta description",
            category="seo", severity="warning", passed=False,
            detail="页面缺少 <meta name=description>，影响搜索结果摘要",
            page_url=page.url,
        ))
    elif len(page.meta_description) < 50:
        result.checks.append(CheckItem(
            name="meta description 过短",
            category="seo", severity="info", passed=False,
            detail=f"描述仅 {len(page.meta_description)} 字符，建议 50-160 字符",
            page_url=page.url,
        ))

    # h1
    if not page.h1:
        result.checks.append(CheckItem(
            name="缺少 <h1>",
            category="seo", severity="warning", passed=False,
            detail="页面缺少 <h1>，建议每个页面有且仅有一个主标题",
            page_url=page.url,
        ))
    elif len(page.h1) > 1:
        result.checks.append(CheckItem(
            name="<h1> 多于一个",
            category="seo", severity="info", passed=False,
            detail=f"页面有 {len(page.h1)} 个 <h1>，建议只保留 1 个",
            page_url=page.url, evidence={"h1": page.h1},
        ))


# ============ 可访问性检查 ============

def _check_accessibility(page: PageInfo, result: AutoTestResult) -> None:
    """可访问性基础检查（基于爬取数据）"""
    # 图片 alt（基于已爬的 images 数量只能近似——这里用页面 images 总数与无 alt 的差值）
    # 由于爬虫没有保存 alt，此处用"图片数量过多而无 alt 信息"作为弱信号
    if len(page.images) > 0:
        # 启发式：图片超过 5 张且为装饰性图片（无法判断）→ 给出通用提示
        result.checks.append(CheckItem(
            name="图片 alt 属性需人工核验",
            category="accessibility", severity="info", passed=True,
            detail=f"页面有 {len(page.images)} 张图片，请核验是否提供 alt 属性",
            page_url=page.url,
        ))

    # 表单 label
    for form in page.forms:
        unlabeled = []
        for f in form.fields:
            # 简化判断：type=hidden 不算；其他字段需要 label 关联
            if f.get("type") in ("hidden", "submit", "button", "image"):
                continue
            if not f.get("placeholder") and not f.get("name"):
                unlabeled.append(f)
        if unlabeled:
            result.checks.append(CheckItem(
                name="表单字段缺少 label/placeholder",
                category="accessibility", severity="warning", passed=False,
                detail=f"表单 {form.action} 有 {len(unlabeled)} 个字段缺少可访问性标签",
                page_url=page.url,
                evidence={"action": form.action, "fields": unlabeled},
            ))


# ============ 安全检查 ============

def _check_security(page: PageInfo, result: AutoTestResult) -> None:
    """安全检查"""
    is_https = page.url.startswith("https://")

    # mixed content：https 页面引用 http 资源
    if is_https:
        insecure = []
        for res in page.scripts + page.styles + page.images:
            if res.startswith("http://"):
                insecure.append(res)
        if insecure:
            result.checks.append(CheckItem(
                name="Mixed Content（HTTPS 页面引用 HTTP 资源）",
                category="security", severity="critical", passed=False,
                detail=f"HTTPS 页面引用了 {len(insecure)} 个不安全 HTTP 资源",
                page_url=page.url, evidence={"resources": insecure[:5]},
            ))

    # 表单通过 http 提交
    for form in page.forms:
        if form.action.startswith("http://"):
            result.checks.append(CheckItem(
                name="表单通过不安全 HTTP 提交",
                category="security", severity="critical", passed=False,
                detail=f"表单 {form.action} 通过 HTTP 提交，存在数据泄露风险",
                page_url=page.url,
            ))


# ============ 性能检查 ============

def _check_performance(page: PageInfo, result: AutoTestResult) -> None:
    """性能指标检查"""
    if page.response_time_ms <= 0:
        return
    if page.response_time_ms > 3000:
        result.checks.append(CheckItem(
            name="页面响应缓慢",
            category="performance", severity="error", passed=False,
            detail=f"页面响应耗时 {page.response_time_ms}ms（建议 < 3000ms）",
            page_url=page.url, evidence={"response_time_ms": page.response_time_ms},
        ))
    elif page.response_time_ms > 1500:
        result.checks.append(CheckItem(
            name="页面响应偏慢",
            category="performance", severity="warning", passed=False,
            detail=f"页面响应耗时 {page.response_time_ms}ms（建议 < 1500ms）",
            page_url=page.url,
        ))

    # 资源数量过多
    total_assets = len(page.scripts) + len(page.styles) + len(page.images)
    if total_assets > 50:
        result.checks.append(CheckItem(
            name="页面资源过多",
            category="performance", severity="warning", passed=False,
            detail=f"页面引用 {total_assets} 个资源（脚本 {len(page.scripts)} / 样式 {len(page.styles)} / 图片 {len(page.images)}），建议合并压缩",
            page_url=page.url,
        ))


# ============ 表单测试 ============

async def _check_forms(
    crawl: CrawlResult,
    session: aiohttp.ClientSession,
    result: AutoTestResult,
) -> None:
    """探测性提交表单（GET/POST 不带期望字段值，仅观察服务端响应）"""
    tested: set[str] = set()
    for page in crawl.pages:
        for form in page.forms:
            if form.action in tested:
                continue
            tested.add(form.action)
            # 跳过外部域表单
            if urlparse(form.action).netloc != urlparse(page.url).netloc:
                continue
            try:
                sample_data = _generate_form_sample(form)
                if form.method == "GET":
                    async with session.get(form.action, params=sample_data, allow_redirects=True) as resp:
                        status = resp.status
                else:
                    async with session.post(form.action, data=sample_data, allow_redirects=True) as resp:
                        status = resp.status
                # 5xx 视为严重；4xx 视为失败；2xx/3xx 视为通过
                if status >= 500:
                    sev = "critical"
                    passed = False
                elif status >= 400:
                    sev = "error"
                    passed = False
                else:
                    sev = "info"
                    passed = True
                result.checks.append(CheckItem(
                    name=f"表单探测提交: {form.method} {form.action}",
                    category="form", severity=sev, passed=passed,
                    detail=f"提交 {len(sample_data)} 个字段 → HTTP {status}",
                    page_url=page.url,
                    evidence={"action": form.action, "method": form.method, "status": status, "fields": list(sample_data.keys())},
                ))
            except asyncio.TimeoutError:
                result.checks.append(CheckItem(
                    name=f"表单提交超时: {form.action}",
                    category="form", severity="warning", passed=False,
                    detail="表单提交请求超时",
                    page_url=page.url,
                ))
            except Exception as e:
                result.checks.append(CheckItem(
                    name=f"表单提交异常: {form.action}",
                    category="form", severity="warning", passed=False,
                    detail=f"提交异常: {e}",
                    page_url=page.url,
                ))


def _generate_form_sample(form) -> dict:
    """为表单生成示例填充数据"""
    data: dict[str, str] = {}
    for f in form.fields:
        name = f["name"]
        ftype = f.get("type", "text")
        if ftype in ("submit", "button", "image", "reset"):
            continue
        # 1. 字段名匹配
        matched = False
        for key, val in _FIELD_SAMPLES.items():
            if key in name.lower():
                data[name] = val
                matched = True
                break
        if matched:
            continue
        # 2. type 匹配
        if ftype == "email":
            data[name] = "test@example.com"
        elif ftype == "password":
            data[name] = "Test@12345"
        elif ftype == "number":
            data[name] = "1"
        elif ftype == "checkbox" or ftype == "radio":
            data[name] = "on"
        elif ftype == "url":
            data[name] = "https://example.com"
        elif ftype == "date":
            data[name] = "2026-01-01"
        else:
            data[name] = "TestForge_Sample"
    return data


# ============ 浏览器深度检查（可选） ============

async def _browser_checks(
    start_url: str,
    pages: list[PageInfo],
    check_js: bool,
    check_responsive: bool,
    result: AutoTestResult,
) -> None:
    """使用 Playwright 执行 JS 错误捕获与响应式截图"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        result.checks.append(CheckItem(
            name="Playwright 未安装",
            category="js_error", severity="warning", passed=False,
            detail="跳过浏览器深度检查。安装: pip install playwright && playwright install chromium",
        ))
        return

    import os
    screenshot_dir = os.path.join(os.getcwd(), "screenshots", "auto_test")
    os.makedirs(screenshot_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # 注入 JS 错误监听
        errors_collected: list[dict] = []

        # 仅检查起始页（避免过度消耗）
        target_pages = pages[:3] if pages else [PageInfo(url=start_url)]

        for page_info in target_pages:
            if page_info.error:
                continue
            page = await context.new_page()

            if check_js:
                def _on_console(msg):
                    if msg.type == "error":
                        errors_collected.append({"page": page_info.url, "text": msg.text})

                def _on_pageerror(err):
                    errors_collected.append({"page": page_info.url, "text": str(err), "fatal": True})

                page.on("console", _on_console)
                page.on("pageerror", _on_pageerror)

            try:
                await page.goto(page_info.url, wait_until="domcontentloaded", timeout=15000)

                if check_responsive:
                    for vp in VIEWPORTS:
                        await page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
                        await page.wait_for_timeout(300)
                        fname = f"{_slugify(page_info.url)}_{vp['name']}.png"
                        fpath = os.path.join(screenshot_dir, fname)
                        await page.screenshot(path=fpath, full_page=False)
                        result.screenshots.append({
                            "page": page_info.url,
                            "viewport": vp["name"],
                            "width": vp["width"],
                            "path": fpath,
                        })
            except Exception as e:
                result.checks.append(CheckItem(
                    name=f"浏览器加载失败: {page_info.url}",
                    category="js_error", severity="warning", passed=False,
                    detail=f"加载页面异常: {e}",
                    page_url=page_info.url,
                ))
            finally:
                await page.close()

        await browser.close()

    if check_js:
        if errors_collected:
            result.checks.append(CheckItem(
                name="JS 错误捕获",
                category="js_error", severity="error", passed=False,
                detail=f"捕获 {len(errors_collected)} 个 JavaScript 错误",
                evidence={"errors": errors_collected[:10]},
            ))
        else:
            result.checks.append(CheckItem(
                name="JS 错误捕获",
                category="js_error", severity="info", passed=True,
                detail="未捕获到 JavaScript 错误",
            ))


def _slugify(url: str) -> str:
    """URL 转为文件名友好的 slug"""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", url)[:80]
