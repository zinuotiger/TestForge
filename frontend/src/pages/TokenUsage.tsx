import { useEffect, useState, useCallback } from "react";

interface Summary {
  total_calls: number;
  success_calls: number;
  failed_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  monthly_cost_usd: number;
  monthly_budget_usd: number;
  budget_used_pct: number;
  budget_remaining_usd: number;
  avg_latency_ms: number;
  budget_alert: boolean;
}

interface ModelStat {
  model: string;
  provider: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  avg_latency_ms: number;
  is_local: boolean;
}

interface SceneStat {
  scene: string;
  calls: number;
  total_tokens: number;
  cost_usd: number;
}

interface TrendItem {
  date: string;
  calls: number;
  tokens: number;
  cost: number;
}

interface RecentRecord {
  timestamp: string;
  provider: string;
  model: string;
  scene: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
  success: boolean;
  error: string;
}

const fmtNum = (n: number) => n.toLocaleString();
const fmtCost = (n: number) => `$${n.toFixed(4)}`;
const fmtToken = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
};

export default function TokenUsage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [models, setModels] = useState<ModelStat[]>([]);
  const [scenes, setScenes] = useState<SceneStat[]>([]);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [recent, setRecent] = useState<RecentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [budgetInput, setBudgetInput] = useState("");
  const [tab, setTab] = useState<"models" | "scenes" | "recent">("models");

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, m, sc, t, r] = await Promise.all([
        fetch("/api/token-usage/summary").then((r) => r.json()),
        fetch("/api/token-usage/by-model").then((r) => r.json()),
        fetch("/api/token-usage/by-scene").then((r) => r.json()),
        fetch("/api/token-usage/trend?days=30").then((r) => r.json()),
        fetch("/api/token-usage/recent?limit=50").then((r) => r.json()),
      ]);
      setSummary(s);
      setModels(m.models || []);
      setScenes(sc.scenes || []);
      setTrend(t.trend || []);
      setRecent(r.records || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const timer = setInterval(fetchAll, 15000);
    return () => clearInterval(timer);
  }, [fetchAll]);

  const updateBudget = async () => {
    const val = parseFloat(budgetInput);
    if (isNaN(val) || val <= 0) return;
    await fetch("/api/token-usage/budget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ monthly_budget_usd: val }),
    });
    setBudgetInput("");
    fetchAll();
  };

  const resetRecords = async () => {
    if (!confirm("确认清空所有用量记录？此操作不可撤销。")) return;
    await fetch("/api/token-usage/reset", { method: "POST" });
    fetchAll();
  };

  if (loading && !summary) {
    return <div style={{ color: "#94a3b8" }}>加载中...</div>;
  }

  const budgetColor = summary!.budget_used_pct >= 80 ? "#ef4444" : summary!.budget_used_pct >= 60 ? "#f59e0b" : "#22c55e";
  const maxTrendCost = Math.max(...trend.map((t) => t.cost), 0.01);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
        <div>
          <h1 style={{ color: "#e2e8f0", fontSize: "1.5rem", marginBottom: "0.25rem" }}>
            Token 用量监控
          </h1>
          <p style={{ color: "#64748b" }}>LLM 调用消耗统计 · 成本分析 · 预算管理</p>
        </div>
        <button
          onClick={fetchAll}
          style={{
            background: "#1e293b", border: "1px solid #334155", borderRadius: 6,
            padding: "0.5rem 1rem", color: "#38bdf8", cursor: "pointer", fontSize: "0.85rem",
          }}
        >
          🔄 刷新
        </button>
      </div>

      {/* 概览卡片 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        <StatCard label="总 Token 消耗" value={fmtToken(summary!.total_tokens)} sub={`输入 ${fmtToken(summary!.total_prompt_tokens)} / 输出 ${fmtToken(summary!.total_completion_tokens)}`} color="#38bdf8" />
        <StatCard label="总调用次数" value={fmtNum(summary!.total_calls)} sub={`✅ ${summary!.success_calls}  ❌ ${summary!.failed_calls}`} color="#a78bfa" />
        <StatCard label="总成本" value={fmtCost(summary!.total_cost_usd)} sub={`本月 ${fmtCost(summary!.monthly_cost_usd)}`} color="#34d399" />
        <StatCard label="平均延迟" value={`${summary!.avg_latency_ms}ms`} sub="单次 LLM 调用" color="#fbbf24" />
      </div>

      {/* 预算进度条 */}
      <div style={{ background: "#1e293b", borderRadius: 8, padding: "1.25rem 1.5rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem", margin: 0 }}>
            💰 月度预算
            {summary!.budget_alert && (
              <span style={{ marginLeft: "0.5rem", color: "#ef4444", fontSize: "0.8rem" }}>⚠️ 预算告警</span>
            )}
          </h3>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input
              type="number"
              placeholder="设置预算 ($)"
              value={budgetInput}
              onChange={(e) => setBudgetInput(e.target.value)}
              style={{
                width: 120, background: "#0f172a", border: "1px solid #334155",
                borderRadius: 4, padding: "0.35rem 0.5rem", color: "#e2e8f0", outline: "none", fontSize: "0.85rem",
              }}
            />
            <button
              onClick={updateBudget}
              style={{
                background: "#0ea5e9", border: "none", borderRadius: 4,
                padding: "0.35rem 0.75rem", color: "white", cursor: "pointer", fontSize: "0.85rem",
              }}
            >
              设置
            </button>
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.85rem" }}>
          <span style={{ color: "#94a3b8" }}>
            已用 <span style={{ color: budgetColor, fontWeight: 700 }}>{fmtCost(summary!.monthly_cost_usd)}</span>
            {" / "}
            <span style={{ color: "#e2e8f0" }}>{fmtCost(summary!.monthly_budget_usd)}</span>
          </span>
          <span style={{ color: budgetColor, fontWeight: 600 }}>{summary!.budget_used_pct}%</span>
        </div>
        <div style={{ width: "100%", height: 10, background: "#0f172a", borderRadius: 5, overflow: "hidden" }}>
          <div style={{
            width: `${Math.min(summary!.budget_used_pct, 100)}%`, height: "100%",
            background: budgetColor, transition: "width 0.5s ease",
          }} />
        </div>
        <div style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "0.4rem" }}>
          剩余 {fmtCost(summary!.budget_remaining_usd)} · 超过 80% 将触发告警
        </div>
      </div>

      {/* 趋势图 */}
      {trend.length > 0 && (
        <div style={{ background: "#1e293b", borderRadius: 8, padding: "1.25rem 1.5rem", marginBottom: "1.5rem" }}>
          <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem", marginBottom: "1rem" }}>📈 每日成本趋势（近 30 天）</h3>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 120, overflowX: "auto" }}>
            {trend.map((d) => (
              <div key={d.date} style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 24, flex: 1, title: `${d.date}: ${fmtCost(d.cost)} / ${d.calls}次` } as any}>
                <div style={{ color: "#64748b", fontSize: "0.65rem", marginBottom: 2 }}>
                  {d.cost > 0 ? `$${d.cost.toFixed(2)}` : ""}
                </div>
                <div style={{
                  width: "100%", maxWidth: 20,
                  height: `${Math.max((d.cost / maxTrendCost) * 80, 2)}px`,
                  background: d.cost > 0 ? "#0ea5e9" : "#334155",
                  borderRadius: "3px 3px 0 0",
                }} />
                <div style={{ color: "#475569", fontSize: "0.6rem", marginTop: 2, transform: "rotate(-45deg)", whiteSpace: "nowrap" }}>
                  {d.date.slice(5)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 切换 */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        {([
          { key: "models", label: `按模型 (${models.length})` },
          { key: "scenes", label: `按场景 (${scenes.length})` },
          { key: "recent", label: `最近调用 (${recent.length})` },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              background: tab === t.key ? "#0ea5e9" : "#1e293b",
              border: `1px solid ${tab === t.key ? "#0ea5e9" : "#334155"}`,
              borderRadius: 6, padding: "0.5rem 1rem",
              color: tab === t.key ? "white" : "#94a3b8",
              cursor: "pointer", fontSize: "0.85rem", fontWeight: 500,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      <div style={{ background: "#1e293b", borderRadius: 8, overflow: "hidden" }}>
        {tab === "models" && (
          <TableView
            headers={["模型", "提供商", "调用次数", "输入Token", "输出Token", "总Token", "成本", "平均延迟"]}
            rows={models.map((m) => [
              <span style={{ color: m.is_local ? "#22c55e" : "#e2e8f0", fontWeight: 500 }}>
                {m.model} {m.is_local && "🏠"}
              </span>,
              <span style={{ color: "#64748b" }}>{m.provider}</span>,
              fmtNum(m.calls),
              fmtToken(m.prompt_tokens),
              fmtToken(m.completion_tokens),
              fmtToken(m.total_tokens),
              m.is_local ? <span style={{ color: "#22c55e" }}>免费</span> : <span style={{ color: "#34d399" }}>{fmtCost(m.cost_usd)}</span>,
              `${m.avg_latency_ms}ms`,
            ])}
          />
        )}

        {tab === "scenes" && (
          <TableView
            headers={["场景", "调用次数", "总Token", "成本", "占比"]}
            rows={scenes.map((s) => {
              const totalCost = scenes.reduce((a, b) => a + b.cost_usd, 0) || 1;
              return [
                <span style={{ color: "#38bdf8", fontWeight: 500 }}>{s.scene}</span>,
                fmtNum(s.calls),
                fmtToken(s.total_tokens),
                <span style={{ color: "#34d399" }}>{fmtCost(s.cost_usd)}</span>,
                <span style={{ color: "#64748b" }}>{((s.cost_usd / totalCost) * 100).toFixed(1)}%</span>,
              ];
            })}
          />
        )}

        {tab === "recent" && (
          <TableView
            headers={["时间", "提供商", "模型", "场景", "Token", "成本", "延迟", "状态"]}
            rows={recent.slice(0, 30).map((r) => [
              <span style={{ color: "#64748b", fontSize: "0.8rem" }}>{r.timestamp.slice(11, 19)}</span>,
              <span style={{ color: "#94a3b8" }}>{r.provider}</span>,
              <span style={{ color: "#e2e8f0", fontSize: "0.85rem" }}>{r.model}</span>,
              <span style={{ color: "#38bdf8", fontSize: "0.85rem" }}>{r.scene}</span>,
              <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{fmtToken(r.total_tokens)}</span>,
              <span style={{ color: "#34d399" }}>{r.cost_usd > 0 ? fmtCost(r.cost_usd) : "—"}</span>,
              <span style={{ color: "#64748b" }}>{r.latency_ms}ms</span>,
              r.success
                ? <span style={{ color: "#22c55e" }}>✅</span>
                : <span style={{ color: "#ef4444" }} title={r.error}>❌</span>,
            ])}
          />
        )}
      </div>

      {/* 底部操作 */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1rem" }}>
        <button
          onClick={resetRecords}
          style={{
            background: "transparent", border: "1px solid #7f1d1d",
            borderRadius: 6, padding: "0.4rem 0.8rem",
            color: "#ef4444", cursor: "pointer", fontSize: "0.8rem",
          }}
        >
          🗑️ 清空记录
        </button>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color: string }) {
  return (
    <div style={{ background: "#1e293b", borderRadius: 8, padding: "1.25rem" }}>
      <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginBottom: "0.4rem" }}>{label}</div>
      <div style={{ color, fontSize: "1.6rem", fontWeight: 800, fontFamily: "monospace" }}>{value}</div>
      {sub && <div style={{ color: "#475569", fontSize: "0.72rem", marginTop: "0.3rem" }}>{sub}</div>}
    </div>
  );
}

function TableView({ headers, rows }: { headers: string[]; rows: any[][] }) {
  if (rows.length === 0) {
    return <div style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>暂无数据</div>;
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ borderBottom: "2px solid #334155" }}>
          {headers.map((h) => (
            <th key={h} style={{ textAlign: "left", padding: "0.7rem 1rem", color: "#94a3b8", fontSize: "0.78rem", fontWeight: 600 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #334155" }}>
            {row.map((cell, j) => (
              <td key={j} style={{ padding: "0.6rem 1rem", fontSize: "0.85rem" }}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
