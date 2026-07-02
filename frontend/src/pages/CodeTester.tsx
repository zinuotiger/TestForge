import { useState } from "react";

// ============ 类型定义 ============

interface CodeTestSummary {
  analysis: { functions: number; classes: number; complexity: string };
  tests: { generated: number; executed: number; passed: number; failed: number; pass_rate: number };
  security: { risks_found: number };
  overall_score: number;
  language: string;
}

interface CodeTestResult {
  status: string;
  analysis: { function_count: number; class_count: number; complexity: string; smells: number };
  generated_test_count: number;
  test_cases: { name: string; type: string; steps: number }[];
  execution: { exit_code: number; total: number; passed: number; failed: number; output: string; details: string };
  security: { risks_found: number; risks: any[] };
  summary: CodeTestSummary;
  duration_ms: number;
  error: string;
}

interface GenerateResult {
  count: number;
  test_cases: { name: string; type: string; steps: number }[];
  pytest_code: string;
}

// ============ 样式 ============

const cardStyle: React.CSSProperties = {
  background: "#1e293b", borderRadius: 8, padding: "1.5rem",
};

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "0.75rem",
  background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
  color: "#e2e8f0", fontSize: "0.85rem", fontFamily: "monospace",
};

const btnPrimary: React.CSSProperties = {
  padding: "0.75rem 2rem", border: "none", borderRadius: 6,
  background: "#3b82f6", color: "#fff", fontWeight: 700, cursor: "pointer",
};

const btnSecondary: React.CSSProperties = {
  ...btnPrimary, background: "#334155",
};

const labelStyle: React.CSSProperties = {
  color: "#94a3b8", fontSize: "0.8rem", marginBottom: "0.4rem", fontWeight: 600,
};

const statStyle = (color: string): React.CSSProperties => ({
  fontSize: "1.5rem", fontWeight: 800, color, fontFamily: "monospace",
});

// ============ 组件 ============

export default function CodeTester() {
  const [code, setCode] = useState("def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b");
  const [language, setLanguage] = useState("python");
  const [funcName, setFuncName] = useState("");
  const [folderPath, setFolderPath] = useState("");
  const [mode, setMode] = useState<"comprehensive" | "generate" | "execute" | "project">("comprehensive");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CodeTestResult | null>(null);
  const [generateResult, setGenerateResult] = useState<GenerateResult | null>(null);
  const [projectResult, setProjectResult] = useState<any>(null);
  const [execCode, setExecCode] = useState("");
  const [error, setError] = useState("");

  // 综合测试
  const runComprehensive = async () => {
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await fetch("/api/code/comprehensive-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, language, function_name: funcName }),
      });
      const data = await res.json();
      setResult(data);
      if (data.status === "error") setError(data.error);
    } catch (e) {
      setError(`请求失败: ${String(e)}`);
    }
    setLoading(false);
  };

  // 仅生成
  const runGenerate = async () => {
    setLoading(true); setError(""); setGenerateResult(null);
    try {
      const res = await fetch("/api/code/generate-only", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, language, function_name: funcName }),
      });
      const data = await res.json();
      setGenerateResult(data);
      setExecCode(data.pytest_code || "");
    } catch (e) {
      setError(`生成失败: ${String(e)}`);
    }
    setLoading(false);
  };

  // 仅执行
  const runExecute = async () => {
    if (!execCode) { setError("请先生成测试代码或粘贴测试代码"); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch("/api/code/execute-only", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: execCode, language, timeout: 60 }),
      });
      const data = await res.json();
      const partial: CodeTestResult = {
        status: "completed", analysis: { function_count: 0, class_count: 0, complexity: "", smells: 0 }, generated_test_count: 0, test_cases: [],
        execution: data, security: { risks_found: 0, risks: [] }, summary: {} as CodeTestSummary, duration_ms: 0, error: "",
      };
      setResult(partial);
    } catch (e) {
      setError(`执行失败: ${String(e)}`);
    }
    setLoading(false);
  };

  // 项目文件夹测试
  const runProject = async () => {
    if (!folderPath) { setError("请输入项目文件夹路径"); return; }
    setLoading(true); setError(""); setProjectResult(null);
    try {
      const res = await fetch("/api/code/project-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_path: folderPath, language, timeout: 300 }),
      });
      const data = await res.json();
      setProjectResult(data);
    } catch (e) {
      setError(`项目测试失败: ${String(e)}`);
    }
    setLoading(false);
  };

  const s = result?.summary;
  const exec = result?.execution;
  const scoreColor = s ? (s.overall_score >= 80 ? "#22c55e" : s.overall_score >= 60 ? "#f59e0b" : "#ef4444") : "#94a3b8";

  return (
    <div style={{ color: "#e2e8f0" }}>
      <h1 style={{ fontSize: "1.5rem", marginBottom: "0.3rem" }}>🧬 代码测试</h1>
      <p style={{ color: "#64748b", marginBottom: "1.5rem", fontSize: "0.9rem" }}>
        粘贴源代码 → AI 分析 + 生成 + pytest 真实执行 → 出报告
      </p>

      {/* 模式选择 */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        {(["comprehensive", "generate", "execute", "project"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: "0.5rem 1.25rem", borderRadius: 6, border: "none", cursor: "pointer",
              background: mode === m ? "#3b82f6" : "#1e293b", color: mode === m ? "#fff" : "#94a3b8",
              fontWeight: mode === m ? 700 : 500, fontSize: "0.85rem",
            }}
          >
            {m === "comprehensive" ? "🔬 综合测试" : m === "generate" ? "🧬 仅生成" : m === "execute" ? "⚡ 仅执行" : "📁 项目测试"}
          </button>
        ))}
      </div>

      {/* 输入区 */}
      <div style={cardStyle}>
        <div style={labelStyle}>语言</div>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          style={{ ...inputStyle, width: "auto", marginBottom: "1rem", padding: "0.4rem 0.75rem" }}
        >
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="typescript">TypeScript</option>
          <option value="java">Java</option>
          <option value="go">Go</option>
        </select>

        {(mode === "project") && (
          <div>
            <div style={labelStyle}>项目文件夹路径</div>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
              <input
                placeholder="C:\path\to\your\project"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                style={{ ...inputStyle, flex: 1 }}
              />
            </div>
            <p style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "-0.5rem", marginBottom: "1rem" }}>
              自动扫描所有 .py 文件，逐个进行分析 → 生成 → 执行 → 安全扫描
            </p>
          </div>
        )}

{mode !== "project" && (<>
        <div style={labelStyle}>源代码</div>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={10}
          style={inputStyle}
          placeholder="粘贴你的源代码..."
        />
        </>)}

        <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", alignItems: "center" }}>
          <input
            placeholder="重点函数名（可选）"
            value={funcName}
            onChange={(e) => setFuncName(e.target.value)}
            style={{ ...inputStyle, width: "200px", padding: "0.5rem 0.75rem" }}
          />
          <button onClick={mode === "comprehensive" ? runComprehensive : mode === "generate" ? runGenerate : mode === "execute" ? runExecute : runProject} disabled={loading} style={loading ? btnSecondary : btnPrimary}>
            {loading ? "⏳ 执行中..." : mode === "comprehensive" ? "🚀 一键测试" : mode === "generate" ? "🧬 生成测试" : mode === "execute" ? "⚡ 执行测试" : "📁 项目测试"}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ ...cardStyle, marginTop: "1rem", border: "1px solid #ef4444", color: "#ef4444" }}>❌ {error}</div>
      )}

      {projectResult && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3 style={{ color: "#e2e8f0", fontSize: "1.1rem", marginBottom: "0.75rem" }}>
            ✅ 项目测试结果 ({projectResult.total_files} 个文件)
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            {projectResult.files?.map((f: any) => (
              <div key={f.filepath} style={{
                ...cardStyle,
                borderLeft: `4px solid ${f.status === "completed" ? (f.summary?.pass_rate >= 80 ? "#22c55e" : f.summary?.pass_rate >= 50 ? "#f59e0b" : "#ef4444") : "#ef4444"}`,
                padding: "0.75rem 1rem",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span style={{ color: "#cbd5e1", fontWeight: 600, fontSize: "0.85rem" }}>{f.filename}</span>
                    {f.summary?.functions > 0 && (
                      <span style={{ marginLeft: "1rem", color: "#64748b", fontSize: "0.75rem" }}>
                        {f.summary.functions} 函数 | {f.summary.test_count} 测试 | 通过 {f.summary.passed}/{f.summary.passed + f.summary.failed}
                      </span>
                    )}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {f.status === "completed" ? (
                      <span style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: "0.75rem", fontWeight: 600,
                        background: f.summary?.pass_rate >= 80 ? "#14532d" : f.summary?.pass_rate >= 50 ? "#422006" : "#451a03",
                        color: f.summary?.pass_rate >= 80 ? "#86efac" : f.summary?.pass_rate >= 50 ? "#fde68a" : "#fca5a5",
                      }}>
                        {f.summary?.pass_rate ?? 0}%
                      </span>
                    ) : (
                      <span style={{ color: "#ef4444", fontSize: "0.75rem" }}>{f.error || "失败"}</span>
                    )}
                    <span style={{ color: "#475569", fontSize: "0.7rem" }}>{(f.duration_ms / 1000).toFixed(1)}s</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 综合测试结果 */}
      {result && mode === "comprehensive" && (
        <div style={{ marginTop: "1rem" }}>
          {/* 评分卡片 */}
          <div style={{ ...cardStyle, textAlign: "center", marginBottom: "1rem", background: `linear-gradient(135deg, ${scoreColor}22, #1e293b)` }}>
            <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>综合评分</div>
            <div style={{ fontSize: "3rem", fontWeight: 800, color: scoreColor }}>{s?.overall_score ?? "—"}</div>
            <div style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "0.5rem" }}>
              耗时 {result.duration_ms}ms | 语言 {s?.language}
            </div>
          </div>

          {/* 详情卡片 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem" }}>
            <div style={cardStyle}>
              <div style={labelStyle}>📊 分析</div>
              <div>函数 <b style={{ color: "#38bdf8" }}>{result.analysis?.function_count ?? 0}</b></div>
              <div>类 <b style={{ color: "#38bdf8" }}>{result.analysis?.class_count ?? 0}</b></div>
              <div>复杂度 <b style={{ color: "#a78bfa" }}>{result.analysis?.complexity ?? "—"}</b></div>
            </div>
            <div style={cardStyle}>
              <div style={labelStyle}>🧪 测试</div>
              <div style={statStyle(exec && exec.passed > 0 ? "#22c55e" : "#94a3b8")}>
                {exec?.passed ?? 0}<span style={{ fontSize: "0.9rem", color: "#64748b" }}>/{exec?.total ?? 0}</span>
              </div>
              <div style={{ color: "#ef4444", fontSize: "0.85rem" }}>失败 {exec?.failed ?? 0}</div>
              <div style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                生成 {result.generated_test_count} 个用例
              </div>
            </div>
            <div style={cardStyle}>
              <div style={labelStyle}>🔒 安全</div>
              <div style={statStyle(result.security?.risks_found ? "#ef4444" : "#22c55e")}>
                {result.security?.risks_found ?? 0}
              </div>
              <div style={{ color: "#64748b", fontSize: "0.8rem" }}>风险点</div>
            </div>
          </div>

          {/* 执行详情 */}
          {exec && (
            <div style={{ ...cardStyle, marginTop: "0.75rem" }}>
              <div style={labelStyle}>📝 执行输出</div>
              <pre style={{
                background: "#0f172a", padding: "1rem", borderRadius: 6, overflow: "auto", maxHeight: 300,
                fontSize: "0.75rem", color: "#94a3b8", fontFamily: "monospace",
              }}>
                {exec.details || exec.output || "无输出"}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* 生成模式 */}
      {generateResult && mode === "generate" && (
        <div style={{ marginTop: "1rem" }}>
          <div style={cardStyle}>
            <div style={labelStyle}>✅ 已生成 {generateResult.count} 个测试用例</div>
            {generateResult.test_cases.map((tc, i) => (
              <div key={i} style={{ color: "#94a3b8", fontSize: "0.85rem", padding: "0.25rem 0" }}>
                • <b style={{ color: "#38bdf8" }}>{tc.name}</b> — {tc.type} ({tc.steps} 步)
              </div>
            ))}
          </div>

          <div style={{ ...cardStyle, marginTop: "0.75rem" }}>
            <div style={labelStyle}>📝 生成的测试代码</div>
            <textarea
              value={execCode}
              onChange={(e) => setExecCode(e.target.value)}
              rows={12}
              style={{ ...inputStyle, fontSize: "0.78rem", marginBottom: "0.75rem" }}
            />
            <button onClick={() => { setMode("execute"); }} style={btnPrimary}>
              ⚡ 执行这段测试代码
            </button>
          </div>
        </div>
      )}

      {/* 执行模式 */}
      {result && mode === "execute" && exec && (
        <div style={{ marginTop: "1rem" }}>
          <div style={cardStyle}>
            <div style={labelStyle}>⚡ 执行结果</div>
            <div style={{ display: "flex", gap: "2rem" }}>
              <div>
                <div style={statStyle(exec.passed > 0 ? "#22c55e" : "#94a3b8")}>{exec.passed ?? 0}</div>
                <div style={{ color: "#64748b", fontSize: "0.8rem" }}>通过</div>
              </div>
              <div>
                <div style={statStyle(exec.failed > 0 ? "#ef4444" : "#94a3b8")}>{exec.failed ?? 0}</div>
                <div style={{ color: "#64748b", fontSize: "0.8rem" }}>失败</div>
              </div>
              <div>
                <div style={statStyle("#a78bfa")}>{exec.exit_code ?? "—"}</div>
                <div style={{ color: "#64748b", fontSize: "0.8rem" }}>Exit Code</div>
              </div>
            </div>
          </div>
          <div style={{ ...cardStyle, marginTop: "0.75rem" }}>
            <div style={labelStyle}>📝 输出</div>
            <pre style={{ background: "#0f172a", padding: "1rem", borderRadius: 6, maxHeight: 300, overflow: "auto", fontSize: "0.75rem", color: "#94a3b8", fontFamily: "monospace" }}>
              {exec.details || exec.output || "无输出"}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
