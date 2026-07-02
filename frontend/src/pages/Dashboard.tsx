import { useEffect, useState, useRef } from "react";

interface StageEvent {
  stage_id: string;
  name: string;
  status: "pending" | "running" | "passed" | "failed";
  progress_pct?: number;
  duration_s?: number;
}

// 与后端 executions.py 的 STAGES 保持一致
const ALL_STAGES = [
  { id: "01", name: "预处理", layer: "L1" },
  { id: "02", name: "静态分析", layer: "L1" },
  { id: "08", name: "策略路由", layer: "L2" },
  { id: "09", name: "测试生成", layer: "L2" },
  { id: "16", name: "单元测试", layer: "L3" },
  { id: "22", name: "安全扫描", layer: "L3" },
  { id: "30", name: "TIA分析", layer: "L4" },
  { id: "31", name: "Flaky检测", layer: "L4" },
  { id: "33", name: "健康度评分", layer: "L5" },
  { id: "43", name: "汇总评分", layer: "L6" },
];

const statusColors: Record<string, string> = {
  pending: "#334155",
  running: "#3b82f6",
  passed: "#22c55e",
  failed: "#ef4444",
  skipped: "#f59e0b",
};

export default function Dashboard() {
  const [stages, setStages] = useState<Record<string, StageEvent>>({});
  const [logs, setLogs] = useState<string[]>([]);
  const [metrics, setMetrics] = useState({ passed: 0, failed: 0, running: 0, coverage: 0 });
  const [health, setHealth] = useState<string>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 健康检查
    fetch("/api/health")
      .then((r) => r.json())
      .then(() => setHealth("connected"))
      .catch(() => setHealth("disconnected"));

    // WebSocket 连接
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${location.host}/ws/events`);
    wsRef.current = ws;

    ws.onopen = () => setHealth("live");
    ws.onclose = () => setHealth("disconnected");

    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);

      switch (event.type) {
        case "stage_start":
          setStages((prev) => ({
            ...prev,
            [event.data.stage_id]: { ...event.data, status: "running", progress_pct: 0 },
          }));
          setMetrics((m) => ({ ...m, running: m.running + 1 }));
          setLogs((l) => [...l, `▶ ${event.data.name} 开始`]);
          break;

        case "stage_progress":
          setStages((prev) => ({
            ...prev,
            [event.data.stage_id]: {
              ...prev[event.data.stage_id],
              progress_pct: event.data.progress_pct,
            },
          }));
          break;

        case "stage_complete":
          setStages((prev) => ({
            ...prev,
            [event.data.stage_id]: {
              ...event.data,
              status: "passed",
              duration_s: event.data.duration_s,
            },
          }));
          setMetrics((m) => ({
            ...m,
            running: Math.max(0, m.running - 1),
            passed: m.passed + 1,
          }));
          setLogs((l) => [...l, `✅ ${event.data.name} 完成 (${event.data.duration_s}s)`]);
          break;

        case "stage_error":
          setStages((prev) => ({
            ...prev,
            [event.data.stage_id]: { ...event.data, status: "failed" },
          }));
          setMetrics((m) => ({
            ...m,
            running: Math.max(0, m.running - 1),
            failed: m.failed + 1,
          }));
          setLogs((l) => [...l, `❌ ${event.data.name} 失败: ${event.data.error}`]);
          break;

        case "resource_snapshot":
          setLogs((l) => [
            ...l.slice(-99),
            `💻 CPU:${event.data.cpu_pct}% RAM:${event.data.mem_gb}GB`,
          ]);
          break;
      }
    };

    return () => ws.close();
  }, []);

  // 自动滚动日志
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const triggerRun = async (strategy: string) => {
    setStages({});
    setLogs([]);
    setMetrics({ passed: 0, failed: 0, running: 0, coverage: 0 });
    await fetch("/api/executions/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: ".", strategy }),
    });
  };

  const statusIcon = (status: string) =>
    status === "passed" ? "✅" : status === "running" ? "▶" : status === "failed" ? "❌" : "⬜";

  return (
    <div>
      {/* 状态栏 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: health === "live" ? "#22c55e" : health === "connected" ? "#f59e0b" : "#ef4444",
            }}
          />
          <span style={{ color: "#94a3b8" }}>
            {health === "live" ? "实时连接" : health === "connected" ? "已连接" : "断开"}
          </span>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={() => triggerRun("smoke")} style={btnStyle}>
            🔥 冒烟
          </button>
          <button onClick={() => triggerRun("smart")} style={{ ...btnStyle, background: "#3b82f6" }}>
            🚀 智能执行
          </button>
          <button onClick={() => triggerRun("full")} style={btnStyle}>
            📦 全量
          </button>
        </div>
      </div>

      {/* 主体：阶段进度 + 指标 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: "1.5rem" }}>
        {/* 阶段进度 */}
        <div style={{ background: "#1e293b", borderRadius: 8, padding: "1rem" }}>
          <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>📊 流水线阶段</h3>
          {ALL_STAGES.map((s) => {
            const st = stages[s.id];
            return (
              <div
                key={s.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.5rem 0.5rem",
                  borderBottom: "1px solid #1e293b",
                  fontFamily: "monospace",
                }}
              >
                <span style={{ width: 24, textAlign: "center" }}>
                  {statusIcon(st?.status || "pending")}
                </span>
                <span style={{ color: "#64748b", width: 30 }}>{s.id}</span>
                <span style={{ flex: 1 }}>{s.name}</span>
                {st?.status === "running" && st.progress_pct !== undefined && (
                  <div
                    style={{
                      width: 120,
                      height: 6,
                      background: "#334155",
                      borderRadius: 3,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${st.progress_pct}%`,
                        height: "100%",
                        background: "#3b82f6",
                        borderRadius: 3,
                        transition: "width 0.3s",
                      }}
                    />
                  </div>
                )}
                {st?.duration_s !== undefined && (
                  <span style={{ color: "#64748b", fontSize: "0.8rem", width: 50, textAlign: "right" }}>
                    {st.duration_s}s
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* 实时指标 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ background: "#1e293b", borderRadius: 8, padding: "1rem" }}>
            <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>📈 实时指标</h3>
            <Metric label="通过" value={metrics.passed} color="#22c55e" />
            <Metric label="失败" value={metrics.failed} color="#ef4444" />
            <Metric label="运行中" value={metrics.running} color="#3b82f6" />
            <Metric label="覆盖率" value={`${metrics.coverage}%`} color="#38bdf8" />
          </div>

          {/* 日志流 */}
          <div
            style={{
              background: "#0f172a",
              borderRadius: 8,
              padding: "1rem",
              maxHeight: 300,
              overflow: "auto",
              fontFamily: "monospace",
              fontSize: "0.8rem",
            }}
          >
            <h3 style={{ marginBottom: "0.5rem", color: "#94a3b8" }}>📜 日志</h3>
            {logs.slice(-20).map((l, i) => (
              <div key={i} style={{ color: l.includes("❌") ? "#ef4444" : "#94a3b8", padding: "2px 0" }}>
                {l}
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0" }}>
      <span style={{ color: "#94a3b8" }}>{label}</span>
      <span style={{ fontWeight: 700, color, fontFamily: "monospace", fontSize: "1.2rem" }}>
        {value}
      </span>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: "0.5rem 1rem",
  border: "none",
  borderRadius: 6,
  background: "#334155",
  color: "#e2e8f0",
  cursor: "pointer",
  fontWeight: 600,
  fontSize: "0.9rem",
};
