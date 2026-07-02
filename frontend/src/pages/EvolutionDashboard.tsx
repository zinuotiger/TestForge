import { useEffect, useState, useCallback } from "react";

// ========== 类型 ==========
interface StrategyInfo {
  name: string;
  calls: number;
  cases: number;
  success_rate: number;
  avg_duration_ms: number;
  recommended_weight: number;
  cost_per_call?: number;
}

interface KnowledgeItem {
  id: number;
  category: string;
  title: string;
  score: number;
  use_count?: number;
  content?: any;
}

interface EvolutionReport {
  summary: {
    total_events: number;
    total_knowledge: number;
    total_strategies: number;
    primary_strategy: string;
  };
  strategies: StrategyInfo[];
  recent_event_distribution: Record<string, number>;
  recent_knowledge: KnowledgeItem[];
}

interface EvolutionStats {
  total_knowledge: number;
  strategies: StrategyInfo[];
  recent_events: Record<string, number>;
  total_events_100: number;
}

// ========== 颜色/常量 ==========
const strategyColors: Record<string, string> = {
  template: "#22c55e",
  property: "#a855f7",
  ai: "#3b82f6",
  search: "#f59e0b",
  traffic: "#ef4444",
};

const strategyIcons: Record<string, string> = {
  template: "\u{1F4CB}",
  property: "\u{1F9EA}",
  ai: "\u{1F916}",
  search: "\u{1F50D}",
  traffic: "\u{1F310}",
};

const eventLabels: Record<string, string> = {
  execution_complete: "执行完成",
  heal_success: "治愈成功",
  heal_failure: "治愈失败",
  flaky_detected: "Flaky检测",
  strategy_called: "策略调用",
  knowledge_extracted: "知识提取",
  cross_project_match: "跨项目匹配",
  health_degraded: "健康下降",
  health_improved: "健康提升",
};

const cardStyle: React.CSSProperties = {
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: 8,
  padding: "1.25rem",
};

const statValueStyle: React.CSSProperties = {
  fontSize: "2rem",
  fontWeight: 800,
  color: "#e2e8f0",
  lineHeight: 1.2,
};

const statLabelStyle: React.CSSProperties = {
  fontSize: "0.8rem",
  color: "#64748b",
  marginTop: "0.25rem",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

export default function EvolutionDashboard() {
  const [stats, setStats] = useState<EvolutionStats | null>(null);
  const [report, setReport] = useState<EvolutionReport | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([]);
  const [knowledgeQuery, setKnowledgeQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statsRes, reportRes, knowledgeRes] = await Promise.all([
        fetch("/api/v1/evolution/stats").then((r) => r.json()),
        fetch("/api/v1/evolution/report").then((r) => r.json()),
        fetch("/api/v1/evolution/knowledge?limit=20").then((r) => r.json()),
      ]);
      setStats(statsRes);
      setReport(reportRes);
      setKnowledge(knowledgeRes.results || []);
    } catch (e: any) {
      setError(e.message || "获取进化数据失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const searchKnowledge = useCallback(async () => {
    if (!knowledgeQuery.trim()) {
      fetchAll();
      return;
    }
    try {
      const res = await fetch(
        "/api/v1/evolution/knowledge?query=" + encodeURIComponent(knowledgeQuery) + "&limit=20"
      ).then((r) => r.json());
      setKnowledge(res.results || []);
    } catch (e: any) {
      setError(e.message || "搜索失败");
    }
  }, [knowledgeQuery, fetchAll]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  if (loading && !stats) {
    return (
      <div style={{ color: "#64748b", textAlign: "center", padding: "4rem 0" }}>
        加载进化数据中...
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div style={{ color: "#ef4444", textAlign: "center", padding: "4rem 0" }}>
        {error}
        <br />
        <button
          onClick={fetchAll}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: 6,
            color: "#e2e8f0",
            cursor: "pointer",
          }}
        >
          重试
        </button>
      </div>
    );
  }

  const primaryStrategy = stats?.strategies?.[0]?.name || "template";

  return (
    <div>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#e2e8f0", marginBottom: "0.25rem" }}>
        自进化引擎
      </h1>
      <p style={{ color: "#64748b", fontSize: "0.85rem", marginBottom: "1.5rem" }}>
        策略自适应 · 知识库构建 · 跨项目迁移 · 闭环改进
      </p>

      {/* 概览卡片 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: "0.75rem",
          marginBottom: "1.5rem",
        }}
      >
        <div style={cardStyle}>
          <div style={statValueStyle}>{stats?.total_knowledge || 0}</div>
          <div style={statLabelStyle}>知识条目</div>
        </div>
        <div style={cardStyle}>
          <div style={statValueStyle}>{stats?.total_events_100 || 0}</div>
          <div style={statLabelStyle}>近期事件</div>
        </div>
        <div style={cardStyle}>
          <div style={{ ...statValueStyle, fontSize: "1.5rem", color: strategyColors[primaryStrategy] || "#38bdf8" }}>
            {strategyIcons[primaryStrategy] || "\u{1F3AF}"} {primaryStrategy}
          </div>
          <div style={statLabelStyle}>主推策略</div>
        </div>
        <div style={cardStyle}>
          <div style={{ ...statValueStyle, fontSize: "1.5rem" }}>
            {report ? report.summary.total_strategies : 0}
          </div>
          <div style={statLabelStyle}>有效策略数</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
        {/* 策略表现 */}
        <div style={cardStyle}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#e2e8f0", marginBottom: "0.75rem" }}>
            {'🎯'} 策略表现权重
          </h3>
          {stats?.strategies && stats.strategies.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {stats.strategies.map((s) => {
                const successPct = Math.round(s.success_rate * 100);
                return (
                  <div key={s.name}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "0.2rem",
                      }}
                    >
                      <span style={{ color: "#cbd5e1", fontSize: "0.85rem", fontWeight: 600 }}>
                        {strategyIcons[s.name] || "\u{1F3AF}"} {s.name}
                      </span>
                      <span style={{ color: "#64748b", fontSize: "0.75rem" }}>
                        {s.cases} 用例 · {(s.success_rate * 100).toFixed(0)}% · {s.avg_duration_ms.toFixed(0)}ms
                      </span>
                    </div>
                    <div
                      style={{
                        height: 6,
                        background: "#0f172a",
                        borderRadius: 3,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: Math.max(Math.round((s.recommended_weight || s.success_rate) * 100), 2) + "%",
                          background: strategyColors[s.name] || "#64748b",
                          borderRadius: 3,
                          transition: "width 0.3s",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ color: "#475569", fontSize: "0.85rem" }}>暂无策略数据，执行测试后自动生成</p>
          )}
        </div>

        {/* 近期事件分布 */}
        <div style={cardStyle}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#e2e8f0", marginBottom: "0.75rem" }}>
            {'📊'} 近期事件分布
          </h3>
          {stats?.recent_events && Object.keys(stats.recent_events).length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
              {Object.entries(stats.recent_events)
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <div
                    key={type}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "0.35rem 0",
                      borderBottom: "1px solid #1e293b",
                    }}
                  >
                    <span style={{ color: "#94a3b8", fontSize: "0.8rem" }}>
                      {eventLabels[type] || type}
                    </span>
                    <span
                      style={{
                        background: "#334155",
                        color: "#e2e8f0",
                        padding: "2px 8px",
                        borderRadius: 10,
                        fontSize: "0.75rem",
                        fontWeight: 600,
                      }}
                    >
                      {count}
                    </span>
                  </div>
                ))}
            </div>
          ) : (
            <p style={{ color: "#475569", fontSize: "0.85rem" }}>暂无事件，执行测试后自动记录</p>
          )}
        </div>
      </div>

      {/* 进化报告摘要 */}
      {report && (
        <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#e2e8f0", marginBottom: "0.75rem" }}>
            {'📋'} 进化报告摘要
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
            <div>
              <div style={statLabelStyle}>总事件数</div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#e2e8f0" }}>
                {report.summary.total_events.toLocaleString()}
              </div>
            </div>
            <div>
              <div style={statLabelStyle}>知识库条目</div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#e2e8f0" }}>
                {report.summary.total_knowledge.toLocaleString()}
              </div>
            </div>
            <div>
              <div style={statLabelStyle}>主推策略</div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, color: strategyColors[report.summary.primary_strategy] || "#38bdf8" }}>
                {strategyIcons[report.summary.primary_strategy] || ""} {report.summary.primary_strategy}
              </div>
            </div>
          </div>

          {report.recent_knowledge && report.recent_knowledge.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
            {'🔍'} 洞察与趋势
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.5rem" }}>
                {report.recent_knowledge.map((k) => (
                  <span
                    key={k.id}
                    style={{
                      background: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: 6,
                      padding: "0.3rem 0.6rem",
                      fontSize: "0.75rem",
                      color: "#94a3b8",
                    }}
                  >
                    [{k.category}] {k.title.length > 40 ? k.title.slice(0, 40) + "..." : k.title}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 知识库 */}
      <div style={cardStyle}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "0.75rem",
          }}
        >
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#e2e8f0", margin: 0 }}>
            {'💡'} 优化建议
          </h3>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              type="text"
              placeholder="搜索知识..."
              value={knowledgeQuery}
              onChange={(e) => setKnowledgeQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchKnowledge()}
              style={{
                padding: "0.4rem 0.75rem",
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 6,
                color: "#e2e8f0",
                fontSize: "0.8rem",
                width: 200,
              }}
            />
            <button
              onClick={searchKnowledge}
              style={{
                padding: "0.4rem 0.75rem",
                background: "#2563eb",
                border: "none",
                borderRadius: 6,
                color: "#fff",
                cursor: "pointer",
                fontSize: "0.8rem",
                fontWeight: 600,
              }}
            >
              搜索
            </button>
          </div>
        </div>

        {knowledge.length > 0 ? (
          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {knowledge.map((k) => (
                <div
                  key={k.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "0.5rem 0.75rem",
                    background: "#0f172a",
                    border: "1px solid #1e293b",
                    borderRadius: 6,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: "#cbd5e1", fontSize: "0.85rem", fontWeight: 500 }}>
                      [{k.category}] {k.title}
                    </div>
                    {k.content && typeof k.content === "object" && (
                      <div style={{ color: "#475569", fontSize: "0.7rem", marginTop: "0.15rem" }}>
                        {JSON.stringify(k.content).slice(0, 120)}
                        {JSON.stringify(k.content).length > 120 ? "..." : ""}
                      </div>
                    )}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexShrink: 0 }}>
                    <span style={{ color: "#64748b", fontSize: "0.7rem" }}>
                      评分: {typeof k.score === "number" ? k.score.toFixed(2) : k.score}
                    </span>
                    {k.use_count !== undefined && (
                      <span style={{ color: "#475569", fontSize: "0.7rem" }}>
                        使用: {k.use_count}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p style={{ color: "#475569", fontSize: "0.85rem", textAlign: "center", padding: "2rem 0" }}>
            知识库为空，执行测试后将自动积累
          </p>
        )}
      </div>
    </div>
  );
}
