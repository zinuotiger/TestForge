"""网站测试 API — OpenAPI 扫描 + 网页爬虫 + 自动化测试"""

import logging
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from backend.generator.openapi_parser import parse_openapi_url, spec_to_dict
from backend.generator.api_test_generator import generate_api_tests
from backend.executors.http_executor import execute_api_tests
from backend.safety.auth import get_current_user
from backend.config import settings
from backend.reporter.pdf_generator import generate_test_report_pdf
from backend.safety.notifier import send_test_report_email, is_email_configured
from backend.core.web_crawler import crawl_website
from backend.core.web_auto_tester import auto_test_website

logger = logging.getLogger("testforge")

router = APIRouter()


class ScanRequest(BaseModel):
    """网站扫描请求"""
    url: str                          # OpenAPI 文档 URL 或网站 URL
    execute: bool = True              # 是否自动执行生成的测试
    base_url: str = ""                # API base URL（覆盖文档中的）


class ScanResult(BaseModel):
    """扫描结果"""
    status: str                       # success | error
    api_title: str = ""
    api_version: str = ""
    endpoint_count: int = 0
    test_count: int = 0
    saved_count: int = 0              # 持久化保存数
    execution: dict = {}             # 执行结果
    error: str = ""


@router.post("/scan", response_model=ScanResult)
async def scan_website(req: ScanRequest, user: str = Depends(get_current_user)):
    """扫描网站 API → 自动生成测试 → 执行

    流程:
    1. 获取并解析 OpenAPI/Swagger 文档
    2. 为每个端点生成测试用例（正常/边界/404）
    3. （可选）用 aiohttp 真实执行所有测试
    4. 返回完整结果
    """
    try:
        # 1. 解析 OpenAPI
        logger.info("开始解析 OpenAPI 文档: %s", req.url)
        spec = await parse_openapi_url(req.url)
        spec_dict = spec_to_dict(spec)
        logger.info("解析完成: %s, %d 个端点", spec.title, len(spec.endpoints))

        # 2. 生成测试用例
        test_cases = generate_api_tests(spec, req.base_url)
        logger.info("生成 %d 个测试用例", len(test_cases))

        # 持久化：保存到数据库
        from backend.models.store import save_test
        saved_count = 0
        for tc in test_cases:
            try:
                await save_test(tc)
                saved_count += 1
            except Exception as e:
                logger.warning("保存测试用例失败: %s", e)
        logger.info("已保存 %d/%d 个测试用例到数据库", saved_count, len(test_cases))

        # RAG：加入向量库
        from backend.core.rag import vector_store
        cases_data = [tc.model_dump() for tc in test_cases]
        vector_store.add_batch(cases_data)

        # 3. 执行测试
        execution_result = {}
        if req.execute and spec.endpoints:
            base = req.base_url or spec.base_url
            execution_result = await execute_api_tests(cases_data, base)

        return ScanResult(
            status="success",
            api_title=spec.title,
            api_version=spec.version,
            endpoint_count=len(spec.endpoints),
            test_count=len(test_cases),
            saved_count=saved_count,
            execution={
                "total": execution_result.get("total", 0),
                "passed": execution_result.get("passed", 0),
                "failed": execution_result.get("failed", 0),
                "duration_ms": execution_result.get("duration_ms", 0),
                "results": execution_result.get("results", [])[:50],  # 限制返回数量
            },
        )

    except Exception as e:
        logger.error("网站扫描失败: %s", e)
        return ScanResult(status="error", error=str(e))


class ParseRequest(BaseModel):
    """OpenAPI 解析请求"""
    url: str
    base_url: str = ""


@router.post("/parse")
async def parse_api_spec(req: ParseRequest, user: str = Depends(get_current_user)):
    """仅解析 OpenAPI 文档，不执行测试"""
    try:
        spec = await parse_openapi_url(req.url)
        return {
            "status": "success",
            "spec": spec_to_dict(spec),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


class ExportRequest(BaseModel):
    """导出 PDF 请求"""
    url: str
    base_url: str = ""


@router.post("/export")
async def export_pdf(req: ExportRequest, user: str = Depends(get_current_user)):
    """扫描网站 → 执行测试 → 导出 PDF 报告"""
    try:
        spec = await parse_openapi_url(req.url)
        test_cases = generate_api_tests(spec, req.base_url)
        cases_data = [tc.model_dump() for tc in test_cases]
        base = req.base_url or spec.base_url
        execution = await execute_api_tests(cases_data, base)

        pdf_bytes = generate_test_report_pdf(
            api_title=spec.title,
            api_version=spec.version,
            endpoint_count=len(spec.endpoints),
            test_count=len(test_cases),
            execution=execution,
            scan_url=req.url,
        )

        filename = f"testforge_report_{spec.title.replace(' ', '_')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error("PDF 导出失败: %s", e)
        return {"status": "error", "error": str(e)}


class EmailRequest(BaseModel):
    """邮件发送请求"""
    url: str
    to_emails: list[str]
    base_url: str = ""


@router.post("/email")
async def send_email_report(req: EmailRequest, user: str = Depends(get_current_user)):
    """扫描网站 → 执行测试 → 生成 PDF → 发送邮件"""
    try:
        if not is_email_configured():
            return {"success": False, "error": "SMTP 未配置，请在 .env 中设置 TESTFORGE_SMTP_* 环境变量"}

        spec = await parse_openapi_url(req.url)
        test_cases = generate_api_tests(spec, req.base_url)
        cases_data = [tc.model_dump() for tc in test_cases]
        base = req.base_url or spec.base_url
        execution = await execute_api_tests(cases_data, base)

        pdf_bytes = generate_test_report_pdf(
            api_title=spec.title,
            api_version=spec.version,
            endpoint_count=len(spec.endpoints),
            test_count=len(test_cases),
            execution=execution,
            scan_url=req.url,
        )

        result = send_test_report_email(
            to_emails=req.to_emails,
            api_title=spec.title,
            execution=execution,
            pdf_bytes=pdf_bytes,
            scan_url=req.url,
        )
        return result
    except Exception as e:
        logger.error("邮件发送失败: %s", e)
        return {"success": False, "error": str(e)}


@router.get("/email/status")
async def email_status():
    """检查邮件配置状态"""
    return {"configured": is_email_configured()}


# ============================================================
# 网页爬虫 & 自动化测试
# ============================================================

class CrawlRequest(BaseModel):
    """网站爬虫请求"""
    url: str                              # 起始 URL
    max_depth: int = 2                    # 最大爬取深度
    max_pages: int = 30                   # 最大爬取页面数
    max_concurrency: int = 5              # 并发数
    timeout: int = 10                     # 单页超时秒数
    respect_robots: bool = True           # 是否尊重 robots.txt
    use_browser: bool = False             # 强制浏览器渲染（SPA网站设为True）


@router.post("/crawl")
async def crawl_site(req: CrawlRequest, user: str = Depends(get_current_user)):
    """爬取网站：BFS 异步抓取，提取页面/链接/表单/资源

    返回:
      - pages: 每个页面的元信息（标题/状态/响应时间/链接数/表单/资源）
      - broken_links: 死链列表
      - forms: 所有表单及字段
      - 统计信息
    """
    try:
        result = await crawl_website(
            req.url,
            max_depth=req.max_depth,
            max_pages=req.max_pages,
            max_concurrency=req.max_concurrency,
            timeout=req.timeout,
            respect_robots=req.respect_robots,
            use_browser=req.use_browser,
        )
        return result.to_dict()
    except Exception as e:
        logger.error("网站爬取失败: %s", e)
        return {"start_url": req.url, "error": str(e), "pages": [], "visited_count": 0}


class AutoTestRequest(BaseModel):
    """网页自动化测试请求"""
    url: str                              # 起始 URL
    crawl_depth: int = 2                  # 爬取深度（自动化测试通常 0-2 即可）
    max_pages: int = 10                   # 最大测试页面数
    max_concurrency: int = 5              # 并发数
    timeout: int = 10                     # 单页超时秒数
    check_js: bool = False                # 是否启用浏览器 JS 错误检查（需 Playwright）
    check_responsive: bool = False        # 是否启用响应式截图（需 Playwright）
    test_forms: bool = True               # 是否探测表单提交


@router.post("/auto-test")
async def auto_test_site(req: AutoTestRequest, user: str = Depends(get_current_user)):
    """对网站执行自动化测试

    自动完成以下检查（无需写代码）：
      1. 死链检测（HEAD/GET 探测所有链接）
      2. 表单可提交性（自动填充示例数据并探测响应码）
      3. 可访问性检查（图片 alt / 表单 label）
      4. SEO 检查（title / meta description / h1）
      5. 安全检查（mixed content / HTTP 表单提交）
      6. 性能检查（响应时间 / 资源数量）
      7. JS 错误捕获（可选，需 Playwright）
      8. 响应式截图（可选，需 Playwright）

    返回:
      - score: 综合健康分（0-100）
      - checks: 全部检查项明细
      - crawl: 爬取摘要
      - screenshots: 响应式截图路径（如启用）
    """
    try:
        result = await auto_test_website(
            req.url,
            crawl_depth=req.crawl_depth,
            max_pages=req.max_pages,
            max_concurrency=req.max_concurrency,
            timeout=req.timeout,
            check_js=req.check_js,
            check_responsive=req.check_responsive,
            test_forms=req.test_forms,
        )
        return result.to_dict()
    except Exception as e:
        logger.error("自动化测试失败: %s", e)
        return {
            "start_url": req.url,
            "error": str(e),
            "pages_tested": 0,
            "total_checks": 0,
            "passed": 0,
            "warnings": 0,
            "failed": 0,
            "critical": 0,
            "score": 0,
            "checks": [],
        }


# ============================================================
# 综合网站测试 — 功能/压力/边界/回归 + 功能分析 + 报告发送
# ============================================================

from backend.core.website_test_engine import run_comprehensive_test


class ComprehensiveTestRequest(BaseModel):
    """综合测试请求"""
    url: str                                    # 目标网站URL
    run_functional: bool = True                 # 功能测试
    run_stress: bool = True                     # 压力测试
    run_boundary: bool = True                   # 边界测试
    run_regression: bool = True                 # 回归测试
    run_feature_analysis: bool = True           # 功能分析
    crawl_depth: int = 2                        # 爬取深度
    max_pages: int = 10                         # 最大页面数
    stress_concurrency: int = 10                # 压力测试并发数
    stress_total: int = 50                      # 压力测试总请求数
    timeout: int = 10                           # 超时秒数


@router.post("/comprehensive-test")
async def comprehensive_test(req: ComprehensiveTestRequest, user: str = Depends(get_current_user)):
    """综合网站测试 — 一键执行功能/压力/边界/回归测试 + 功能分析

    返回各类测试的完整结果和综合评分。
    """
    try:
        result = await run_comprehensive_test(
            req.url,
            run_functional=req.run_functional,
            run_stress=req.run_stress,
            run_boundary=req.run_boundary,
            run_regression=req.run_regression,
            run_feature_analysis=req.run_feature_analysis,
            crawl_depth=req.crawl_depth,
            max_pages=req.max_pages,
            stress_concurrency=req.stress_concurrency,
            stress_total=req.stress_total,
            timeout=req.timeout,
        )
        return result.to_dict()
    except Exception as e:
        logger.error("综合测试失败: %s", e)
        return {"start_url": req.url, "error": str(e), "summary": {}}


class SendReportRequest(BaseModel):
    """发送测试报告邮件请求"""
    url: str                                    # 测试的网站URL
    to_emails: list[str]                        # 收件人列表
    test_result: dict = {}                      # 测试结果数据（可选，不传则重新测试）


@router.post("/send-report")
async def send_test_report(req: SendReportRequest, user: str = Depends(get_current_user)):
    """发送网站测试报告邮件

    将综合测试结果生成HTML邮件并发送到指定邮箱。
    """
    try:
        if not is_email_configured():
            return {"success": False, "error": "SMTP 未配置，请在 .env 中设置 TESTFORGE_SMTP_* 环境变量"}

        # 如果没有传入测试结果，重新执行测试
        test_data = req.test_result
        if not test_data:
            result = await run_comprehensive_test(req.url)
            test_data = result.to_dict()

        # 生成HTML邮件内容
        html_content = _generate_report_html(req.url, test_data)

        # 发送邮件（复用notifier的SMTP逻辑）
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        msg["From"] = settings.smtp_user
        msg["To"] = ", ".join(req.to_emails)
        msg["Subject"] = f"TestForge 网站测试报告 - {req.url}"
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        port = settings.smtp_port
        if settings.smtp_use_tls:
            server = smtplib.SMTP_SSL(settings.smtp_host, port, timeout=30)
        else:
            server = smtplib.SMTP(settings.smtp_host, port, timeout=30)
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, req.to_emails, msg.as_string())
        server.quit()

        return {"success": True, "message": f"报告已发送至 {', '.join(req.to_emails)}"}
    except Exception as e:
        logger.error("发送测试报告失败: %s", e)
        return {"success": False, "error": str(e)}


def _generate_report_html(url: str, data: dict) -> str:
    """生成HTML格式的测试报告"""
    summary = data.get("summary", {})
    score = summary.get("overall_score", 0)
    score_color = "#22c55e" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"

    # 功能测试部分
    functional = data.get("functional") or {}
    func_score = functional.get("score", "N/A")
    func_total = functional.get("test_total", 0)
    func_passed = functional.get("test_passed", 0)
    func_failed = functional.get("test_failed", 0)

    # 压力测试部分
    stress = data.get("stress") or {}
    stress_qps = stress.get("qps", "N/A")
    stress_p95 = stress.get("p95", "N/A")
    stress_err = stress.get("error_rate", 0)

    # 边界测试部分
    boundary = data.get("boundary") or {}
    bnd_total = boundary.get("total", 0)
    bnd_passed = boundary.get("passed", 0)
    bnd_rate = boundary.get("pass_rate", 0)

    # 回归测试部分
    regression = data.get("regression") or {}
    reg_changes = regression.get("change_count", 0)

    # 功能分析部分
    features = data.get("features") or []
    features_html = ""
    for f in features:
        status_icon = {"detected": "✅", "missing": "❌", "warning": "⚠️"}.get(f.get("status"), "•")
        features_html += f"<li>{status_icon} <b>{f.get('name')}</b>: {f.get('description')}</li>"

    # 测试用例明细
    test_cases = functional.get("test_cases") or []
    cases_html = ""
    for tc in test_cases[:50]:  # 最多展示50条
        icon = "✅" if tc.get("passed") else "❌"
        cases_html += f"<tr><td>{icon}</td><td>{tc.get('id','')}</td><td>{tc.get('name','')}</td><td>{tc.get('method','')}</td><td>{tc.get('status_code','')}</td><td>{tc.get('duration_ms','')}ms</td><td>{tc.get('actual','')}</td></tr>"

    return f"""
    <html><body style="font-family: 'Microsoft YaHei', Arial, sans-serif; background:#f1f5f9; padding:20px;">
    <div style="max-width:800px; margin:0 auto; background:#fff; border-radius:12px; padding:30px;">

    <h1 style="color:#1e293b; border-bottom:3px solid #3b82f6; padding-bottom:10px;">
      TestForge 网站测试报告
    </h1>

    <p style="color:#64748b;">测试目标: <b style="color:#3b82f6;">{url}</b><br/>
    测试时间: {summary.get('duration_ms', 0)}ms | 测试页面: {summary.get('pages_tested', 0)} 页</p>

    <div style="background:{score_color}; color:#fff; padding:20px; border-radius:8px; text-align:center; margin:20px 0;">
      <div style="font-size:1.2rem;">综合评分</div>
      <div style="font-size:3rem; font-weight:bold;">{score}</div>
    </div>

    <h2 style="color:#1e293b;">📊 测试结果汇总</h2>
    <table style="width:100%; border-collapse:collapse; margin:10px 0;">
      <tr style="background:#f1f5f9;"><th style="padding:10px; text-align:left; border:1px solid #e2e8f0;">测试类型</th><th style="padding:10px; text-align:left; border:1px solid #e2e8f0;">结果</th></tr>
      <tr><td style="padding:8px; border:1px solid #e2e8f0;">功能测试</td><td style="padding:8px; border:1px solid #e2e8f0;">健康分 {func_score} | {func_passed}/{func_total} 用例通过</td></tr>
      <tr><td style="padding:8px; border:1px solid #e2e8f0;">压力测试</td><td style="padding:8px; border:1px solid #e2e8f0;">QPS {stress_qps} | P95 {stress_p95}ms | 错误率 {stress_err*100:.1f}%</td></tr>
      <tr><td style="padding:8px; border:1px solid #e2e8f0;">边界测试</td><td style="padding:8px; border:1px solid #e2e8f0;">{bnd_passed}/{bnd_total} 通过 ({bnd_rate}%)</td></tr>
      <tr><td style="padding:8px; border:1px solid #e2e8f0;">回归测试</td><td style="padding:8px; border:1px solid #e2e8f0;">检测到 {reg_changes} 项变化</td></tr>
    </table>

    <h2 style="color:#1e293b;">🔍 网站功能分析</h2>
    <ul style="color:#475569;">{features_html or '<li>未执行功能分析</li>'}</ul>

    <h2 style="color:#1e293b;">🧪 功能测试用例明细</h2>
    <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
      <tr style="background:#f1f5f9;"><th style="padding:6px; border:1px solid #e2e8f0;">结果</th><th style="padding:6px; border:1px solid #e2e8f0;">ID</th><th style="padding:6px; border:1px solid #e2e8f0;">名称</th><th style="padding:6px; border:1px solid #e2e8f0;">方法</th><th style="padding:6px; border:1px solid #e2e8f0;">状态码</th><th style="padding:6px; border:1px solid #e2e8f0;">耗时</th><th style="padding:6px; border:1px solid #e2e8f0;">实际结果</th></tr>
      {cases_html or '<tr><td colspan="7" style="padding:10px; text-align:center; color:#94a3b8;">无测试用例</td></tr>'}
    </table>

    <p style="color:#94a3b8; font-size:0.8rem; margin-top:20px; text-align:center;">
      本报告由 TestForge 自动生成 | Apache 2.0 © 2026 TestForge Team
    </p>
    </div>
    </body></html>
    """


# ============================================================
# AI Browser Agent — 自然语言驱动的浏览器测试
# ============================================================
#
# 与 _generate_report_html 区别：
# - _generate_report_html 末尾是 """（HTML 模板字符串结束）
# - 下面是新加的 Pydantic 模型 + FastAPI 路由
# ============================================================


class AgentTaskRequest(BaseModel):
    """AI Agent 自然语言任务请求"""
    task: str                                # 自然语言任务描述
    start_url: str = ""                      # 起始 URL（可选，LLM 可自行推断）
    max_steps: int = 10                      # ReAct 最大循环步数


class AgentStepRequest(BaseModel):
    """手动执行单个 Agent 步骤（用于调试/手动控制）"""
    action: str
    params: dict = {}


@router.post("/agent/run")
async def run_agent_task(req: AgentTaskRequest, user: str = Depends(get_current_user)):
    """运行 AI Agent：自然语言任务 → ReAct 循环 → 浏览器执行

    示例：
    {
        "task": "打开 example.com，验证页面有 'Example Domain' 标题",
        "start_url": "https://example.com",
        "max_steps": 8
    }
    """
    from backend.core.browser_agent import run_browser_agent

    # 浏览器状态检查
    from backend.executors.browser_executor import check_browser_status
    bs = await check_browser_status()
    if not bs.get("available"):
        return {
            "success": False,
            "error": f"浏览器不可用: {bs.get('status')} | {bs.get('hint', '')}",
            "task": req.task,
        }

    try:
        result = await run_browser_agent(
            task=req.task,
            start_url=req.start_url,
            max_steps=req.max_steps,
        )
        return {
            "success": True,
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.exception("Agent 任务执行失败")
        return {"success": False, "error": str(e), "task": req.task}


@router.get("/agent/browser-status")
async def agent_browser_status():
    """检查 Playwright/Chromium 是否就绪"""
    from backend.executors.browser_executor import check_browser_status
    return await check_browser_status()


@router.get("/agent/actions")
async def list_agent_actions():
    """列出 Agent 支持的所有动作及说明"""
    from backend.core.browser_agent import AGENT_ACTIONS
    descriptions = {
        "navigate":       "打开 URL",
        "click":          "点击元素（支持 CSS / 文本 / data-testid）",
        "input":          "在输入框填入文本",
        "select":         "下拉框选择",
        "hover":          "鼠标悬停",
        "scroll":         "滚动页面（up/down/top/bottom）",
        "wait":           "等待若干毫秒",
        "wait_for":       "等待元素出现",
        "press_key":      "键盘按键（Enter/Tab/Escape 等）",
        "screenshot":     "截屏",
        "extract":        "从页面提取信息（text/links/forms/title/url/all）",
        "assert":         "AI 语义断言",
        "switch_tab":     "切换标签页",
        "switch_frame":   "切换 iframe",
        "close_dialog":   "处理 alert/confirm 弹窗",
        "upload_file":    "文件上传",
        "drag":           "拖拽",
        "visual_click":   "👁️ 视觉定位点击（截图+AI找按钮，无需 selector）",
        "visual_find":    "👁️ 视觉定位（不点击）",
        "smart_locate":   "🧠 智能定位（selector→a11y→视觉 自动选最优）",
        "finish":         "任务结束，输出结论",
    }
    return {
        "actions": [
            {"name": a, "description": descriptions.get(a, "")}
            for a in AGENT_ACTIONS
        ],
        "total": len(AGENT_ACTIONS),
    }


# ============================================================
# 多 Agent 协作（分析-执行-验证）
# ============================================================

class MultiAgentRequest(BaseModel):
    """多 Agent 协作请求"""
    task: str
    start_url: str = ""
    max_steps: int = 12


@router.post("/agent/multi-run")
async def run_multi_agent_task(req: MultiAgentRequest, user: str = Depends(get_current_user)):
    """运行多 Agent 协作：Analyst 分析 → Executor 执行 → Verifier 验证

    返回完整协作报告：
    {
      "plan": {目标, 步骤, 风险, 难度},
      "execution": {成功, 通过步骤, 错误},
      "verification": {整体通过, 置信度, 问题, 建议},
      "agent_timeline": [...],
      "summary": "分析: 5 步计划, 难度 medium; 执行: 4/5; 验证: 通过"
    }
    """
    from backend.core.browser_multi_agent import run_browser_multi_agent

    # 浏览器环境检查
    from backend.executors.browser_executor import check_browser_status
    bs = await check_browser_status()
    if not bs.get("available"):
        return {
            "success": False,
            "error": f"浏览器不可用: {bs.get('status')}",
        }

    try:
        report = await run_browser_multi_agent(
            task=req.task,
            start_url=req.start_url,
            max_steps=req.max_steps,
        )
        return {"success": True, "report": report.to_dict()}
    except Exception as e:
        logger.exception("多 Agent 协作失败")
        return {"success": False, "error": str(e)}


# ============================================================
# Agent 经验记忆 API
# ============================================================

@router.get("/agent/memory/stats")
async def get_agent_memory_stats():
    """获取 Agent 经验记忆库统计"""
    from backend.core.agent_memory import agent_memory
    return {
        "success": True,
        "stats": agent_memory.stats(),
    }


@router.post("/agent/memory/search")
async def search_agent_memory(req: dict, user: str = Depends(get_current_user)):
    """检索 Agent 经验记忆"""
    from backend.core.agent_memory import agent_memory, ExperienceType
    from typing import Optional as Opt

    exp_type_str = req.get("type")
    exp_type = ExperienceType(exp_type_str) if exp_type_str else None
    domain = req.get("domain", "")
    key_contains = req.get("key_contains", "")
    limit = int(req.get("limit", 10))

    exps = agent_memory.search(
        exp_type=exp_type,
        domain=domain,
        key_contains=key_contains,
        limit=limit,
    )
    return {
        "success": True,
        "experiences": [e.to_dict() for e in exps],
        "count": len(exps),
    }


# ============================================================
# 视觉定位 API（独立使用）
# ============================================================

class VisualLocateRequest(BaseModel):
    url: str
    description: str           # 元素描述，如"登录按钮"


@router.post("/agent/visual-locate")
async def visual_locate_element(req: VisualLocateRequest, user: str = Depends(get_current_user)):
    """独立视觉定位端点：导航 + 截图 + 视觉模型定位

    用于调试或单独验证视觉能力
    """
    from playwright.async_api import async_playwright
    from backend.core.visual_locator import locate_element_by_visual

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(req.url, wait_until="domcontentloaded", timeout=15000)
                loc = await locate_element_by_visual(page, req.description)
                return {
                    "success": loc.get("found", False),
                    "location": loc,
                }
            finally:
                await browser.close()
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/browser/execute")
async def browser_execute(req: dict, user: str = Depends(get_current_user)):
    """通用浏览器脚本执行端点

    支持完整动作集（滚动/iframe/弹窗/多Tab/键盘/文件上传/AI断言等）
    req: {"steps": [...], "base_url": "...", "timeout": 30}
    """
    from backend.executors.browser_executor import execute_browser_test

    steps = req.get("steps", [])
    base_url = req.get("base_url", "")
    timeout = int(req.get("timeout", 30))
    return await execute_browser_test(steps, base_url, timeout)
