import { useEffect, useState } from "react";

interface PriorityItem {
  test: string;
  priority: string;
  score: number;
}

interface ImpactResult {
  changed_files: string[];
  affected_tests: string[];
  affected_functions: string[];
  total_tests: number;
  selected_count: number;
  acceleration: string;
  priority: PriorityItem[];
  message?: string;
}

const PRIORITY_COLORS: Record<string, string> = {
  P0: "#ef4444",
  P1: "#f59e0b",
  P2: "#22c55e",
};

export default function ImpactAnalysis() {
  const [result, setResult] = useState<ImpactResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [ref, setRef] = useState("HEAD~1");
  const [error, setError] = useState("");

  const runAnalysis = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`/api/executions/analyze/impact?ref=${encodeURIComponent(ref)}`, {
        method: "POST",
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "分析失败");
      setResult(data);
    } catch (e: any) {
      setError(e.message || "分析失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runAnalysis();
  }, []);

  const accelNum = result?.acceleration ? parseFloat(result.acceleration) : 0;

  return (
    <div>
      <h1 style={{ color: "#e2e8f0", fontSize: "1.5rem", marginBottom: "0.25rem" }}>
        测试影响分析 (TIA)
      </h1>
      <p style={{ color: "#64748b", marginBottom: "1.5rem" }}>
        Git diff → 依赖图 → 只跑受影响测试，实现 CI 加速
      </p>

      {/* 输入栏 */}
      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1.5rem" }}>
        <input
          value={ref}
          onChange={(e) => setRef(e.target.value)}
          placeholder="Git ref，如 HEAD~1"
          style={{
            flex: 1, background: "#1e293b", border: "1px solid #334155",
            borderRadius: 6, padding: "0.6rem 0.9rem", color: "#e2e8f0", outline: "none",
            fontFamily: "monospace",
          }}
        />
        <button
          onClick={runAnalysis}
          disabled={loading}
          style={{
            background: "#0ea5e9", border: "none", borderRadius: 6,
            padding: "0.6rem 1.5rem", color: "white", cursor: loading ? "wait" : "pointer",
            fontWeight: 600,
          }}
        >
          {loading ? "分析中..." : "重新分析"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#7f1d1d22", border: "1px solid #ef4444", borderRadius: 6, padding: "1rem", color: "#ef4444", marginBottom: "1rem" }}>
          ❌ {error}
        </div>
      )}

      {result?.message && !result.changed_files.length && (
        <div style={{ background: "#1e293b", borderRadius: 8, padding: "2rem", textAlign: "center", color: "#64748b" }}>
          {result.message}
        </div>
      )}

      {result && result.changed_files.length > 0 && (
        <>
          {/* 加速概览 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
            {[
              { label: "变更文件", value: result.changed_files.length, color: "#fbbf24" },
              { label: "受影响测试", value: result.selected_count, color: "#38bdf8" },
              { label: "全量测试", value: result.total_tests, color: "#64748b" },
              { label: "加速比", value: result.acceleration, color: accelNum > 5 ? "#22c55e" : "#94a3b8" },
            ].map((s) => (
              <div key={s.label} style={{ background: "#1e293b", borderRadius: 8, padding: "1.25rem", textAlign: "center" }}>
                <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginBottom: "0.4rem" }}>{s.label}</div>
                <div style={{ color: s.color, fontSize: "1.8rem", fontWeight: 800, fontFamily: "monospace" }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* 变更文件列表 */}
          <div style={{ background: "#1e293b", borderRadius: 8, padding: "1.25rem", marginBottom: "1.5rem" }}>
            <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem", marginBottom: "0.75rem" }}>📁 变更文件 ({result.changed_files.length})</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
              {result.changed_files.map((f) => (
                <span key={f} style={{
                  background: "#334155", color: "#cbd5e1",
                  padding: "0.3rem 0.6rem", borderRadius: 4, fontSize: "0.8rem", fontFamily: "monospace",
                }}>
                  {f}
                </span>
              ))}
            </div>
          </div>

          {/* 受影响测试优先级 */}
          {result.priority.length > 0 && (
            <div style={{ background: "#1e293b", borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid #334155" }}>
                <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem" }}>🎯 受影响测试优先级 ({result.priority.length})</h3>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #334155" }}>
                    {["优先级", "测试", "关联分数"].map((h) => (
                      <th key={h} style={{ textAlign: "left", padding: "0.6rem 1rem", color: "#94a3b8", fontSize: "0.8rem" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.priority.slice(0, 50).map((p, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #334155" }}>
                      <td style={{ padding: "0.6rem 1rem" }}>
                        <span style={{
                          background: (PRIORITY_COLORS[p.priority] || "#64748b") + "22",
                          color: PRIORITY_COLORS[p.priority] || "#64748b",
                          padding: "0.2rem 0.5rem", borderRadius: 4, fontSize: "0.75rem", fontWeight: 700,
                        }}>
                          {p.priority}
                        </span>
                      </td>
                      <td style={{ padding: "0.6rem 1rem", color: "#e2e8f0", fontFamily: "monospace", fontSize: "0.85rem" }}>{p.test}</td>
                      <td style={{ padding: "0.6rem 1rem", color: "#64748b", fontFamily: "monospace" }}>{p.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {!loading && !result && !error && (
        <div style={{ color: "#64748b" }}>点击"重新分析"开始 TIA 分析</div>
      )}
    </div>
  );
}
