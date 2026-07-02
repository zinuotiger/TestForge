import { useState } from "react";

// ============ 类型定义 ============

interface AssertionResult {
  type: string;
  expected: number | number[] | string;
  actual: number | string | null;
  passed: boolean;
}

interface TestResult {
  passed: boolean;
  method: string;
  url: string;
  status: number;
  duration_ms: number;
  error: string;
  test_name: string;
  assertions: AssertionResult[];
}

interface ScanResult {
  status: string;
  api_title: string;
  api_version: string;
  endpoint_count: number;
  test_count: number;
  saved_count?: number;
  execution: {
    total: number;
    passed: number;
    failed: number;
    duration_ms: number;
    results: TestResult[];
  };
  error: string;
}

interface CrawledPage {
  url: string;
  status: number;
  title: string;
  content_type: string;
  response_time_ms: number;
  depth: number;
  internal_links_count: number;
  external_links_count: number;
  forms_count: number;
  images_count: number;
  scripts_count: number;
  h1: string[];
  meta_description: string;
  error: string;
}

interface BrokenLink {
  url: string;
  status: number;
  parent: string;
}

interface CrawlForm {
  action: string;
  method: string;
  field_count: number;
  fields: { name: string; type: string; required: boolean; placeholder: string }[];
  page_url: string;
}

interface CrawlResult {
  start_url: string;
  visited_count: number;
  failed_count: number;
  total_links: number;
  broken_links_count: number;
  duration_ms: number;
  max_depth_reached: number;
  error: string;
  pages: CrawledPage[];
  broken_links: BrokenLink[];
  forms: CrawlForm[];
}

interface CheckItem {
  name: string;
  category: string;
  severity: "info" | "warning" | "error" | "critical";
  passed: boolean;
  detail: string;
  page_url: string;
  evidence: Record<string, unknown>;
}

interface AutoTestResult {
  start_url: string;
  pages_tested: number;
  total_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  critical: number;
  score: number;
  duration_ms: number;
  screenshots: { page: string; viewport: string; width: number; path: string }[];
  crawl: CrawlResult | null;
  checks: CheckItem[];
  // 新增：结构化测试用例
  test_cases: TestCase[];
  test_total: number;
  test_passed: number;
  test_failed: number;
  error?: string;
}

interface TestCase {
  id: string;
  name: string;
  category: string;       // page_access / link_check / form_test / seo / security
  method: string;         // GET / POST / HEAD / -
  url: string;
  expected: string;
  actual: string;
  passed: boolean;
  status_code: number;
  duration_ms: number;
  error: string;
  detail: string;
  page_url: string;
}

type Mode = "agent" | "comprehensive" | "autotest" | "crawl" | "openapi";

// ============ 综合测试类型定义 ============

interface StressResult {
  url: string;
  concurrency: number;
  total_requests: number;
  success_count: number;
  failed_count: number;
  duration_ms: number;
  qps: number;
  p50: number;
  p95: number;
  p99: number;
  min_latency: number;
  max_latency: number;
  avg_latency: number;
  error_rate: number;
  status_codes: Record<string, number>;
}

interface BoundaryResult {
  test_cases: TestCase[];
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
  per_page?: Array<{ url: string; passed: number; total: number; failed: number; pass_rate: string }>;
}

interface RegressionResult {
  has_baseline: boolean;
  baseline_path: string;
  current_snapshot: Record<string, unknown>;
  changes: { type: string; description: string; severity: string }[];
  change_count: number;
  regression_count: number;
}

interface WebsiteFeature {
  name: string;
  category: string;
  description: string;
  evidence: string;
  status: string;
}

// ============ AI Agent 类型定义 ============

interface AgentStep {
  step_id: number;
  thought: string;
  action: string;
  params: Record<string, unknown>;
  observation: string;
  success: boolean;
  error: string;
  has_screenshot: boolean;
  duration_ms: number;
}

interface AgentResult {
  task: string;
  start_url: string;
  success: boolean;
  finish_reason: string;
  total_steps: number;
  total_duration_ms: number;
  error: string;
  final_url: string;
  final_title: string;
  final_screenshot_b64: string;
  steps: AgentStep[];
}

interface ComprehensiveResult {
  start_url: string;
  functional: AutoTestResult | null;
  stress: StressResult | null;
  boundary: BoundaryResult | null;
  regression: RegressionResult | null;
  features: WebsiteFeature[];
  summary: {
    url: string;
    pages_tested: number;
    duration_ms: number;
    functional_score?: number;
    functional_pass_rate?: number;
    stress_qps?: number;
    stress_p95?: number;
    stress_error_rate?: number;
    boundary_pass_rate?: number;
    regression_changes?: number;
    feature_count?: number;
    features_detected?: number;
    features_missing?: number;
    overall_score?: number;
  };
  duration_ms: number;
  error: string;
}

// ============ 样式常量 ============

const cardStyle: React.CSSProperties = {
  background: "#1e293b",
  borderRadius: 8,
  padding: "1.5rem",
};

const numberStyle = (color: string): React.CSSProperties => ({
  fontSize: "1.8rem",
  fontWeight: 800,
  color,
  fontFamily: "monospace",
});

const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: "0.75rem",
  background: "#0f172a",
  border: "1px solid #334155",
  borderRadius: 6,
  color: "#e2e8f0",
  fontSize: "0.9rem",
};

const btnPrimary: React.CSSProperties = {
  padding: "0.75rem 2rem",
  border: "none",
  borderRadius: 6,
  background: "#3b82f6",
  color: "#fff",
  fontWeight: 700,
  cursor: "pointer",
};

const btnDisabled: React.CSSProperties = {
  ...btnPrimary,
  background: "#334155",
  cursor: "default",
};

const severityColor: Record<string, string> = {
  info: "#38bdf8",
  warning: "#f59e0b",
  error: "#ef4444",
  critical: "#dc2626",
};

const categoryLabel: Record<string, string> = {
  broken_link: "死链检测",
  form: "表单测试",
  accessibility: "可访问性",
  seo: "SEO",
  security: "安全",
  performance: "性能",
  js_error: "JS 错误",
  responsive: "响应式",
};

// 测试用例分类标签
const testCaseCategoryLabel: Record<string, string> = {
  page_access: "页面访问",
  link_check: "链接检查",
  form_test: "表单测试",
  seo: "SEO",
  security: "安全",
};

// 测试用例分类颜色
const testCaseCategoryColor: Record<string, string> = {
  page_access: "#38bdf8",
  link_check: "#a78bfa",
  form_test: "#22c55e",
  seo: "#f59e0b",
  security: "#ef4444",
};

// 测试用例分类图标
const testCaseCategoryIcon: Record<string, string> = {
  page_access: "📄",
  link_check: "🔗",
  form_test: "📝",
  seo: "📈",
  security: "🔒",
};

// ============ 主组件 ============

export default function WebsiteTester() {
  // 默认使用 AI Agent 模式（自然语言驱动）
  const [mode, setMode] = useState<Mode>("agent");
  const [url, setUrl] = useState("");
  const [baseUrl, setBaseUrl] = useState("");

  // OpenAPI 扫描
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [emailModal, setEmailModal] = useState(false);
  const [emailAddr, setEmailAddr] = useState("");
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailResult, setEmailResult] = useState("");

  // 爬虫
  const [crawlDepth, setCrawlDepth] = useState(2);
  const [crawlMaxPages, setCrawlMaxPages] = useState(30);
  const [crawling, setCrawling] = useState(false);
  const [crawlResult, setCrawlResult] = useState<CrawlResult | null>(null);

  // 自动化测试
  const [autoDepth, setAutoDepth] = useState(2);
  const [autoMaxPages, setAutoMaxPages] = useState(10);
  const [checkJs, setCheckJs] = useState(false);
  const [checkResponsive, setCheckResponsive] = useState(false);
  const [testForms, setTestForms] = useState(true);
  const [autoTesting, setAutoTesting] = useState(false);
  const [autoResult, setAutoResult] = useState<AutoTestResult | null>(null);
  // 测试用例筛选
  const [caseFilter, setCaseFilter] = useState<string>("all");
  // 测试阶段：idle | crawling | generating | executing | done | error
  const [testStage, setTestStage] = useState<string>("idle");
  // 结果展示Tab：cases / checks / crawl
  const [resultTab, setResultTab] = useState<string>("cases");

  // 综合测试
  const [compTesting, setCompTesting] = useState(false);
  const [compResult, setCompResult] = useState<ComprehensiveResult | null>(null);
  const [compStage, setCompStage] = useState<string>("idle");
  const [compTab, setCompTab] = useState<string>("summary");
  // 测试类型开关
  const [runFunctional, setRunFunctional] = useState(true);
  const [runStress, setRunStress] = useState(true);
  const [runBoundary, setRunBoundary] = useState(true);
  const [runRegression, setRunRegression] = useState(true);
  const [runFeatureAnalysis, setRunFeatureAnalysis] = useState(true);
  // 压力测试参数
  const [stressConcurrency, setStressConcurrency] = useState(10);
  const [stressTotal, setStressTotal] = useState(50);
  // 报告发送
  const [reportModal, setReportModal] = useState(false);
  const [reportEmail, setReportEmail] = useState("");
  const [sendingReport, setSendingReport] = useState(false);
  const [reportResult, setReportResult] = useState("");

  // AI Agent 自然语言测试
  const [agentTask, setAgentTask] = useState("");
  const [agentMaxSteps, setAgentMaxSteps] = useState(10);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentResult, setAgentResult] = useState<AgentResult | null>(null);
  const [agentBrowserReady, setAgentBrowserReady] = useState<boolean | null>(null);
  const [agentStepFilter, setAgentStepFilter] = useState<"all" | "success" | "failed">("all");
  const [agentTaskTemplates, setAgentTaskTemplates] = useState<string[]>([
    "打开 example.com，验证页面有 'Example Domain' 标题",
    "打开 GitHub 首页，点击 Sign in 按钮，验证跳转到登录页",
    "打开 example.com，截图保存，然后结束",
  ]);

  const resetResults = () => {
    setResult(null);
    setCrawlResult(null);
    setAutoResult(null);
    setError("");
  };

  // ---- OpenAPI 扫描 ----
  const scan = async () => {
    setError("");
    setResult(null);
    setScanning(true);
    try {
      const res = await fetch("/api/website/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, base_url: baseUrl, execute: true }),
      });
      const data = await res.json();
      setResult(data);
      if (data.status === "error") setError(data.error);
    } catch (e) {
      setError(`请求失败: ${String(e)}`);
    }
    setScanning(false);
  };

  const exportPDF = async () => {
    setExporting(true);
    setError("");
    try {
      const res = await fetch("/api/website/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, base_url: baseUrl }),
      });
      if (res.headers.get("content-type")?.includes("application/pdf")) {
        const blob = await res.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = `testforge_report_${Date.now()}.pdf`;
        a.click();
        URL.revokeObjectURL(downloadUrl);
      } else {
        const data = await res.json();
        setError(data.error || "导出失败");
      }
    } catch (e) {
      setError(`导出失败: ${String(e)}`);
    }
    setExporting(false);
  };

  const sendEmail = async () => {
    setSendingEmail(true);
    setEmailResult("");
    try {
      const res = await fetch("/api/website/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, base_url: baseUrl, to_emails: [emailAddr] }),
      });
      const data = await res.json();
      if (data.success) {
        setEmailResult(`✅ 已发送至 ${emailAddr}`);
        setTimeout(() => { setEmailModal(false); setEmailResult(""); }, 2000);
      } else {
        setEmailResult(`❌ ${data.error}`);
      }
    } catch (e) {
      setEmailResult(`❌ ${String(e)}`);
    }
    setSendingEmail(false);
  };

  // ---- 网页爬虫 ----
  const crawl = async () => {
    setError("");
    setCrawlResult(null);
    setCrawling(true);
    try {
      const res = await fetch("/api/website/crawl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          max_depth: crawlDepth,
          max_pages: crawlMaxPages,
          max_concurrency: 5,
          timeout: 10,
          respect_robots: true,
        }),
      });
      const data = await res.json();
      setCrawlResult(data);
      if (data.error) setError(data.error);
    } catch (e) {
      setError(`爬取失败: ${String(e)}`);
    }
    setCrawling(false);
  };

  // ---- 自动化测试 ----
  const autoTest = async () => {
    setError("");
    setAutoResult(null);
    setAutoTesting(true);
    setTestStage("crawling");
    setResultTab("cases");

    // 模拟阶段推进（后端是单次请求，前端用定时器展示进度）
    const stageTimers: number[] = [];
    let finished = false;
    stageTimers.push(window.setTimeout(() => { if (!finished) setTestStage("generating"); }, 2000));
    stageTimers.push(window.setTimeout(() => { if (!finished) setTestStage("executing"); }, 4500));

    try {
      const res = await fetch("/api/website/auto-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          crawl_depth: autoDepth,
          max_pages: autoMaxPages,
          max_concurrency: 5,
          timeout: 10,
          check_js: checkJs,
          check_responsive: checkResponsive,
          test_forms: testForms,
        }),
      });

      // 检查响应是否为空（后端异常时可能返回空body）
      const text = await res.text();
      if (!text) {
        throw new Error("服务器返回空响应，请检查后端是否正常运行");
      }

      let data: AutoTestResult;
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("服务器返回的数据格式异常，无法解析为JSON");
      }

      finished = true;
      setAutoResult(data);
      setTestStage(data.error ? "error" : "done");
      if (data.error) setError(data.error);
    } catch (e) {
      finished = true;
      setError(`自动化测试失败: ${String(e)}`);
      setTestStage("error");
    } finally {
      stageTimers.forEach((t) => clearTimeout(t));
      setAutoTesting(false);
    }
  };

  // ---- 综合测试 ----
  const comprehensiveTest = async () => {
    setError("");
    setCompResult(null);
    setCompTesting(true);
    setCompStage("crawling");
    setCompTab("summary");

    const stageTimers: number[] = [];
    let finished = false;
    stageTimers.push(window.setTimeout(() => { if (!finished) setCompStage("functional"); }, 3000));
    stageTimers.push(window.setTimeout(() => { if (!finished) setCompStage("stress"); }, 8000));
    stageTimers.push(window.setTimeout(() => { if (!finished) setCompStage("boundary"); }, 12000));
    stageTimers.push(window.setTimeout(() => { if (!finished) setCompStage("regression"); }, 16000));
    stageTimers.push(window.setTimeout(() => { if (!finished) setCompStage("analysis"); }, 19000));

    try {
      const res = await fetch("/api/website/comprehensive-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          run_functional: runFunctional,
          run_stress: runStress,
          run_boundary: runBoundary,
          run_regression: runRegression,
          run_feature_analysis: runFeatureAnalysis,
          crawl_depth: autoDepth,
          max_pages: autoMaxPages,
          stress_concurrency: stressConcurrency,
          stress_total: stressTotal,
          timeout: 10,
        }),
      });

      const text = await res.text();
      if (!text) {
        throw new Error("服务器返回空响应，请检查后端是否正常运行");
      }

      let data: ComprehensiveResult;
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("服务器返回的数据格式异常，无法解析为JSON");
      }

      finished = true;
      setCompResult(data);
      setCompStage(data.error ? "error" : "done");
      if (data.error) setError(data.error);
    } catch (e) {
      finished = true;
      setError(`综合测试失败: ${String(e)}`);
      setCompStage("error");
    } finally {
      stageTimers.forEach((t) => clearTimeout(t));
      setCompTesting(false);
    }
  };

  // ---- 发送测试报告 ----
  const sendReport = async () => {
    setSendingReport(true);
    setReportResult("");
    try {
      const res = await fetch("/api/website/send-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          to_emails: [reportEmail],
          test_result: compResult || {},
        }),
      });
      const data = await res.json();
      if (data.success) {
        setReportResult(`✅ ${data.message}`);
        setTimeout(() => { setReportModal(false); setReportResult(""); }, 2500);
      } else {
        setReportResult(`❌ ${data.error}`);
      }
    } catch (e) {
      setReportResult(`❌ ${String(e)}`);
    }
    setSendingReport(false);
  };

  // ---- AI Agent 自然语言任务执行 ----
  const checkAgentBrowser = async () => {
    try {
      const r = await fetch("/api/website/agent/browser-status");
      const data = await r.json();
      setAgentBrowserReady(!!data.available);
    } catch {
      setAgentBrowserReady(false);
    }
  };

  const runAgentTask = async () => {
    if (!agentTask.trim()) {
      setError("请输入自然语言任务描述");
      return;
    }
    setError("");
    setAgentResult(null);
    setAgentRunning(true);

    try {
      const res = await fetch("/api/website/agent/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: agentTask,
          start_url: url || "",
          max_steps: agentMaxSteps,
        }),
      });
      const text = await res.text();
      if (!text) {
        throw new Error("服务器返回空响应，请检查后端是否正常运行");
      }
      const data = JSON.parse(text);
      if (!data.success) {
        setError(data.error || "Agent 任务执行失败");
        return;
      }
      setAgentResult(data.result);
    } catch (e) {
      setError(`AI Agent 执行失败: ${String(e)}`);
    } finally {
      setAgentRunning(false);
    }
  };

  // ============ 渲染 ============

  const tabBtn = (m: Mode): React.CSSProperties => ({
    padding: "0.6rem 1.2rem",
    borderRadius: 6,
    background: mode === m ? "#3b82f6" : "#0f172a",
    color: mode === m ? "#fff" : "#94a3b8",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: "0.9rem",
    border: "1px solid #334155",
  });

  return (
    <div>
      <h2 style={{ marginBottom: "1.5rem" }}>🌐 网站自动测试</h2>

      {/* 模式切换 Tab */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        <button style={tabBtn("agent")} onClick={() => { setMode("agent"); resetResults(); setCompResult(null); }}>
          🤖 AI Agent
        </button>
        <button style={tabBtn("comprehensive")} onClick={() => { setMode("comprehensive"); resetResults(); setCompResult(null); }}>
          🎯 综合测试
        </button>
        <button style={tabBtn("autotest")} onClick={() => { setMode("autotest"); resetResults(); setCompResult(null); }}>
          🧪 自动化测试
        </button>
        <button style={tabBtn("crawl")} onClick={() => { setMode("crawl"); resetResults(); setCompResult(null); }}>
          🕷️ 网页爬虫
        </button>
        <button style={tabBtn("openapi")} onClick={() => { setMode("openapi"); resetResults(); setCompResult(null); }}>
          📄 OpenAPI 扫描
        </button>
      </div>

      {/* URL 输入区（所有模式共用） */}
      <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
        <div style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
          {mode === "agent" && "用自然语言描述你想做的操作（如：\"打开 example.com 并验证标题\"），AI Agent 会自主决策并操作真实浏览器"}
          {mode === "comprehensive" && "输入网站 URL，一键执行功能测试 + 压力测试 + 边界测试 + 回归测试 + 功能分析，生成综合报告"}
          {mode === "openapi" && "输入 OpenAPI/Swagger 文档 URL，自动解析所有 API 端点 → 生成测试 → 执行"}
          {mode === "crawl" && "输入任意网站 URL，自动爬取页面、提取链接/表单/资源、检测死链"}
          {mode === "autotest" && "输入网站 URL，自动执行死链/表单/可访问性/SEO/安全/性能多维测试"}
        </div>
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={
              mode === "openapi"
                ? "https://petstore.swagger.io/v2/swagger.json"
                : "https://example.com"
            }
            style={inputStyle}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                if (mode === "openapi") scan();
                else if (mode === "crawl") crawl();
                else if (mode === "comprehensive") comprehensiveTest();
                else if (mode === "agent") runAgentTask();
                else autoTest();
              }
            }}
          />
          {mode === "openapi" ? (
            <button onClick={scan} disabled={scanning || !url} style={scanning || !url ? btnDisabled : btnPrimary}>
              {scanning ? "⏳ 扫描中..." : "🚀 扫描并测试"}
            </button>
          ) : mode === "crawl" ? (
            <button onClick={crawl} disabled={crawling || !url} style={crawling || !url ? btnDisabled : btnPrimary}>
              {crawling ? "⏳ 爬取中..." : "🕷️ 开始爬取"}
            </button>
          ) : mode === "comprehensive" ? (
            <button onClick={comprehensiveTest} disabled={compTesting || !url} style={compTesting || !url ? btnDisabled : btnPrimary}>
              {compTesting ? "⏳ 综合测试中..." : "🎯 开始综合测试"}
            </button>
          ) : mode === "agent" ? (
            <button onClick={runAgentTask} disabled={agentRunning || !agentTask.trim()} style={agentRunning || !agentTask.trim() ? btnDisabled : btnPrimary}>
              {agentRunning ? "🤖 Agent 思考中..." : "🤖 让 AI Agent 执行"}
            </button>
          ) : (
            <button onClick={autoTest} disabled={autoTesting || !url} style={autoTesting || !url ? btnDisabled : btnPrimary}>
              {autoTesting ? "⏳ 测试中..." : "🤖 开始测试"}
            </button>
          )}
        </div>
        {mode === "openapi" && (
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="API Base URL（可选，留空使用文档中的）"
            style={{ ...inputStyle, flex: "none", width: "100%", padding: "0.5rem", fontSize: "0.85rem" }}
          />
        )}

        {/* 模式专属配置 */}
        {mode === "agent" && (
          <div style={{ marginTop: "0.75rem" }}>
            {/* 浏览器状态指示器 */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
              {agentBrowserReady === null ? (
                <span style={{ color: "#64748b", fontSize: "0.75rem" }}>⏳ 检查浏览器环境...</span>
              ) : agentBrowserReady ? (
                <span style={{ color: "#22c55e", fontSize: "0.75rem" }}>🟢 浏览器就绪 (Chromium + Playwright)</span>
              ) : (
                <span style={{ color: "#ef4444", fontSize: "0.75rem" }}>🔴 浏览器未就绪，请先执行: <code>playwright install chromium</code></span>
              )}
              <button onClick={checkAgentBrowser} style={{
                padding: "0.15rem 0.5rem", background: "transparent", border: "1px solid #334155",
                borderRadius: 4, color: "#94a3b8", cursor: "pointer", fontSize: "0.7rem",
              }}>刷新</button>
            </div>

            {/* 自然语言任务输入 */}
            <textarea
              value={agentTask}
              onChange={(e) => setAgentTask(e.target.value)}
              placeholder="用自然语言描述任务，如：&#10;• 打开 example.com，验证页面有 'Example Domain' 标题&#10;• 打开 GitHub 首页，点击 Sign in 按钮，验证跳转到登录页"
              rows={3}
              style={{
                ...inputStyle, fontFamily: "inherit", resize: "vertical", minHeight: 70,
              }}
            />

            {/* 任务模板 */}
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "0.5rem 0" }}>
              <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>💡 模板：</span>
              {agentTaskTemplates.map((tpl, i) => (
                <button key={i} onClick={() => setAgentTask(tpl)} style={{
                  padding: "0.2rem 0.6rem", background: "#1e293b", border: "1px solid #334155",
                  borderRadius: 4, color: "#94a3b8", cursor: "pointer", fontSize: "0.7rem",
                }}>{tpl.length > 30 ? tpl.slice(0, 30) + "..." : tpl}</button>
              ))}
            </div>

            {/* Agent 参数 */}
            <div style={{ display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
              <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                起始 URL（可选）:
                <input value={url} onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com（留空由 LLM 推断）"
                  style={{ ...inputStyle, width: 280, marginLeft: "0.5rem", padding: "0.4rem" }} />
              </label>
              <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                最大步数:
                <input type="number" min={1} max={30} value={agentMaxSteps}
                  onChange={(e) => setAgentMaxSteps(Number(e.target.value))}
                  style={{ ...inputStyle, width: 60, marginLeft: "0.5rem", padding: "0.4rem" }} />
              </label>
            </div>

            {/* 能力说明 */}
            <details style={{ marginTop: "0.5rem", color: "#94a3b8", fontSize: "0.8rem" }}>
              <summary style={{ cursor: "pointer", color: "#38bdf8" }}>📖 AI Agent 能力说明（点击展开）</summary>
              <div style={{ marginTop: "0.5rem", padding: "0.5rem", background: "#0f172a", borderRadius: 4 }}>
                <b>工作原理：</b>自然语言任务 → LLM 推理（截图+DOM观察）→ Playwright 操作 → 循环直到完成<br />
                <b>支持的操作：</b>点击、输入、选择、悬停、滚动、等待、键盘按键、文件上传、拖拽、iframe切换、多标签页、弹窗处理、截图、AI语义断言<br />
                <b>观察能力：</b>URL、标题、可访问树（a11y tree）、页面截图（base64）<br />
                <b>自愈能力：</b>操作失败时自动让 LLM 重新规划<br />
                <b>典型用例：</b>登录态测试、多步骤业务流程（注册→登录→下单）、SPA 动态加载、文件下载验证
              </div>
            </details>
          </div>
        )}
        {mode === "comprehensive" && (
          <div style={{ marginTop: "0.75rem" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.8rem", marginBottom: "0.5rem" }}>选择测试类型:</div>
            <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
              {[
                { key: "functional", label: "功能测试", icon: "🧪", state: runFunctional, set: setRunFunctional },
                { key: "stress", label: "压力测试", icon: "⚡", state: runStress, set: setRunStress },
                { key: "boundary", label: "边界测试", icon: "🔧", state: runBoundary, set: setRunBoundary },
                { key: "regression", label: "回归测试", icon: "📊", state: runRegression, set: setRunRegression },
                { key: "analysis", label: "功能分析", icon: "🔍", state: runFeatureAnalysis, set: setRunFeatureAnalysis },
              ].map((t) => (
                <label key={t.key} style={{
                  display: "flex", alignItems: "center", gap: "0.3rem",
                  color: t.state ? "#38bdf8" : "#94a3b8", fontSize: "0.85rem",
                  padding: "0.3rem 0.6rem", borderRadius: 5,
                  background: t.state ? "rgba(56,189,248,0.1)" : "#0f172a",
                  border: `1px solid ${t.state ? "rgba(56,189,248,0.3)" : "#334155"}`,
                  cursor: "pointer",
                }}>
                  <input type="checkbox" checked={t.state} onChange={(e) => t.set(e.target.checked)} />
                  {t.icon} {t.label}
                </label>
              ))}
            </div>
            <div style={{ display: "flex", gap: "1.5rem", alignItems: "center", flexWrap: "wrap" }}>
              <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                爬取深度:
                <input type="number" min={0} max={3} value={autoDepth}
                  onChange={(e) => setAutoDepth(Number(e.target.value))}
                  style={{ ...inputStyle, width: 70, marginLeft: "0.5rem", padding: "0.4rem" }} />
              </label>
              <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                最大页面:
                <input type="number" min={1} max={50} value={autoMaxPages}
                  onChange={(e) => setAutoMaxPages(Number(e.target.value))}
                  style={{ ...inputStyle, width: 70, marginLeft: "0.5rem", padding: "0.4rem" }} />
              </label>
              <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                压力并发数:
                <input type="number" min={1} max={100} value={stressConcurrency}
                  onChange={(e) => setStressConcurrency(Number(e.target.value))}
                  style={{ ...inputStyle, width: 70, marginLeft: "0.5rem", padding: "0.4rem" }} />
              </label>
              <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                压力总请求:
                <input type="number" min={10} max={500} value={stressTotal}
                  onChange={(e) => setStressTotal(Number(e.target.value))}
                  style={{ ...inputStyle, width: 70, marginLeft: "0.5rem", padding: "0.4rem" }} />
              </label>
            </div>
          </div>
        )}
        {mode === "crawl" && (
          <div style={{ display: "flex", gap: "1.5rem", marginTop: "0.75rem", alignItems: "center" }}>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
              爬取深度:
              <input type="number" min={0} max={5} value={crawlDepth}
                onChange={(e) => setCrawlDepth(Number(e.target.value))}
                style={{ ...inputStyle, width: 80, marginLeft: "0.5rem", padding: "0.4rem" }} />
            </label>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
              最大页面数:
              <input type="number" min={1} max={100} value={crawlMaxPages}
                onChange={(e) => setCrawlMaxPages(Number(e.target.value))}
                style={{ ...inputStyle, width: 80, marginLeft: "0.5rem", padding: "0.4rem" }} />
            </label>
          </div>
        )}
        {mode === "autotest" && (
          <div style={{ display: "flex", gap: "1.5rem", marginTop: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
              爬取深度:
              <input type="number" min={0} max={3} value={autoDepth}
                onChange={(e) => setAutoDepth(Number(e.target.value))}
                style={{ ...inputStyle, width: 70, marginLeft: "0.5rem", padding: "0.4rem" }} />
            </label>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
              最大页面:
              <input type="number" min={1} max={50} value={autoMaxPages}
                onChange={(e) => setAutoMaxPages(Number(e.target.value))}
                style={{ ...inputStyle, width: 70, marginLeft: "0.5rem", padding: "0.4rem" }} />
            </label>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
              <input type="checkbox" checked={testForms} onChange={(e) => setTestForms(e.target.checked)} />
              表单测试
            </label>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
              <input type="checkbox" checked={checkJs} onChange={(e) => setCheckJs(e.target.checked)} />
              JS 错误检查
            </label>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
              <input type="checkbox" checked={checkResponsive} onChange={(e) => setCheckResponsive(e.target.checked)} />
              响应式截图
            </label>
            {(checkJs || checkResponsive) && (
              <span style={{ color: "#f59e0b", fontSize: "0.75rem" }}>⚠️ 需安装 Playwright</span>
            )}
          </div>
        )}

        {/* 示例链接 */}
        {mode === "openapi" && (
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <span style={{ color: "#475569", fontSize: "0.8rem" }}>示例:</span>
            {[
              "https://petstore.swagger.io/v2/swagger.json",
              "https://petstore3.swagger.io/api/v3/openapi.json",
            ].map((u) => (
              <button key={u} onClick={() => setUrl(u)}
                style={{ padding: "2px 8px", background: "#0f172a", border: "1px solid #334155", borderRadius: 4, color: "#38bdf8", cursor: "pointer", fontSize: "0.75rem" }}>
                {u.split("/")[2]}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 错误提示 */}
      {error && (
        <div style={{ padding: "0.75rem 1rem", marginBottom: "1rem", background: "#7f1d1d", borderRadius: 8, color: "#fca5a5" }}>
          ⚠️ {error}
        </div>
      )}

      {/* ============ 测试流程步骤指示器（自动化测试模式） ============ */}
      {mode === "autotest" && (autoTesting || testStage === "done" || testStage === "error") && (
        <div style={{ ...cardStyle, marginBottom: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
            {[
              { key: "crawling", icon: "🕷️", label: "爬取网站", desc: "抓取页面、提取链接和表单" },
              { key: "generating", icon: "🧪", label: "生成用例", desc: "根据页面生成测试用例" },
              { key: "executing", icon: "⚡", label: "执行测试", desc: "真实HTTP请求验证" },
              { key: "done", icon: "✅", label: "测试完成", desc: "汇总结果和评分" },
            ].map((step, i, arr) => {
              const order = ["crawling", "generating", "executing", "done", "error"];
              const currentIdx = order.indexOf(testStage);
              const stepIdx = order.indexOf(step.key);
              const isDone = testStage === "done" || (testStage !== "error" && currentIdx > stepIdx);
              const isActive = testStage === step.key;
              const isError = testStage === "error" && step.key === "done";
              const color = isError ? "#ef4444" : isDone ? "#22c55e" : isActive ? "#3b82f6" : "#475569";
              return (
                <div key={step.key} style={{ flex: 1, textAlign: "center" }}>
                  <div style={{
                    width: 44, height: 44, borderRadius: "50%", margin: "0 auto 0.5rem",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "1.3rem",
                    background: isActive ? "#3b82f6" : isDone ? "rgba(34,197,94,0.15)" : isError ? "rgba(239,68,68,0.15)" : "#0f172a",
                    border: `2px solid ${color}`,
                    transition: "all 0.3s",
                  }}>
                    {isError ? "❌" : isDone ? "✅" : isActive ? "⏳" : step.icon}
                  </div>
                  <div style={{ color, fontSize: "0.85rem", fontWeight: 700 }}>{step.label}</div>
                  <div style={{ color: "#475569", fontSize: "0.7rem", marginTop: "0.15rem" }}>{step.desc}</div>
                  {i < arr.length - 1 && (
                    <div style={{ height: 2, background: isDone ? "#22c55e" : "#334155", margin: "0.75rem -50% 0", position: "relative", zIndex: 0 }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ============ AI Agent 结果展示 ============ */}
      {mode === "agent" && agentResult && (
        <div style={{ marginBottom: "1.5rem" }}>
          {/* 顶部汇总卡 */}
          <div style={{ ...cardStyle, marginBottom: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            <div style={{ flex: 1, minWidth: 240 }}>
              <h3 style={{ color: agentResult.success ? "#22c55e" : "#ef4444", margin: "0 0 0.5rem" }}>
                {agentResult.success ? "✅ AI Agent 任务完成" : "❌ AI Agent 任务失败"}
              </h3>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                任务: <span style={{ color: "#e2e8f0" }}>{agentResult.task}</span>
              </div>
              <div style={{ color: "#94a3b8", fontSize: "0.8rem", marginTop: "0.3rem" }}>
                📍 {agentResult.final_url || "—"} | 📄 {agentResult.final_title || "—"}
              </div>
              <div style={{ color: "#94a3b8", fontSize: "0.8rem", marginTop: "0.3rem" }}>
                完成原因: {agentResult.finish_reason || "—"}
              </div>
            </div>
            <div style={{ display: "flex", gap: "1.5rem", textAlign: "center" }}>
              <div>
                <div style={{ color: "#94a3b8", fontSize: "0.7rem" }}>总步数</div>
                <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "#e2e8f0", fontFamily: "monospace" }}>
                  {agentResult.total_steps}
                </div>
              </div>
              <div>
                <div style={{ color: "#94a3b8", fontSize: "0.7rem" }}>耗时</div>
                <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#38bdf8", fontFamily: "monospace" }}>
                  {(agentResult.total_duration_ms / 1000).toFixed(1)}s
                </div>
              </div>
              <div>
                <div style={{ color: "#94a3b8", fontSize: "0.7rem" }}>成功率</div>
                <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#22c55e", fontFamily: "monospace" }}>
                  {agentResult.total_steps > 0
                    ? Math.round(agentResult.steps.filter((s) => s.success).length / agentResult.total_steps * 100)
                    : 0}%
                </div>
              </div>
            </div>
          </div>

          {/* 双栏布局：左步骤日志 + 右最终截图 */}
          <div style={{ display: "grid", gridTemplateColumns: agentResult.final_screenshot_b64 ? "1fr 360px" : "1fr", gap: "1rem" }}>
            {/* 步骤日志 */}
            <div style={cardStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h4 style={{ color: "#38bdf8", margin: 0 }}>🔁 ReAct 决策日志</h4>
                <div style={{ display: "flex", gap: "0.4rem" }}>
                  {([
                    ["all", "全部"],
                    ["success", "✅ 成功"],
                    ["failed", "❌ 失败"],
                  ] as const).map(([k, label]) => (
                    <button key={k} onClick={() => setAgentStepFilter(k)}
                      style={{
                        padding: "0.25rem 0.7rem", borderRadius: 4, cursor: "pointer", fontSize: "0.75rem",
                        background: agentStepFilter === k ? "#3b82f6" : "#0f172a",
                        color: agentStepFilter === k ? "#fff" : "#94a3b8",
                        border: "1px solid #334155",
                      }}>{label}</button>
                  ))}
                </div>
              </div>

              <div style={{ maxHeight: 600, overflowY: "auto" }}>
                {agentResult.steps
                  .filter((s) => agentStepFilter === "all" || (agentStepFilter === "success" ? s.success : !s.success))
                  .map((s) => (
                  <div key={s.step_id} style={{
                    padding: "0.6rem 0.75rem", marginBottom: "0.5rem", background: "#0f172a",
                    borderRadius: 6, borderLeft: `3px solid ${s.success ? "#22c55e" : "#ef4444"}`,
                  }}>
                    {/* 头部：步骤号 + 动作 + 状态 */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
                      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                        <span style={{ color: "#64748b", fontSize: "0.7rem", fontFamily: "monospace", fontWeight: 700 }}>
                          #{s.step_id}
                        </span>
                        <span style={{
                          padding: "0.15rem 0.5rem", borderRadius: 3, fontSize: "0.7rem", fontWeight: 700,
                          background: "#1e293b", color: "#38bdf8",
                        }}>{s.action}</span>
                        <span style={{ color: s.success ? "#22c55e" : "#ef4444", fontSize: "0.85rem" }}>
                          {s.success ? "✅" : "❌"}
                        </span>
                      </div>
                      <span style={{ color: "#64748b", fontSize: "0.7rem", fontFamily: "monospace" }}>
                        {s.duration_ms}ms
                      </span>
                    </div>

                    {/* 思考 */}
                    {s.thought && (
                      <div style={{ color: "#cbd5e1", fontSize: "0.8rem", marginBottom: "0.3rem" }}>
                        💭 {s.thought}
                      </div>
                    )}

                    {/* 参数 */}
                    {Object.keys(s.params || {}).length > 0 && (
                      <div style={{ fontSize: "0.7rem", color: "#94a3b8", fontFamily: "monospace", background: "#020617", padding: "0.3rem 0.5rem", borderRadius: 3, marginBottom: "0.3rem", overflow: "auto" }}>
                        {JSON.stringify(s.params, null, 0)}
                      </div>
                    )}

                    {/* 错误 */}
                    {s.error && (
                      <div style={{ color: "#fca5a5", fontSize: "0.75rem", marginBottom: "0.2rem" }}>
                        ⚠️ {s.error}
                      </div>
                    )}

                    {/* 观察摘要 */}
                    {s.observation && (
                      <details style={{ marginTop: "0.3rem" }}>
                        <summary style={{ cursor: "pointer", color: "#64748b", fontSize: "0.7rem" }}>
                          👁 观察（点击展开）
                        </summary>
                        <pre style={{
                          color: "#94a3b8", fontSize: "0.7rem", background: "#020617",
                          padding: "0.4rem", borderRadius: 3, marginTop: "0.3rem",
                          maxHeight: 200, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word",
                        }}>{s.observation.slice(0, 1500)}</pre>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 最终截图 */}
            {agentResult.final_screenshot_b64 && (
              <div style={cardStyle}>
                <h4 style={{ color: "#38bdf8", margin: "0 0 0.5rem" }}>📸 最终页面截图</h4>
                <img
                  src={`data:image/jpeg;base64,${agentResult.final_screenshot_b64}`}
                  alt="Final page screenshot"
                  style={{ width: "100%", borderRadius: 4, border: "1px solid #334155" }}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============ 综合测试流程步骤指示器 ============ */}
      {mode === "comprehensive" && (compTesting || compStage === "done" || compStage === "error") && (
        <div style={{ ...cardStyle, marginBottom: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
            {[
              { key: "crawling", icon: "🕷️", label: "爬取网站" },
              { key: "functional", icon: "🧪", label: "功能测试" },
              { key: "stress", icon: "⚡", label: "压力测试" },
              { key: "boundary", icon: "🔧", label: "边界测试" },
              { key: "regression", icon: "📊", label: "回归测试" },
              { key: "analysis", icon: "🔍", label: "功能分析" },
              { key: "done", icon: "✅", label: "完成" },
            ].map((step, i, arr) => {
              const order = ["crawling", "functional", "stress", "boundary", "regression", "analysis", "done", "error"];
              const currentIdx = order.indexOf(compStage);
              const stepIdx = order.indexOf(step.key);
              const isDone = compStage === "done" || (compStage !== "error" && currentIdx > stepIdx);
              const isActive = compStage === step.key;
              const isError = compStage === "error" && step.key === "done";
              const color = isError ? "#ef4444" : isDone ? "#22c55e" : isActive ? "#3b82f6" : "#475569";
              return (
                <div key={step.key} style={{ flex: 1, textAlign: "center" }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: "50%", margin: "0 auto 0.4rem",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "1.2rem",
                    background: isActive ? "#3b82f6" : isDone ? "rgba(34,197,94,0.15)" : isError ? "rgba(239,68,68,0.15)" : "#0f172a",
                    border: `2px solid ${color}`,
                  }}>
                    {isError ? "❌" : isDone ? "✅" : isActive ? "⏳" : step.icon}
                  </div>
                  <div style={{ color, fontSize: "0.75rem", fontWeight: 700 }}>{step.label}</div>
                  {i < arr.length - 1 && (
                    <div style={{ height: 2, background: isDone ? "#22c55e" : "#334155", margin: "0.5rem -50% 0", zIndex: 0 }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ============ 综合测试结果 ============ */}
      {mode === "comprehensive" && compResult && !compResult.error && (
        <>
          {/* 综合评分 + 发送报告按钮 */}
          <div style={{ ...cardStyle, marginBottom: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ color: "#38bdf8", margin: "0 0 0.5rem" }}>🎯 综合测试报告</h3>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                {compResult.summary.pages_tested} 个页面 | 耗时 {compResult.duration_ms}ms
              </div>
            </div>
            <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>综合评分</div>
                <div style={{
                  fontSize: "2.5rem", fontWeight: 800, fontFamily: "monospace",
                  color: (compResult.summary.overall_score || 0) >= 80 ? "#22c55e" : (compResult.summary.overall_score || 0) >= 60 ? "#f59e0b" : "#ef4444",
                }}>
                  {compResult.summary.overall_score || 0}
                </div>
              </div>
              <button
                onClick={() => setReportModal(true)}
                style={{
                  padding: "0.6rem 1.2rem", border: "none", borderRadius: 6,
                  background: "#14532d", color: "#22c55e", cursor: "pointer",
                  fontWeight: 700, fontSize: "0.85rem",
                }}
              >
                📧 发送报告
              </button>
            </div>
          </div>

          {/* 结果Tab栏 */}
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            {[
              { key: "summary", label: "📊 总览" },
              { key: "functional", label: "🧪 功能测试" },
              { key: "stress", label: "⚡ 压力测试" },
              { key: "boundary", label: "🔧 边界测试" },
              { key: "regression", label: "📊 回归测试" },
              { key: "features", label: "🔍 功能分析" },
            ].map((t) => (
              <button key={t.key} onClick={() => setCompTab(t.key)}
                style={{
                  padding: "0.5rem 1rem", borderRadius: 6, cursor: "pointer",
                  fontWeight: 600, fontSize: "0.85rem", border: "1px solid #334155",
                  background: compTab === t.key ? "#3b82f6" : "#0f172a",
                  color: compTab === t.key ? "#fff" : "#94a3b8",
                }}>
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab: 总览 */}
          {compTab === "summary" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1rem" }}>
              {compResult.functional && (
                <div style={cardStyle}>
                  <h4 style={{ color: "#38bdf8", margin: "0 0 0.5rem" }}>🧪 功能测试</h4>
                  <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                    健康分: <b style={{ color: "#e2e8f0" }}>{compResult.functional.score}</b> |
                    用例: <b style={{ color: "#22c55e" }}>{compResult.functional.test_passed}</b>/{compResult.functional.test_total} 通过
                  </div>
                </div>
              )}
              {compResult.stress && (
                <div style={cardStyle}>
                  <h4 style={{ color: "#a78bfa", margin: "0 0 0.5rem" }}>⚡ 压力测试</h4>
                  <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                    QPS: <b style={{ color: "#e2e8f0" }}>{compResult.stress.qps}</b> |
                    P95: <b style={{ color: "#e2e8f0" }}>{compResult.stress.p95}ms</b> |
                    错误率: <b style={{ color: compResult.stress.error_rate > 0.1 ? "#ef4444" : "#22c55e" }}>{(compResult.stress.error_rate * 100).toFixed(1)}%</b>
                  </div>
                </div>
              )}
              {compResult.boundary && (
                <div style={cardStyle}>
                  <h4 style={{ color: "#f59e0b", margin: "0 0 0.5rem" }}>🔧 边界测试</h4>
                  <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                    <b style={{ color: "#22c55e" }}>{compResult.boundary.passed}</b>/{compResult.boundary.total} 通过 |
                    通过率: <b style={{ color: "#e2e8f0" }}>{compResult.boundary.pass_rate}%</b>
                  </div>
                </div>
              )}
              {compResult.regression && (
                <div style={cardStyle}>
                  <h4 style={{ color: "#22c55e", margin: "0 0 0.5rem" }}>📊 回归测试</h4>
                  <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                    {compResult.regression.has_baseline ? "已有基线" : "首次测试"} |
                    变化: <b style={{ color: compResult.regression.regression_count > 0 ? "#ef4444" : "#22c55e" }}>{compResult.regression.change_count} 项</b>
                  </div>
                </div>
              )}
              {compResult.features && compResult.features.length > 0 && (
                <div style={cardStyle}>
                  <h4 style={{ color: "#38bdf8", margin: "0 0 0.5rem" }}>🔍 功能分析</h4>
                  <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                    识别 <b style={{ color: "#e2e8f0" }}>{compResult.features.length}</b> 项功能 |
                    <b style={{ color: "#22c55e" }}> {compResult.summary.features_detected || 0} 项正常</b>
                    {compResult.summary.features_missing ? <b style={{ color: "#ef4444" }}> {compResult.summary.features_missing} 项缺失</b> : ""}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab: 功能测试（复用autoResult展示逻辑） */}
          {compTab === "functional" && compResult.functional && (
            <div style={cardStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
                <h3 style={{ color: "#38bdf8", margin: 0 }}>🧪 功能测试用例</h3>
                <div style={{ fontSize: "0.9rem", color: "#94a3b8" }}>
                  总计 <b style={{ color: "#e2e8f0" }}>{compResult.functional.test_total}</b> |
                  通过 <b style={{ color: "#22c55e" }}>{compResult.functional.test_passed}</b> |
                  失败 <b style={{ color: "#ef4444" }}>{compResult.functional.test_failed}</b> |
                  健康分 <b style={{ color: "#38bdf8" }}>{compResult.functional.score}</b>
                </div>
              </div>
              <div style={{ maxHeight: 400, overflowY: "auto" }}>
                {(compResult.functional.test_cases || []).map((tc, i) => (
                  <div key={tc.id || i} style={{
                    padding: "0.5rem 0.7rem", marginBottom: "0.3rem", background: "#0f172a", borderRadius: 4,
                    borderLeft: `3px solid ${tc.passed ? "#22c55e" : "#ef4444"}`,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
                      <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", flex: 1, minWidth: 0 }}>
                        <span>{tc.passed ? "✅" : "❌"}</span>
                        <span style={{ color: "#64748b", fontSize: "0.7rem", fontFamily: "monospace" }}>{tc.id}</span>
                        {tc.method !== "-" && (
                          <span style={{ padding: "1px 4px", borderRadius: 3, fontSize: "0.65rem", fontWeight: 700, background: "#1e3a5f", color: "#e2e8f0" }}>{tc.method}</span>
                        )}
                        <span style={{ color: "#e2e8f0", fontSize: "0.82rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{tc.name}</span>
                      </div>
                      <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
                        {tc.status_code > 0 && <span style={{ color: tc.status_code < 400 ? "#22c55e" : "#ef4444", fontWeight: 700, fontFamily: "monospace", fontSize: "0.82rem" }}>{tc.status_code}</span>}
                        {tc.duration_ms > 0 && <span style={{ color: "#64748b", fontSize: "0.72rem" }}>{tc.duration_ms}ms</span>}
                      </div>
                    </div>
                    <div style={{ fontSize: "0.75rem", marginTop: "0.2rem", color: "#64748b" }}>
                      期望: <span style={{ color: "#94a3b8" }}>{tc.expected}</span> | 实际: <span style={{ color: tc.passed ? "#86efac" : "#fca5a5" }}>{tc.actual}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab: 压力测试 */}
          {compTab === "stress" && compResult.stress && (
            <div style={cardStyle}>
              <h3 style={{ color: "#a78bfa", marginBottom: "1rem" }}>⚡ 压力测试结果</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
                <div style={{ textAlign: "center", padding: "1rem", background: "#0f172a", borderRadius: 6 }}>
                  <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>总请求</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "#e2e8f0", fontFamily: "monospace" }}>{compResult.stress.total_requests}</div>
                </div>
                <div style={{ textAlign: "center", padding: "1rem", background: "#0f172a", borderRadius: 6 }}>
                  <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>QPS</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "#a78bfa", fontFamily: "monospace" }}>{compResult.stress.qps}</div>
                </div>
                <div style={{ textAlign: "center", padding: "1rem", background: "#0f172a", borderRadius: 6 }}>
                  <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>P95延迟</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "#38bdf8", fontFamily: "monospace" }}>{compResult.stress.p95}ms</div>
                </div>
                <div style={{ textAlign: "center", padding: "1rem", background: "#0f172a", borderRadius: 6 }}>
                  <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>错误率</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: compResult.stress.error_rate > 0.1 ? "#ef4444" : "#22c55e", fontFamily: "monospace" }}>{(compResult.stress.error_rate * 100).toFixed(1)}%</div>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.75rem" }}>
                {[
                  { label: "成功", value: compResult.stress.success_count, color: "#22c55e" },
                  { label: "失败", value: compResult.stress.failed_count, color: "#ef4444" },
                  { label: "P50", value: `${compResult.stress.p50}ms`, color: "#38bdf8" },
                  { label: "P99", value: `${compResult.stress.p99}ms`, color: "#a78bfa" },
                  { label: "平均", value: `${compResult.stress.avg_latency}ms`, color: "#94a3b8" },
                ].map((s) => (
                  <div key={s.label} style={{ textAlign: "center", padding: "0.75rem", background: "#0f172a", borderRadius: 6 }}>
                    <div style={{ color: "#94a3b8", fontSize: "0.7rem" }}>{s.label}</div>
                    <div style={{ fontSize: "1.2rem", fontWeight: 700, color: s.color, fontFamily: "monospace" }}>{s.value}</div>
                  </div>
                ))}
              </div>
              {compResult.stress.status_codes && Object.keys(compResult.stress.status_codes).length > 0 && (
                <div style={{ marginTop: "1rem" }}>
                  <div style={{ color: "#94a3b8", fontSize: "0.8rem", marginBottom: "0.5rem" }}>状态码分布:</div>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {Object.entries(compResult.stress.status_codes).map(([code, count]) => (
                      <span key={code} style={{
                        padding: "0.3rem 0.7rem", borderRadius: 4, fontSize: "0.8rem", fontFamily: "monospace",
                        background: Number(code) < 400 ? "#14532d" : "#7f1d1d",
                        color: Number(code) < 400 ? "#86efac" : "#fca5a5",
                      }}>
                        {code}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab: 边界测试 */}
          {compTab === "boundary" && compResult.boundary && (
            <div style={cardStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
                <h3 style={{ color: "#f59e0b", margin: 0 }}>🔧 边界测试结果</h3>
                <div style={{ fontSize: "0.9rem", color: "#94a3b8" }}>
                  <b style={{ color: "#22c55e" }}>{compResult.boundary.passed}</b>/{compResult.boundary.total} 通过 |
                  通过率 <b style={{ color: "#e2e8f0" }}>{compResult.boundary.pass_rate}%</b>
                </div>
              </div>
              {compResult.boundary.per_page && compResult.boundary.per_page.length > 0 && (
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.8rem" }}>
                  {(compResult.boundary.per_page || []).map((pp) => (
                    <span key={pp.url} style={{
                      padding: "0.35rem 0.7rem", borderRadius: 4, fontSize: "0.75rem",
                      background: pp.failed === 0 ? "#14532d" : "#3f3f00",
                      color: pp.failed === 0 ? "#86efac" : "#fde68a", fontFamily: "monospace",
                    }}>
                      {pp.passed}/{pp.total} ({pp.pass_rate}%)
                    </span>
                  ))}
                </div>
              )}
              <div style={{ maxHeight: 400, overflowY: "auto" }}>
                {(compResult.boundary.test_cases || []).map((tc, i) => (
                  <div key={tc.id || i} style={{
                    padding: "0.5rem 0.7rem", marginBottom: "0.3rem", background: "#0f172a", borderRadius: 4,
                    borderLeft: `3px solid ${tc.passed ? "#22c55e" : "#ef4444"}`,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                        <span>{tc.passed ? "✅" : "❌"}</span>
                        <span style={{ color: "#64748b", fontSize: "0.7rem", fontFamily: "monospace" }}>{tc.id}</span>
                        <span style={{ padding: "1px 4px", borderRadius: 3, fontSize: "0.65rem", fontWeight: 700, background: "#3f3f00", color: "#e2e8f0" }}>{tc.method}</span>
                        <span style={{ color: "#e2e8f0", fontSize: "0.82rem" }}>{tc.name}</span>
                      </div>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        {tc.status_code > 0 && <span style={{ color: tc.status_code < 500 ? "#f59e0b" : "#ef4444", fontWeight: 700, fontFamily: "monospace", fontSize: "0.82rem" }}>{tc.status_code}</span>}
                        {tc.duration_ms > 0 && <span style={{ color: "#64748b", fontSize: "0.72rem" }}>{tc.duration_ms}ms</span>}
                      </div>
                    </div>
                    <div style={{ fontSize: "0.75rem", marginTop: "0.2rem", color: "#64748b" }}>
                      期望: <span style={{ color: "#94a3b8" }}>{tc.expected}</span> | 实际: <span style={{ color: tc.passed ? "#86efac" : "#fca5a5" }}>{tc.actual}</span>
                    </div>
                    {tc.detail && <div style={{ fontSize: "0.72rem", color: "#475569", marginTop: "0.15rem" }}>{tc.detail}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab: 回归测试 */}
          {compTab === "regression" && compResult.regression && (
            <div style={cardStyle}>
              <h3 style={{ color: "#22c55e", marginBottom: "1rem" }}>📊 回归测试结果</h3>
              <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#0f172a", borderRadius: 6 }}>
                <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                  {compResult.regression.has_baseline ? "📌 与历史基线对比" : "📌 首次测试，已创建基线"}
                </div>
                <div style={{ color: "#e2e8f0", fontSize: "0.9rem", marginTop: "0.3rem" }}>
                  检测到 <b style={{ color: compResult.regression.regression_count > 0 ? "#ef4444" : "#22c55e" }}>{compResult.regression.change_count}</b> 项变化
                  {compResult.regression.regression_count > 0 && (
                    <span style={{ color: "#ef4444" }}>（其中 {compResult.regression.regression_count} 项需关注）</span>
                  )}
                </div>
              </div>
              {compResult.regression.changes && compResult.regression.changes.length > 0 && (
                <div>
                  <div style={{ color: "#94a3b8", fontSize: "0.8rem", marginBottom: "0.5rem" }}>变化明细:</div>
                  {compResult.regression.changes.map((c, i) => (
                    <div key={i} style={{
                      padding: "0.5rem 0.7rem", marginBottom: "0.3rem", background: "#0f172a", borderRadius: 4,
                      borderLeft: `3px solid ${c.severity === "warning" ? "#f59e0b" : "#38bdf8"}`,
                    }}>
                      <span style={{ color: c.severity === "warning" ? "#f59e0b" : "#38bdf8", fontSize: "0.7rem", fontWeight: 700, marginRight: "0.5rem" }}>
                        [{c.severity.toUpperCase()}]
                      </span>
                      <span style={{ color: "#e2e8f0", fontSize: "0.85rem" }}>{c.description}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab: 功能分析 */}
          {compTab === "features" && compResult.features && (
            <div style={cardStyle}>
              <h3 style={{ color: "#38bdf8", marginBottom: "1rem" }}>🔍 网站功能分析</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "1rem" }}>
                自动分析并描述网站具备的功能，共识别 {compResult.features.length} 项功能特征：
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "0.75rem" }}>
                {compResult.features.map((f, i) => {
                  const icon = { detected: "✅", missing: "❌", warning: "⚠️" }[f.status] || "•";
                  const color = { detected: "#22c55e", missing: "#ef4444", warning: "#f59e0b" }[f.status] || "#94a3b8";
                  const catLabel = { navigation: "导航", form: "表单", content: "内容", media: "媒体", seo: "SEO", security: "安全" }[f.category] || f.category;
                  return (
                    <div key={i} style={{
                      padding: "0.75rem", background: "#0f172a", borderRadius: 6,
                      borderLeft: `3px solid ${color}`,
                    }}>
                      <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", marginBottom: "0.3rem" }}>
                        <span>{icon}</span>
                        <span style={{ padding: "1px 6px", borderRadius: 3, fontSize: "0.65rem", fontWeight: 700, background: "#1e293b", color }}>{catLabel}</span>
                        <span style={{ color: "#e2e8f0", fontSize: "0.85rem", fontWeight: 600 }}>{f.name}</span>
                      </div>
                      <div style={{ color: "#94a3b8", fontSize: "0.8rem" }}>{f.description}</div>
                      {f.evidence && <div style={{ color: "#475569", fontSize: "0.72rem", marginTop: "0.2rem", fontFamily: "monospace" }}>{f.evidence}</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* ============ OpenAPI 扫描结果 ============ */}
      {mode === "openapi" && result && result.status === "success" && (
        <>
          <div style={{ ...cardStyle, marginBottom: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ color: "#38bdf8", marginBottom: "0.5rem" }}>
                  📋 {result.api_title} <span style={{ color: "#64748b", fontSize: "0.85rem" }}>v{result.api_version}</span>
                </h3>
                <div style={{ color: "#94a3b8", fontSize: "0.9rem" }}>
                  发现 {result.endpoint_count} 个 API 端点 → 生成 {result.test_count} 个测试用例
                  {result.saved_count !== undefined && ` → 已保存 ${result.saved_count} 个`}
                </div>
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button onClick={exportPDF} disabled={exporting}
                  style={{ padding: "0.5rem 1rem", border: "none", borderRadius: 6, background: exporting ? "#334155" : "#1e3a5f", color: "#38bdf8", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}>
                  {exporting ? "⏳ 生成中..." : "📄 导出PDF"}
                </button>
                <button onClick={() => setEmailModal(true)}
                  style={{ padding: "0.5rem 1rem", border: "none", borderRadius: 6, background: "#14532d", color: "#22c55e", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}>
                  📧 发送邮件
                </button>
              </div>
            </div>
          </div>

          {result.execution && result.execution.total > 0 && (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>总测试</div>
                  <div style={numberStyle("#e2e8f0")}>{result.execution.total}</div>
                </div>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>通过</div>
                  <div style={numberStyle("#22c55e")}>{result.execution.passed}</div>
                </div>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>失败</div>
                  <div style={numberStyle("#ef4444")}>{result.execution.failed}</div>
                </div>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>耗时</div>
                  <div style={numberStyle("#38bdf8")}>{result.execution.duration_ms}ms</div>
                </div>
              </div>
              <div style={cardStyle}>
                <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>📝 测试详情</h3>
                {result.execution.results.map((r, i) => (
                  <div key={i} style={{ padding: "0.75rem", marginBottom: "0.5rem", background: "#0f172a", borderRadius: 6, borderLeft: `3px solid ${r.passed ? "#22c55e" : "#ef4444"}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                        <span style={{ padding: "2px 6px", borderRadius: 3, fontSize: "0.75rem", fontWeight: 700, background: r.method === "GET" ? "#1e3a5f" : r.method === "POST" ? "#14532d" : r.method === "DELETE" ? "#7f1d1d" : "#3f3f00", color: "#e2e8f0" }}>{r.method}</span>
                        <span style={{ color: "#94a3b8", fontSize: "0.85rem", fontFamily: "monospace" }}>{r.url.length > 80 ? r.url.slice(0, 80) + "..." : r.url}</span>
                      </div>
                      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                        <span style={{ color: r.status >= 200 && r.status < 300 ? "#22c55e" : "#ef4444", fontWeight: 700, fontFamily: "monospace" }}>{r.status || "N/A"}</span>
                        <span style={{ color: "#64748b", fontSize: "0.8rem" }}>{r.duration_ms}ms</span>
                        <span>{r.passed ? "✅" : "❌"}</span>
                      </div>
                    </div>
                    {r.error && <div style={{ color: "#fca5a5", fontSize: "0.8rem", marginTop: "0.25rem" }}>{r.error}</div>}
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {/* ============ 爬虫结果 ============ */}
      {mode === "crawl" && crawlResult && !crawlResult.error && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>已访问</div>
              <div style={numberStyle("#e2e8f0")}>{crawlResult.visited_count}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>失败</div>
              <div style={numberStyle("#ef4444")}>{crawlResult.failed_count}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>总链接</div>
              <div style={numberStyle("#38bdf8")}>{crawlResult.total_links}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>死链</div>
              <div style={numberStyle(crawlResult.broken_links_count > 0 ? "#ef4444" : "#22c55e")}>{crawlResult.broken_links_count}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>耗时</div>
              <div style={numberStyle("#a78bfa")}>{crawlResult.duration_ms}ms</div>
            </div>
          </div>

          {/* 死链列表 */}
          {crawlResult.broken_links.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: "1rem" }}>
              <h3 style={{ color: "#ef4444", marginBottom: "0.75rem" }}>🔗 死链 ({crawlResult.broken_links.length})</h3>
              {crawlResult.broken_links.slice(0, 20).map((bl, i) => (
                <div key={i} style={{ padding: "0.5rem", marginBottom: "0.4rem", background: "#0f172a", borderRadius: 4, borderLeft: "3px solid #ef4444" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#fca5a5", fontSize: "0.85rem", fontFamily: "monospace" }}>{bl.url.length > 70 ? bl.url.slice(0, 70) + "..." : bl.url}</span>
                    <span style={{ color: "#ef4444", fontWeight: 700, fontSize: "0.85rem" }}>HTTP {bl.status}</span>
                  </div>
                  <div style={{ color: "#64748b", fontSize: "0.75rem" }}>来源: {bl.parent}</div>
                </div>
              ))}
            </div>
          )}

          {/* 表单列表 */}
          {crawlResult.forms.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: "1rem" }}>
              <h3 style={{ color: "#38bdf8", marginBottom: "0.75rem" }}>📝 发现表单 ({crawlResult.forms.length})</h3>
              {crawlResult.forms.slice(0, 10).map((f, i) => (
                <div key={i} style={{ padding: "0.6rem", marginBottom: "0.4rem", background: "#0f172a", borderRadius: 4 }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.3rem" }}>
                    <span style={{ padding: "2px 6px", borderRadius: 3, fontSize: "0.7rem", fontWeight: 700, background: f.method === "POST" ? "#14532d" : "#1e3a5f", color: "#e2e8f0" }}>{f.method}</span>
                    <span style={{ color: "#94a3b8", fontSize: "0.85rem", fontFamily: "monospace" }}>{f.action.length > 60 ? f.action.slice(0, 60) + "..." : f.action}</span>
                    <span style={{ color: "#64748b", fontSize: "0.75rem" }}>({f.field_count} 字段)</span>
                  </div>
                  {f.fields.length > 0 && (
                    <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                      {f.fields.slice(0, 6).map((fld, j) => (
                        <span key={j} style={{ padding: "1px 6px", background: "#1e293b", border: "1px solid #334155", borderRadius: 3, color: "#94a3b8", fontSize: "0.7rem" }}>
                          {fld.name}:{fld.type}{fld.required ? "*" : ""}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* 页面列表 */}
          <div style={cardStyle}>
            <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>📄 爬取页面 ({crawlResult.pages.length})</h3>
            {crawlResult.pages.map((p, i) => (
              <div key={i} style={{ padding: "0.75rem", marginBottom: "0.5rem", background: "#0f172a", borderRadius: 6, borderLeft: `3px solid ${p.error ? "#ef4444" : p.status >= 400 ? "#f59e0b" : "#22c55e"}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: "#e2e8f0", fontSize: "0.9rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {p.title || p.url}
                    </div>
                    <div style={{ color: "#64748b", fontSize: "0.75rem", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {p.url}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexShrink: 0 }}>
                    <span style={{ color: p.status >= 400 ? "#ef4444" : "#22c55e", fontWeight: 700, fontFamily: "monospace", fontSize: "0.85rem" }}>{p.status || "—"}</span>
                    <span style={{ color: "#64748b", fontSize: "0.75rem" }}>{p.response_time_ms}ms</span>
                    <span style={{ color: "#475569", fontSize: "0.7rem" }}>d{p.depth}</span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.3rem", fontSize: "0.7rem", color: "#64748b" }}>
                  <span>🔗 内链 {p.internal_links_count}</span>
                  <span>🌍 外链 {p.external_links_count}</span>
                  <span>📝 表单 {p.forms_count}</span>
                  <span>🖼️ 图片 {p.images_count}</span>
                  <span>📜 脚本 {p.scripts_count}</span>
                  {p.h1.length > 0 && <span>H1: {p.h1[0]}</span>}
                </div>
                {p.error && <div style={{ color: "#fca5a5", fontSize: "0.75rem", marginTop: "0.25rem" }}>{p.error}</div>}
              </div>
            ))}
          </div>
        </>
      )}

      {/* ============ 自动化测试结果 ============ */}
      {mode === "autotest" && autoResult && !autoResult.error && (
        <>
          {/* 评分卡片 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr 1fr", gap: "0.75rem", marginBottom: "1.5rem" }}>
            <div style={{ ...cardStyle, textAlign: "center", gridColumn: "span 1" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>健康评分</div>
              <div style={{ ...numberStyle(autoResult.score >= 80 ? "#22c55e" : autoResult.score >= 60 ? "#f59e0b" : "#ef4444"), fontSize: "2.2rem" }}>{autoResult.score}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.75rem" }}>测试页面</div>
              <div style={numberStyle("#e2e8f0")}>{autoResult.pages_tested}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.75rem" }}>通过</div>
              <div style={numberStyle("#22c55e")}>{autoResult.passed}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.75rem" }}>警告</div>
              <div style={numberStyle("#f59e0b")}>{autoResult.warnings}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.75rem" }}>失败</div>
              <div style={numberStyle("#ef4444")}>{autoResult.failed}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.75rem" }}>严重</div>
              <div style={numberStyle("#dc2626")}>{autoResult.critical}</div>
            </div>
          </div>

          {/* 结果Tab切换栏 */}
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
            <button
              onClick={() => setResultTab("cases")}
              style={{
                padding: "0.6rem 1.2rem", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem", border: "1px solid #334155",
                background: resultTab === "cases" ? "#3b82f6" : "#0f172a",
                color: resultTab === "cases" ? "#fff" : "#94a3b8",
              }}
            >
              🧪 测试用例 {autoResult.test_cases && autoResult.test_cases.length > 0 && `(${autoResult.test_total})`}
            </button>
            <button
              onClick={() => setResultTab("checks")}
              style={{
                padding: "0.6rem 1.2rem", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem", border: "1px solid #334155",
                background: resultTab === "checks" ? "#3b82f6" : "#0f172a",
                color: resultTab === "checks" ? "#fff" : "#94a3b8",
              }}
            >
              🔍 检查项 ({autoResult.checks.length})
            </button>
            <button
              onClick={() => setResultTab("crawl")}
              style={{
                padding: "0.6rem 1.2rem", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem", border: "1px solid #334155",
                background: resultTab === "crawl" ? "#3b82f6" : "#0f172a",
                color: resultTab === "crawl" ? "#fff" : "#94a3b8",
              }}
            >
              📄 爬取详情 {autoResult.crawl && `(${autoResult.crawl.visited_count}页)`}
            </button>
          </div>

          {/* ====== Tab 1: 测试用例 ====== */}
          {resultTab === "cases" && autoResult.test_cases && autoResult.test_cases.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: "1rem" }}>
              {/* 执行情况概览 */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ color: "#38bdf8", margin: 0 }}>🧪 测试用例执行情况</h3>
                <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.9rem" }}>
                  <span style={{ color: "#94a3b8" }}>总计: <b style={{ color: "#e2e8f0" }}>{autoResult.test_total}</b></span>
                  <span style={{ color: "#94a3b8" }}>通过: <b style={{ color: "#22c55e" }}>{autoResult.test_passed}</b></span>
                  <span style={{ color: "#94a3b8" }}>失败: <b style={{ color: "#ef4444" }}>{autoResult.test_failed}</b></span>
                  <span style={{ color: "#94a3b8" }}>通过率: <b style={{ color: autoResult.test_passed / Math.max(autoResult.test_total, 1) >= 0.8 ? "#22c55e" : "#f59e0b" }}>{autoResult.test_total > 0 ? Math.round(autoResult.test_passed / autoResult.test_total * 100) : 0}%</b></span>
                </div>
              </div>

              {/* 按分类统计执行情况 */}
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem", paddingBottom: "1rem", borderBottom: "1px solid #334155" }}>
                {Array.from(new Set(autoResult.test_cases.map((c) => c.category))).map((cat) => {
                  const items = autoResult.test_cases.filter((c) => c.category === cat);
                  const passCnt = items.filter((c) => c.passed).length;
                  const failCnt = items.length - passCnt;
                  return (
                    <div key={cat} style={{
                      padding: "0.5rem 0.9rem", borderRadius: 6, fontSize: "0.8rem",
                      background: failCnt > 0 ? "rgba(239,68,68,0.1)" : "rgba(34,197,94,0.1)",
                      border: `1px solid ${failCnt > 0 ? "rgba(239,68,68,0.3)" : "rgba(34,197,94,0.3)"}`,
                    }}>
                      <span style={{ color: testCaseCategoryColor[cat] || "#94a3b8", fontWeight: 700 }}>
                        {testCaseCategoryIcon[cat] || "📋"} {testCaseCategoryLabel[cat] || cat}
                      </span>
                      <span style={{ color: "#94a3b8", marginLeft: "0.5rem" }}>
                        {passCnt}/{items.length} 通过{failCnt > 0 && ` (${failCnt}失败)`}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* 分类筛选按钮 */}
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
                <button
                  onClick={() => setCaseFilter("all")}
                  style={{
                    padding: "0.35rem 0.8rem", borderRadius: 5, cursor: "pointer", fontSize: "0.8rem", fontWeight: 600,
                    border: "1px solid #334155",
                    background: caseFilter === "all" ? "#3b82f6" : "#0f172a",
                    color: caseFilter === "all" ? "#fff" : "#94a3b8",
                  }}
                >
                  全部 ({autoResult.test_total})
                </button>
                {Array.from(new Set(autoResult.test_cases.map((c) => c.category))).map((cat) => {
                  const items = autoResult.test_cases.filter((c) => c.category === cat);
                  const failCnt = items.filter((c) => !c.passed).length;
                  return (
                    <button
                      key={cat}
                      onClick={() => setCaseFilter(cat)}
                      style={{
                        padding: "0.35rem 0.8rem", borderRadius: 5, cursor: "pointer", fontSize: "0.8rem", fontWeight: 600,
                        border: "1px solid #334155",
                        background: caseFilter === cat ? testCaseCategoryColor[cat] || "#3b82f6" : "#0f172a",
                        color: caseFilter === cat ? "#fff" : "#94a3b8",
                      }}
                    >
                      {testCaseCategoryIcon[cat] || "📋"} {testCaseCategoryLabel[cat] || cat} ({items.length}{failCnt > 0 && ` ❌${failCnt}`})
                    </button>
                  );
                })}
              </div>

              {/* 测试用例列表 */}
              <div style={{ maxHeight: 500, overflowY: "auto" }}>
                {autoResult.test_cases
                  .filter((c) => caseFilter === "all" || c.category === caseFilter)
                  .map((tc, i) => (
                    <div key={tc.id || i} style={{
                      padding: "0.6rem 0.75rem", marginBottom: "0.4rem", background: "#0f172a", borderRadius: 4,
                      borderLeft: `3px solid ${tc.passed ? "#22c55e" : "#ef4444"}`,
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flex: 1, minWidth: 0 }}>
                          <span style={{ color: tc.passed ? "#22c55e" : "#ef4444", fontSize: "0.9rem" }}>{tc.passed ? "✅" : "❌"}</span>
                          <span style={{ color: "#64748b", fontSize: "0.7rem", fontFamily: "monospace", flexShrink: 0 }}>{tc.id}</span>
                          <span style={{
                            padding: "1px 6px", borderRadius: 3, fontSize: "0.7rem", fontWeight: 700,
                            background: "#1e293b", color: testCaseCategoryColor[tc.category] || "#94a3b8",
                            flexShrink: 0,
                          }}>
                            {testCaseCategoryIcon[tc.category] || "📋"} {testCaseCategoryLabel[tc.category] || tc.category}
                          </span>
                          {tc.method !== "-" && (
                            <span style={{
                              padding: "1px 5px", borderRadius: 3, fontSize: "0.65rem", fontWeight: 700,
                              background: tc.method === "GET" ? "#1e3a5f" : tc.method === "POST" ? "#14532d" : "#3f3f00",
                              color: "#e2e8f0", flexShrink: 0,
                            }}>{tc.method}</span>
                          )}
                          <span style={{ color: "#e2e8f0", fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {tc.name}
                          </span>
                        </div>
                        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexShrink: 0 }}>
                          {tc.status_code > 0 && (
                            <span style={{
                              color: tc.status_code >= 200 && tc.status_code < 400 ? "#22c55e" : "#ef4444",
                              fontWeight: 700, fontFamily: "monospace", fontSize: "0.85rem",
                            }}>{tc.status_code}</span>
                          )}
                          {tc.duration_ms > 0 && (
                            <span style={{ color: "#64748b", fontSize: "0.75rem" }}>{tc.duration_ms}ms</span>
                          )}
                        </div>
                      </div>
                      {/* 详情行 */}
                      <div style={{ marginTop: "0.3rem", fontSize: "0.78rem", display: "flex", gap: "1rem", flexWrap: "wrap" }}>
                        <span style={{ color: "#64748b" }}>期望: <span style={{ color: "#94a3b8" }}>{tc.expected}</span></span>
                        <span style={{ color: "#64748b" }}>实际: <span style={{ color: tc.passed ? "#86efac" : "#fca5a5" }}>{tc.actual}</span></span>
                      </div>
                      {tc.detail && <div style={{ color: "#475569", fontSize: "0.75rem", marginTop: "0.2rem" }}>{tc.detail}</div>}
                      {tc.error && <div style={{ color: "#fca5a5", fontSize: "0.75rem", marginTop: "0.2rem" }}>错误: {tc.error}</div>}
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Tab 1 无用例时的提示 */}
          {resultTab === "cases" && (!autoResult.test_cases || autoResult.test_cases.length === 0) && (
            <div style={{ ...cardStyle, marginBottom: "1rem", textAlign: "center", color: "#64748b" }}>
              暂无测试用例
            </div>
          )}

          {/* ====== Tab 2: 检查项 ====== */}
          {resultTab === "checks" && (
            <>
              {/* 按类别分组统计 */}
              {(() => {
                const categories = Array.from(new Set(autoResult.checks.map((c) => c.category)));
                return (
                  <div style={{ ...cardStyle, marginBottom: "1rem" }}>
                    <h3 style={{ marginBottom: "0.75rem", color: "#94a3b8" }}>📊 检查维度</h3>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      {categories.map((cat) => {
                        const items = autoResult.checks.filter((c) => c.category === cat);
                        const failCnt = items.filter((c) => !c.passed).length;
                        return (
                          <span key={cat} style={{ padding: "0.4rem 0.8rem", background: failCnt > 0 ? "#7f1d1d" : "#14532d", borderRadius: 6, fontSize: "0.8rem", color: failCnt > 0 ? "#fca5a5" : "#86efac" }}>
                            {categoryLabel[cat] || cat}: {items.length - failCnt}/{items.length}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {/* 检查明细 */}
              <div style={cardStyle}>
                <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>🔍 检查明细 ({autoResult.checks.length})</h3>
                {autoResult.checks.map((c, i) => (
                  <div key={i} style={{ padding: "0.6rem 0.75rem", marginBottom: "0.4rem", background: "#0f172a", borderRadius: 4, borderLeft: `3px solid ${c.passed ? "#22c55e" : severityColor[c.severity]}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                        <span style={{ padding: "1px 6px", borderRadius: 3, fontSize: "0.7rem", fontWeight: 700, background: "#1e293b", color: severityColor[c.severity] }}>
                          {categoryLabel[c.category] || c.category}
                        </span>
                        <span style={{ color: "#e2e8f0", fontSize: "0.85rem" }}>{c.name}</span>
                      </div>
                      <span>{c.passed ? "✅" : c.severity === "critical" ? "🔴" : c.severity === "error" ? "❌" : "⚠️"}</span>
                    </div>
                    {c.detail && <div style={{ color: "#94a3b8", fontSize: "0.78rem", marginTop: "0.25rem" }}>{c.detail}</div>}
                    {c.page_url && <div style={{ color: "#475569", fontSize: "0.7rem", marginTop: "0.15rem", fontFamily: "monospace" }}>{c.page_url}</div>}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ====== Tab 3: 爬取详情 ====== */}
          {resultTab === "crawl" && autoResult.crawl && (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>已访问</div>
                  <div style={numberStyle("#e2e8f0")}>{autoResult.crawl.visited_count}</div>
                </div>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>失败</div>
                  <div style={numberStyle("#ef4444")}>{autoResult.crawl.failed_count}</div>
                </div>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>总链接</div>
                  <div style={numberStyle("#38bdf8")}>{autoResult.crawl.total_links}</div>
                </div>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>死链</div>
                  <div style={numberStyle(autoResult.crawl.broken_links_count > 0 ? "#ef4444" : "#22c55e")}>{autoResult.crawl.broken_links_count}</div>
                </div>
                <div style={{ ...cardStyle, textAlign: "center" }}>
                  <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>耗时</div>
                  <div style={numberStyle("#a78bfa")}>{autoResult.crawl.duration_ms}ms</div>
                </div>
              </div>

              {/* 死链列表 */}
              {autoResult.crawl.broken_links && autoResult.crawl.broken_links.length > 0 && (
                <div style={{ ...cardStyle, marginBottom: "1rem" }}>
                  <h3 style={{ color: "#ef4444", marginBottom: "0.75rem" }}>🔗 死链 ({autoResult.crawl.broken_links.length})</h3>
                  {autoResult.crawl.broken_links.slice(0, 20).map((bl, i) => (
                    <div key={i} style={{ padding: "0.5rem", marginBottom: "0.4rem", background: "#0f172a", borderRadius: 4, borderLeft: "3px solid #ef4444" }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "#fca5a5", fontSize: "0.85rem", fontFamily: "monospace" }}>{bl.url.length > 70 ? bl.url.slice(0, 70) + "..." : bl.url}</span>
                        <span style={{ color: "#ef4444", fontWeight: 700, fontSize: "0.85rem" }}>HTTP {bl.status}</span>
                      </div>
                      <div style={{ color: "#64748b", fontSize: "0.75rem" }}>来源: {bl.parent}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* 页面列表 */}
              <div style={cardStyle}>
                <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>📄 爬取页面 ({autoResult.crawl.pages.length})</h3>
                {autoResult.crawl.pages.map((p, i) => (
                  <div key={i} style={{ padding: "0.75rem", marginBottom: "0.5rem", background: "#0f172a", borderRadius: 6, borderLeft: `3px solid ${p.error ? "#ef4444" : p.status >= 400 ? "#f59e0b" : "#22c55e"}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ color: "#e2e8f0", fontSize: "0.9rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {p.title || p.url}
                        </div>
                        <div style={{ color: "#64748b", fontSize: "0.75rem", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {p.url}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexShrink: 0 }}>
                        <span style={{ color: p.status >= 400 ? "#ef4444" : "#22c55e", fontWeight: 700, fontFamily: "monospace", fontSize: "0.85rem" }}>{p.status || "—"}</span>
                        <span style={{ color: "#64748b", fontSize: "0.75rem" }}>{p.response_time_ms}ms</span>
                        <span style={{ color: "#475569", fontSize: "0.7rem" }}>d{p.depth}</span>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.3rem", fontSize: "0.7rem", color: "#64748b" }}>
                      <span>🔗 内链 {p.internal_links_count}</span>
                      <span>🌍 外链 {p.external_links_count}</span>
                      <span>📝 表单 {p.forms_count}</span>
                      <span>🖼️ 图片 {p.images_count}</span>
                      <span>📜 脚本 {p.scripts_count}</span>
                      {p.h1 && p.h1.length > 0 && <span>H1: {p.h1[0]}</span>}
                    </div>
                    {p.error && <div style={{ color: "#fca5a5", fontSize: "0.75rem", marginTop: "0.25rem" }}>{p.error}</div>}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* 截图（所有Tab可见） */}
          {autoResult.screenshots.length > 0 && (
            <div style={{ ...cardStyle, marginTop: "1rem" }}>
              <h3 style={{ marginBottom: "0.75rem", color: "#94a3b8" }}>📸 响应式截图 ({autoResult.screenshots.length})</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "0.75rem" }}>
                {autoResult.screenshots.map((s, i) => (
                  <div key={i} style={{ padding: "0.5rem", background: "#0f172a", borderRadius: 4 }}>
                    <div style={{ color: "#38bdf8", fontSize: "0.8rem", marginBottom: "0.25rem" }}>{s.viewport} ({s.width}px)</div>
                    <div style={{ color: "#64748b", fontSize: "0.7rem", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.path}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* 综合测试报告发送弹窗 */}
      {reportModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
          onClick={() => !sendingReport && setReportModal(false)}>
          <div style={{ background: "#1e293b", borderRadius: 12, padding: "2rem", width: 420, maxWidth: "90%" }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ color: "#38bdf8", marginBottom: "1rem" }}>📧 发送综合测试报告</h3>
            <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "1rem" }}>
              将功能测试、压力测试、边界测试、回归测试和功能分析结果以HTML邮件发送
            </p>
            <input value={reportEmail} onChange={(e) => setReportEmail(e.target.value)} placeholder="recipient@example.com" type="email"
              style={{ width: "100%", padding: "0.75rem", marginBottom: "1rem", background: "#0f172a", border: "1px solid #334155", borderRadius: 6, color: "#e2e8f0", fontSize: "0.9rem" }} />
            {reportResult && <div style={{ marginBottom: "1rem", color: reportResult.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.85rem" }}>{reportResult}</div>}
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
              <button onClick={() => { setReportModal(false); setReportResult(""); }} disabled={sendingReport}
                style={{ padding: "0.5rem 1rem", border: "1px solid #334155", borderRadius: 6, background: "transparent", color: "#94a3b8", cursor: "pointer" }}>取消</button>
              <button onClick={sendReport} disabled={sendingReport || !reportEmail}
                style={{ padding: "0.5rem 1rem", border: "none", borderRadius: 6, background: sendingReport ? "#334155" : "#22c55e", color: "#fff", cursor: "pointer", fontWeight: 600 }}>
                {sendingReport ? "⏳ 发送中..." : "发送报告"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 邮件发送弹窗 */}
      {emailModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
          onClick={() => !sendingEmail && setEmailModal(false)}>
          <div style={{ background: "#1e293b", borderRadius: 12, padding: "2rem", width: 400, maxWidth: "90%" }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ color: "#38bdf8", marginBottom: "1rem" }}>📧 发送测试报告邮件</h3>
            <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "1rem" }}>将扫描结果和 PDF 报告发送到指定邮箱</p>
            <input value={emailAddr} onChange={(e) => setEmailAddr(e.target.value)} placeholder="recipient@example.com" type="email"
              style={{ width: "100%", padding: "0.75rem", marginBottom: "1rem", background: "#0f172a", border: "1px solid #334155", borderRadius: 6, color: "#e2e8f0", fontSize: "0.9rem" }} />
            {emailResult && <div style={{ marginBottom: "1rem", color: emailResult.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.85rem" }}>{emailResult}</div>}
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
              <button onClick={() => { setEmailModal(false); setEmailResult(""); }} disabled={sendingEmail}
                style={{ padding: "0.5rem 1rem", border: "1px solid #334155", borderRadius: 6, background: "transparent", color: "#94a3b8", cursor: "pointer" }}>取消</button>
              <button onClick={sendEmail} disabled={sendingEmail || !emailAddr}
                style={{ padding: "0.5rem 1rem", border: "none", borderRadius: 6, background: sendingEmail ? "#334155" : "#22c55e", color: "#fff", cursor: "pointer", fontWeight: 600 }}>
                {sendingEmail ? "⏳ 发送中..." : "发送"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
