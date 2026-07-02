import { useEffect, useState } from "react";

interface ScheduleTask {
  task_id: string;
  name: string;
  url: string;
  interval_minutes: number;
  last_run: string | null;
  next_run: string;
  last_pass_rate: number | null;
  enabled: boolean;
  run_count: number;
}

interface Alert {
  timestamp: string;
  task_name: string;
  type: string;
  message: string;
}

export default function ScheduleMonitor() {
  const [tasks, setTasks] = useState<ScheduleTask[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newInterval, setNewInterval] = useState(60);

  const refresh = async () => {
    try {
      const [taskRes, alertRes] = await Promise.all([
        fetch("/api/intelligence/schedule/tasks"),
        fetch("/api/intelligence/schedule/alerts"),
      ]);
      setTasks((await taskRes.json()).tasks || []);
      setAlerts((await alertRes.json()).alerts || []);
    } catch (e) {}
  };

  useEffect(() => { refresh(); }, []);

  const createTask = async () => {
    await fetch("/api/intelligence/schedule/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName, url: newUrl, interval_minutes: newInterval, alert_emails: [] }),
    });
    setShowCreate(false);
    setNewName(""); setNewUrl(""); setNewInterval(60);
    refresh();
  };

  const deleteTask = async (id: string) => {
    await fetch(`/api/intelligence/schedule/tasks/${id}`, { method: "DELETE" });
    refresh();
  };

  const cardStyle: React.CSSProperties = { background: "#1e293b", borderRadius: 8, padding: "1.25rem", marginBottom: "0.75rem" };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h2>⏰ 定时巡检</h2>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={refresh} style={{ padding: "0.5rem 1rem", background: "#334155", border: "none", borderRadius: 6, color: "#e2e8f0", cursor: "pointer" }}>🔄 刷新</button>
          <button onClick={() => setShowCreate(!showCreate)} style={{ padding: "0.5rem 1rem", background: "#3b82f6", border: "none", borderRadius: 6, color: "#fff", cursor: "pointer", fontWeight: 600 }}>+ 新建任务</button>
        </div>
      </div>

      {/* 创建表单 */}
      {showCreate && (
        <div style={{ ...cardStyle, marginBottom: "1rem" }}>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="任务名称" style={{ flex: "1", minWidth: 150, padding: "0.5rem", background: "#0f172a", border: "1px solid #334155", borderRadius: 6, color: "#e2e8f0" }} />
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="OpenAPI URL" style={{ flex: "2", minWidth: 200, padding: "0.5rem", background: "#0f172a", border: "1px solid #334155", borderRadius: 6, color: "#e2e8f0" }} />
            <input type="number" value={newInterval} onChange={(e) => setNewInterval(Number(e.target.value))} placeholder="间隔(分钟)" style={{ width: 100, padding: "0.5rem", background: "#0f172a", border: "1px solid #334155", borderRadius: 6, color: "#e2e8f0" }} />
            <button onClick={createTask} disabled={!newName || !newUrl} style={{ padding: "0.5rem 1rem", background: "#22c55e", border: "none", borderRadius: 6, color: "#fff", cursor: "pointer", fontWeight: 600 }}>创建</button>
          </div>
        </div>
      )}

      {/* 任务列表 */}
      {tasks.length === 0 ? (
        <div style={{ ...cardStyle, textAlign: "center", color: "#64748b" }}>暂无定时任务，点击"新建任务"创建</div>
      ) : (
        tasks.map((t) => (
          <div key={t.task_id} style={{ ...cardStyle, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 600, color: "#38bdf8" }}>{t.name}</div>
              <div style={{ color: "#64748b", fontSize: "0.8rem", fontFamily: "monospace" }}>{t.url.slice(0, 60)}</div>
              <div style={{ display: "flex", gap: "1rem", marginTop: "0.25rem", fontSize: "0.8rem" }}>
                <span style={{ color: "#64748b" }}>每 {t.interval_minutes} 分钟</span>
                <span style={{ color: t.last_pass_rate !== null && t.last_pass_rate < 80 ? "#ef4444" : "#22c55e" }}>
                  {t.last_pass_rate !== null ? `通过率 ${t.last_pass_rate}%` : "未执行"}
                </span>
                <span style={{ color: "#64748b" }}>已运行 {t.run_count} 次</span>
              </div>
            </div>
            <button onClick={() => deleteTask(t.task_id)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: "1.2rem" }}>✕</button>
          </div>
        ))
      )}

      {/* 告警列表 */}
      {alerts.length > 0 && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3 style={{ marginBottom: "0.75rem", color: "#94a3b8" }}>🚨 告警记录</h3>
          {alerts.map((a, i) => (
            <div key={i} style={{ ...cardStyle, borderLeft: `3px solid ${a.type === "error" ? "#ef4444" : "#f59e0b"}` }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#f59e0b", fontWeight: 600 }}>{a.task_name}</span>
                <span style={{ color: "#64748b", fontSize: "0.75rem" }}>{a.timestamp.slice(0, 19)}</span>
              </div>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem", marginTop: "0.25rem" }}>{a.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
