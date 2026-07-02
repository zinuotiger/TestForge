import { useEffect, useState } from "react";

interface ReportSummary {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  pass_rate: number;
  total_test_cases: number;
}

interface ReportData {
  timestamp: string;
  summary: ReportSummary;
  latest_run: Record<string, any> | null;
  recent_runs: Record<string, any>[];
  formats: string[];
}

export default function Reports() {
  const [report, setReport] = useState<ReportData | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetch("/api/reports/latest")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setReport)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div style={{ padding: "2rem", color: "#ef4444" }}>加载失败: {error}</div>;
  if (!report) return <div style={{ padding: "2rem", color: "#94a3b8" }}>加载中...</div>;

  const { summary } = report;

  const cardStyle: React.CSSProperties = {
    background: "#1e293b",
    borderRadius: 8,
    padding: "1.5rem",
    textAlign: "center",
  };

  const numberStyle = (color: string): React.CSSProperties => ({
    fontSize: "2rem",
    fontWeight: 800,
    color,
    fontFamily: "monospace",
  });

  return (
    <div>
      <h2 style={{ marginBottom: "1.5rem" }}>📋 测试报告</h2>

      {/* 时间戳 */}
      <div style={{ color: "#64748b", fontSize: "0.85rem", marginBottom: "1rem" }}>
        生成时间: {report.timestamp}
      </div>

      {/* 摘要卡片 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <div style={cardStyle}>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>执行总数</div>
          <div style={numberStyle("#e2e8f0")}>{summary.total}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>通过</div>
          <div style={numberStyle("#22c55e")}>{summary.passed}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>失败</div>
          <div style={numberStyle("#ef4444")}>{summary.failed}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>用例数</div>
          <div style={numberStyle("#38bdf8")}>{summary.total_test_cases}</div>
        </div>
      </div>

      {/* 详情 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "1rem",
        }}
      >
        <div style={cardStyle}>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>通过率</div>
          <div style={numberStyle("#22c55e")}>{summary.pass_rate}%</div>
        </div>
        <div style={cardStyle}>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>错误数</div>
          <div style={numberStyle("#f59e0b")}>{summary.errors}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>最近执行</div>
          <div style={numberStyle("#38bdf8")}>{report.recent_runs.length}</div>
        </div>
      </div>

      {/* 下载 — 只链接后端实际存在的端点 */}
      <div
        style={{
          marginTop: "1.5rem",
          display: "flex",
          gap: "1rem",
          justifyContent: "center",
        }}
      >
        <a
          href="/api/reports/html"
          style={{
            padding: "0.75rem 2rem",
            background: "#1e293b",
            borderRadius: 8,
            color: "#38bdf8",
            textDecoration: "none",
            fontWeight: 600,
          }}
        >
          📥 HTML
        </a>
        <a
          href="/api/reports/latest"
          style={{
            padding: "0.75rem 2rem",
            background: "#1e293b",
            borderRadius: 8,
            color: "#38bdf8",
            textDecoration: "none",
            fontWeight: 600,
          }}
        >
          📥 JSON
        </a>
      </div>
    </div>
  );
}
