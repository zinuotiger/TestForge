import { useState } from "react";

const TEST_TYPES = [
  { key: "unit", label: "单元测试" },
  { key: "integration", label: "集成测试" },
  { key: "e2e", label: "E2E 测试" },
  { key: "performance", label: "性能测试" },
  { key: "security", label: "安全扫描" },
  { key: "contract", label: "契约测试" },
  { key: "mutation", label: "变异测试" },
  { key: "chaos", label: "混沌工程" },
];

export default function ExecutionCenter() {
  const [selected, setSelected] = useState<string[]>(["unit", "integration", "e2e"]);
  const [strategy, setStrategy] = useState("smart");
  const [llmMode, setLlmMode] = useState("api");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const toggle = (key: string) =>
    setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));

  const trigger = async () => {
    setRunning(true);
    setLogs([]);
    setResult(null);

    const res = await fetch("/api/executions/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: ".", strategy, test_types: selected, llm_mode: llmMode }),
    });
    const data = await res.json();
    const runId = data.run_id;

    // 轮询状态
    const poll = setInterval(async () => {
      const r = await fetch(`/api/executions/${runId}`);
      const d = await r.json();
      setLogs(d.logs || []);
      if (d.status === "passed" || d.status === "failed") {
        clearInterval(poll);
        setResult(d);
        setRunning(false);
      }
    }, 800);
  };

  return (
    <div>
      <h2 style={{ marginBottom: "1.5rem" }}>🚀 执行中心</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        {/* 测试类型选择 */}
        <div style={{ background: "#1e293b", borderRadius: 8, padding: "1.5rem" }}>
          <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>测试类型</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            {TEST_TYPES.map((t) => (
              <label
                key={t.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.5rem",
                  borderRadius: 6,
                  background: selected.includes(t.key) ? "#1e3a5f" : "#0f172a",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(t.key)}
                  onChange={() => toggle(t.key)}
                />
                {t.label}
              </label>
            ))}
          </div>
        </div>

        {/* 策略选择 */}
        <div style={{ background: "#1e293b", borderRadius: 8, padding: "1.5rem" }}>
          <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>执行策略</h3>
          {[
            { key: "smoke", label: "🔥 冒烟 (5min)", desc: "核心路径快速验证" },
            { key: "smart", label: "🧠 智能 (TIA)", desc: "仅执行变更影响的测试" },
            { key: "full", label: "📦 全量 (2h)", desc: "全部 49 阶段完整执行" },
          ].map((s) => (
            <div
              key={s.key}
              onClick={() => setStrategy(s.key)}
              style={{
                padding: "0.75rem",
                marginBottom: "0.5rem",
                borderRadius: 6,
                background: strategy === s.key ? "#1e3a5f" : "#0f172a",
                cursor: "pointer",
                border: strategy === s.key ? "1px solid #3b82f6" : "1px solid transparent",
              }}
            >
              <div style={{ fontWeight: 600 }}>{s.label}</div>
              <div style={{ color: "#64748b", fontSize: "0.85rem" }}>{s.desc}</div>
            </div>
          ))}

          <h3 style={{ margin: "1rem 0", color: "#94a3b8" }}>LLM 引擎</h3>
          <div style={{ display: "flex", gap: "1rem" }}>
            {[
              { key: "api", label: "☁️ API 云端" },
              { key: "local", label: "🏠 本地 Ollama" },
            ].map((m) => (
              <button
                key={m.key}
                onClick={() => setLlmMode(m.key)}
                style={{
                  flex: 1,
                  padding: "0.5rem",
                  borderRadius: 6,
                  border: llmMode === m.key ? "1px solid #3b82f6" : "1px solid #334155",
                  background: llmMode === m.key ? "#1e3a5f" : "#0f172a",
                  color: "#e2e8f0",
                  cursor: "pointer",
                }}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 启动按钮 */}
      <button
        onClick={trigger}
        disabled={running}
        style={{
          marginTop: "1.5rem",
          padding: "1rem 3rem",
          border: "none",
          borderRadius: 8,
          background: running ? "#334155" : "#22c55e",
          color: "#fff",
          fontSize: "1.1rem",
          fontWeight: 700,
          cursor: running ? "default" : "pointer",
          width: "100%",
        }}
      >
        {running ? "⏳ 执行中..." : "🚀 开始执行"}
      </button>

      {/* 日志/结果 */}
      {(logs.length > 0 || result) && (
        <div
          style={{
            marginTop: "1.5rem",
            background: "#0f172a",
            borderRadius: 8,
            padding: "1rem",
            maxHeight: 400,
            overflow: "auto",
            fontFamily: "monospace",
            fontSize: "0.85rem",
          }}
        >
          {logs.map((l, i) => (
            <div key={i} style={{ padding: "2px 0", color: "#94a3b8" }}>
              {l}
            </div>
          ))}
          {result && (
            <div
              style={{
                marginTop: "1rem",
                padding: "1rem",
                borderRadius: 6,
                background: result.status === "passed" ? "#14532d" : "#7f1d1d",
                fontWeight: 700,
              }}
            >
              {result.status === "passed" ? "✅ 全部通过" : "❌ 执行失败"} — 耗时{" "}
              {result.duration_ms}ms
            </div>
          )}
        </div>
      )}
    </div>
  );
}
