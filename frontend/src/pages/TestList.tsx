import { useEffect, useState } from "react";

interface TestCase {
  id: string;
  name: string;
  type: string;
  tags: string[];
  status: string;
  flaky_score: number;
  health_score: number;
  created_by: string;
}

const TYPE_COLORS: Record<string, string> = {
  functional: "#38bdf8",
  boundary: "#a78bfa",
  api: "#34d399",
  e2e: "#fbbf24",
  unit: "#60a5fa",
  performance: "#f87171",
};

const STATUS_COLORS: Record<string, string> = {
  active: "#22c55e",
  quarantine: "#f59e0b",
  deprecated: "#64748b",
};

export default function TestList() {
  const [tests, setTests] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: "all", type: "all", q: "" });

  useEffect(() => {
    fetch("/api/tests/")
      .then((r) => r.json())
      .then((d) => {
        setTests(d.items || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filtered = tests.filter((t) => {
    if (filter.status !== "all" && t.status !== filter.status) return false;
    if (filter.type !== "all" && t.type !== filter.type) return false;
    if (filter.q && !t.name.toLowerCase().includes(filter.q.toLowerCase())) return false;
    return true;
  });

  const stats = {
    total: tests.length,
    active: tests.filter((t) => t.status === "active").length,
    quarantine: tests.filter((t) => t.status === "quarantine").length,
    avgHealth: tests.length
      ? Math.round(tests.reduce((s, t) => s + t.health_score, 0) / tests.length)
      : 0,
  };

  if (loading) {
    return <div style={{ color: "#94a3b8" }}>加载中...</div>;
  }

  return (
    <div>
      <h1 style={{ color: "#e2e8f0", fontSize: "1.5rem", marginBottom: "0.25rem" }}>
        测试用例列表
      </h1>
      <p style={{ color: "#64748b", marginBottom: "1.5rem" }}>
        管理所有测试用例，支持筛选、克隆、隔离
      </p>

      {/* 统计卡片 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        {[
          { label: "总测试", value: stats.total, color: "#e2e8f0" },
          { label: "活跃", value: stats.active, color: "#22c55e" },
          { label: "隔离", value: stats.quarantine, color: "#f59e0b" },
          { label: "平均健康度", value: `${stats.avgHealth}`, color: "#38bdf8" },
        ].map((s) => (
          <div key={s.label} style={{ background: "#1e293b", borderRadius: 8, padding: "1.25rem" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginBottom: "0.25rem" }}>{s.label}</div>
            <div style={{ color: s.color, fontSize: "1.5rem", fontWeight: 700, fontFamily: "monospace" }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* 筛选栏 */}
      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem" }}>
        <input
          placeholder="搜索测试名称..."
          value={filter.q}
          onChange={(e) => setFilter({ ...filter, q: e.target.value })}
          style={{
            flex: 1, background: "#1e293b", border: "1px solid #334155",
            borderRadius: 6, padding: "0.5rem 0.75rem", color: "#e2e8f0", outline: "none",
          }}
        />
        <select
          value={filter.status}
          onChange={(e) => setFilter({ ...filter, status: e.target.value })}
          style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6, padding: "0.5rem", color: "#e2e8f0" }}
        >
          <option value="all">全部状态</option>
          <option value="active">活跃</option>
          <option value="quarantine">隔离</option>
          <option value="deprecated">废弃</option>
        </select>
        <select
          value={filter.type}
          onChange={(e) => setFilter({ ...filter, type: e.target.value })}
          style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6, padding: "0.5rem", color: "#e2e8f0" }}
        >
          <option value="all">全部类型</option>
          <option value="functional">功能</option>
          <option value="boundary">边界</option>
          <option value="api">API</option>
          <option value="e2e">E2E</option>
          <option value="unit">单元</option>
        </select>
      </div>

      {/* 测试列表 */}
      <div style={{ background: "#1e293b", borderRadius: 8, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #334155" }}>
              {["名称", "类型", "状态", "Flaky", "健康度", "来源", "操作"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "0.75rem 1rem", color: "#94a3b8", fontSize: "0.8rem", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>
                  暂无测试用例，前往测试设计器创建
                </td>
              </tr>
            ) : (
              filtered.map((t) => (
                <tr key={t.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "0.75rem 1rem", color: "#e2e8f0", fontWeight: 500 }}>{t.name}</td>
                  <td style={{ padding: "0.75rem 1rem" }}>
                    <span style={{
                      background: (TYPE_COLORS[t.type] || "#64748b") + "22",
                      color: TYPE_COLORS[t.type] || "#64748b",
                      padding: "0.2rem 0.5rem", borderRadius: 4, fontSize: "0.75rem", fontWeight: 600,
                    }}>
                      {t.type}
                    </span>
                  </td>
                  <td style={{ padding: "0.75rem 1rem" }}>
                    <span style={{ color: STATUS_COLORS[t.status] || "#64748b", fontSize: "0.8rem" }}>● {t.status}</span>
                  </td>
                  <td style={{ padding: "0.75rem 1rem", color: t.flaky_score > 0.1 ? "#f59e0b" : "#22c55e", fontFamily: "monospace", fontSize: "0.85rem" }}>
                    {(t.flaky_score * 100).toFixed(1)}%
                  </td>
                  <td style={{ padding: "0.75rem 1rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <div style={{ width: 60, height: 6, background: "#334155", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{
                          width: `${t.health_score}%`, height: "100%",
                          background: t.health_score > 80 ? "#22c55e" : t.health_score > 60 ? "#f59e0b" : "#ef4444",
                        }} />
                      </div>
                      <span style={{ color: "#94a3b8", fontSize: "0.8rem", fontFamily: "monospace" }}>{t.health_score}</span>
                    </div>
                  </td>
                  <td style={{ padding: "0.75rem 1rem", color: "#64748b", fontSize: "0.8rem" }}>{t.created_by}</td>
                  <td style={{ padding: "0.75rem 1rem" }}>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <button
                        onClick={() => _cloneTest(t.id)}
                        style={{ background: "#334155", border: "none", borderRadius: 4, padding: "0.3rem 0.6rem", color: "#38bdf8", cursor: "pointer", fontSize: "0.75rem" }}
                      >
                        克隆
                      </button>
                      {t.status === "active" && (
                        <button
                          onClick={() => _quarantineTest(t.id)}
                          style={{ background: "#334155", border: "none", borderRadius: 4, padding: "0.3rem 0.6rem", color: "#f59e0b", cursor: "pointer", fontSize: "0.75rem" }}
                        >
                          隔离
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

async function _cloneTest(id: string) {
  const r = await fetch(`/api/tests/${id}/clone`, { method: "POST" });
  if (r.ok) {
    alert("克隆成功");
    window.location.reload();
  }
}

async function _quarantineTest(id: string) {
  const r = await fetch(`/api/tests/${id}/quarantine`, { method: "POST" });
  if (r.ok) {
    alert("已隔离");
    window.location.reload();
  }
}
