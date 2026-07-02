import { useState } from "react";
import { apiFetch } from "../api";

// ============ 类型定义 ============

interface ToolCall {
  iteration: number;
  tool: string;
  args: Record<string, any>;
  result_preview: string;
}

interface SingleAgentResult {
  status: string;
  summary: string;
  quality_score: number;
  tool_calls: ToolCall[];
  iterations: number;
  error?: string;
}

interface AgentStatus {
  name: string;
  role: string;
  description: string;
  state: string;
  memory: { short_term_count: number; long_term_count: number };
  messages_received: number;
  messages_sent: number;
  actions_count: number;
  recent_actions: any[];
}

interface TimelineEntry {
  agent: string;
  role: string;
  action: string;
  detail: string;
  state: string;
  timestamp: number;
}

interface MultiAgentResult {
  status: string;
  summary: string;
  results: {
    total_sub_tasks: number;
    results: Record<string, any>;
    agent_statuses: Record<string, AgentStatus>;
  };
  agent_statuses: {
    orchestrator: AgentStatus;
    agents: Record<string, AgentStatus>;
  };
  timeline: TimelineEntry[];
  duration_ms: number;
  agent_count: number;
  error?: string;
}

interface LangGraphTimelineEntry {
  node: string;
  action: string;
  detail: string;
  timestamp: number;
}

interface LangGraphResult {
  status: string;
  framework: string;
  quality_score: number;
  review_passed: boolean;
  analysis: { function_count: number; class_count: number; complexity: number; smells: number };
  test_cases: { name: string; type: string; steps: number }[];
  test_count: number;
  execution_result: { exit_code: number; passed: boolean };
  review_feedback: Record<string, any>;
  retry_count: number;
  timeline: LangGraphTimelineEntry[];
  duration_ms: number;
  graph_structure?: { nodes: string[]; edges: string[] };
  error?: string;
}

interface StreamEvent {
  type: string;
  content?: string;
  tool?: string;
  args?: string[];
  result_preview?: string;
  iteration?: number;
  max?: number;
  current?: number;
  message?: string;
  summary?: string;
  status?: string;
  quality_score?: number;
  iterations?: number;
}

type Mode = "single" | "multi" | "langgraph" | "stream";

// ============ 样式 ============

const cardStyle: React.CSSProperties = { background: "#1e293b", borderRadius: 8, padding: "1.5rem" };

const stateColor: Record<string, string> = {
  idle: "#64748b", thinking: "#38bdf8", acting: "#f59e0b",
  waiting: "#a78bfa", done: "#22c55e", error: "#ef4444",
};

const roleColor: Record<string, string> = {
  orchestrator: "#f59e0b", analyst: "#38bdf8", generator: "#22c55e",
  executor: "#a78bfa", reviewer: "#ec4899",
};

const roleIcon: Record<string, string> = {
  orchestrator: "🎭", analyst: "🔍", generator: "🧬",
  executor: "⚡", reviewer: "🛡️",
};

// ============ 主组件 ============

export default function AgentPlayground() {
  const [mode, setMode] = useState<Mode>("langgraph");
  const [code, setCode] = useState("def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b");
  const [task, setTask] = useState("");
  const [running, setRunning] = useState(false);
  const [singleResult, setSingleResult] = useState<SingleAgentResult | null>(null);
  const [multiResult, setMultiResult] = useState<MultiAgentResult | null>(null);
  const [langgraphResult, setLanggraphResult] = useState<LangGraphResult | null>(null);
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([]);
  const [streamText, setStreamText] = useState("");
  const [streamDone, setStreamDone] = useState(false);
  const [error, setError] = useState("");

  const runAgent = async () => {
    setError("");
    setSingleResult(null);
    setMultiResult(null);
    setLanggraphResult(null);
    setStreamEvents([]);
    setStreamText("");
    setStreamDone(false);
    setRunning(true);
    try {
      if (mode === "stream") {
        // 流式模式：用 fetch + ReadableStream 消费 SSE
        const token = localStorage.getItem("testforge_access_token");
        const res = await fetch("/api/intelligence/agent/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ code, task }),
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("无法读取流");

        const decoder = new TextDecoder();
        let buffer = "";
        let currentText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // 解析 SSE 事件（以 data: 开头，\n\n 分隔）
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const evt: StreamEvent = JSON.parse(line.slice(6));

              if (evt.type === "token" && evt.content) {
                currentText += evt.content;
                setStreamText(currentText);
              }

              setStreamEvents((prev) => [...prev, evt]);

              if (evt.type === "done") {
                setStreamDone(true);
              }
            } catch {
              // 忽略解析错误
            }
          }
        }
      } else {
        let endpoint: string;
        if (mode === "single") endpoint = "/api/intelligence/agent/run";
        else if (mode === "multi") endpoint = "/api/intelligence/multi-agent/run";
        else endpoint = "/api/intelligence/langgraph/run";

        const res = await apiFetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, task }),
        });
        const data = await res.json();
        if (mode === "single") {
          setSingleResult(data);
          if (data.status === "error") setError(data.summary || data.error || "Agent 运行失败");
        } else if (mode === "multi") {
          setMultiResult(data);
          if (data.error) setError(data.error);
        } else {
          setLanggraphResult(data);
          if (data.error) setError(data.error);
        }
      }
    } catch (e) {
      setError(`请求失败: ${String(e)}`);
    }
    setRunning(false);
  };

  const toolIcon: Record<string, string> = {
    analyze_code: "🔍", generate_tests: "🧬", execute_tests: "⚡", scan_security: "🛡️", finish: "✅",
  };

  return (
    <div>
      <h2 style={{ marginBottom: "1.5rem" }}>🤖 Agent Playground</h2>

      {/* 模式切换 */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <button
          onClick={() => { setMode("single"); setSingleResult(null); setMultiResult(null); setLanggraphResult(null); setError(""); }}
          style={{
            padding: "0.6rem 1.2rem", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
            border: "1px solid #334155",
            background: mode === "single" ? "#3b82f6" : "#0f172a",
            color: mode === "single" ? "#fff" : "#94a3b8",
          }}
        >
          🔧 单 Agent（ReAct）
        </button>
        <button
          onClick={() => { setMode("multi"); setSingleResult(null); setMultiResult(null); setLanggraphResult(null); setError(""); }}
          style={{
            padding: "0.6rem 1.2rem", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
            border: "1px solid #334155",
            background: mode === "multi" ? "#3b82f6" : "#0f172a",
            color: mode === "multi" ? "#fff" : "#94a3b8",
          }}
        >
          🤝 多 Agent（自研）
        </button>
        <button
          onClick={() => { setMode("langgraph"); setSingleResult(null); setMultiResult(null); setLanggraphResult(null); setStreamEvents([]); setStreamText(""); setStreamDone(false); setError(""); }}
          style={{
            padding: "0.6rem 1.2rem", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
            border: "1px solid #334155",
            background: mode === "langgraph" ? "#7c3aed" : "#0f172a",
            color: mode === "langgraph" ? "#fff" : "#94a3b8",
          }}
        >
          🔷 LangGraph（StateGraph）
        </button>
        <button
          onClick={() => { setMode("stream"); setSingleResult(null); setMultiResult(null); setLanggraphResult(null); setStreamEvents([]); setStreamText(""); setStreamDone(false); setError(""); }}
          style={{
            padding: "0.6rem 1.2rem", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
            border: "1px solid #334155",
            background: mode === "stream" ? "#06b6d4" : "#0f172a",
            color: mode === "stream" ? "#fff" : "#94a3b8",
          }}
        >
          📡 流式输出（SSE）
        </button>
      </div>

      {/* 输入区 */}
      <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
        <div style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
          {mode === "single"
            ? "单 Agent ReAct 模式：LLM 自主决策调用工具（分析→生成→执行→扫描→总结）"
            : mode === "multi"
            ? "多 Agent 协作（自研框架）：Orchestrator 分解任务 → Analyst/Generator/Executor/Reviewer 协作 + 反思自纠"
            : mode === "langgraph"
            ? "LangGraph StateGraph：声明式状态图 + 条件边路由 + 反思循环 + MemorySaver checkpoint"
            : "流式输出：LLM 逐 token 实时推送思考过程（SSE），前端实时展示 Agent 的每个想法和工具调用"}
        </div>

        <div style={{ color: "#64748b", fontSize: "0.8rem", marginBottom: "0.25rem" }}>源代码:</div>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={8}
          style={{
            width: "100%", padding: "0.75rem", marginBottom: "0.75rem", boxSizing: "border-box",
            background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
            color: "#e2e8f0", fontSize: "0.85rem", fontFamily: "monospace",
          }}
        />

        <div style={{ color: "#64748b", fontSize: "0.8rem", marginBottom: "0.25rem" }}>额外任务指令（可选）:</div>
        <input
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="如：重点测试边界值"
          style={{
            width: "100%", padding: "0.5rem", marginBottom: "0.75rem", boxSizing: "border-box",
            background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
            color: "#e2e8f0", fontSize: "0.85rem",
          }}
        />

        <button
          onClick={runAgent}
          disabled={running || !code}
          style={{
            padding: "0.75rem 2rem", border: "none", borderRadius: 8,
            background: running ? "#334155" : "#3b82f6", color: "#fff",
            fontWeight: 700, cursor: running || !code ? "default" : "pointer",
          }}
        >
          {running ? "⏳ Agent 运行中..." : mode === "single" ? "🚀 启动单 Agent" : mode === "multi" ? "🤝 启动多 Agent" : mode === "langgraph" ? "🔷 启动 LangGraph" : "📡 启动流式 Agent"}
        </button>
      </div>

      {error && (
        <div style={{ padding: "0.75rem 1rem", marginBottom: "1rem", background: "#7f1d1d", borderRadius: 8, color: "#fca5a5" }}>
          ⚠️ {error}
        </div>
      )}

      {/* ============ 单 Agent 结果 ============ */}
      {mode === "single" && singleResult && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>状态</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 800, color: singleResult.status === "completed" ? "#22c55e" : "#f59e0b" }}>
                {singleResult.status === "completed" ? "✅ 完成" : singleResult.status === "max_iterations" ? "⏠ 达到上限" : "❌ 错误"}
              </div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>迭代次数</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#38bdf8", fontFamily: "monospace" }}>{singleResult.iterations}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>质量评分</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: singleResult.quality_score >= 80 ? "#22c55e" : singleResult.quality_score >= 60 ? "#f59e0b" : "#ef4444", fontFamily: "monospace" }}>{singleResult.quality_score}/100</div>
            </div>
          </div>

          {singleResult.tool_calls && singleResult.tool_calls.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
              <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>🔧 工具调用链（ReAct 循环）</h3>
              {singleResult.tool_calls.map((tc, i) => (
                <div key={i} style={{ padding: "0.75rem", marginBottom: "0.5rem", background: "#0f172a", borderRadius: 6, borderLeft: "3px solid #3b82f6" }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.25rem" }}>
                    <span style={{ color: "#64748b", fontSize: "0.75rem" }}>迭代 {tc.iteration}</span>
                    <span style={{ fontSize: "1.2rem" }}>{toolIcon[tc.tool] || "🔧"}</span>
                    <span style={{ color: "#38bdf8", fontWeight: 600, fontFamily: "monospace", fontSize: "0.9rem" }}>{tc.tool}()</span>
                  </div>
                  <div style={{ color: "#64748b", fontSize: "0.8rem", fontFamily: "monospace", marginLeft: "1.5rem" }}>参数: {JSON.stringify(Object.keys(tc.args))}</div>
                  <div style={{ color: "#94a3b8", fontSize: "0.8rem", fontFamily: "monospace", marginLeft: "1.5rem", marginTop: "0.25rem" }}>结果: {tc.result_preview.slice(0, 120)}{tc.result_preview.length > 120 ? "..." : ""}</div>
                </div>
              ))}
            </div>
          )}

          {singleResult.summary && (
            <div style={cardStyle}>
              <h3 style={{ marginBottom: "0.75rem", color: "#94a3b8" }}>📝 Agent 总结</h3>
              <div style={{ color: "#e2e8f0", fontSize: "0.9rem", lineHeight: 1.8, whiteSpace: "pre-wrap" }}>{singleResult.summary}</div>
            </div>
          )}
        </>
      )}

      {/* ============ 多 Agent 结果 ============ */}
      {mode === "multi" && multiResult && !multiResult.error && (
        <>
          {/* 概览 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>Agent 数量</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#38bdf8", fontFamily: "monospace" }}>{multiResult.agent_count}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>子任务</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#e2e8f0", fontFamily: "monospace" }}>{multiResult.results?.total_sub_tasks || 0}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>时间线事件</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#a78bfa", fontFamily: "monospace" }}>{multiResult.timeline?.length || 0}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>总耗时</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#22c55e", fontFamily: "monospace" }}>{multiResult.duration_ms}ms</div>
            </div>
          </div>

          {/* Agent 状态卡片 */}
          {multiResult.agent_statuses && (
            <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
              <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>🤝 Agent 协作状态</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "0.75rem" }}>
                {/* Orchestrator */}
                {multiResult.agent_statuses.orchestrator && (
                  <AgentCard agent={multiResult.agent_statuses.orchestrator} />
                )}
                {/* 子 Agent */}
                {Object.entries(multiResult.agent_statuses.agents || {}).map(([role, agent]) => (
                  <AgentCard key={role} agent={agent} />
                ))}
              </div>
            </div>
          )}

          {/* 协作时间线 */}
          {multiResult.timeline && multiResult.timeline.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
              <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>⏱️ 协作时间线</h3>
              {multiResult.timeline.map((entry, i) => (
                <div key={i} style={{
                  padding: "0.5rem 0.75rem", marginBottom: "0.3rem", background: "#0f172a", borderRadius: 4,
                  borderLeft: `3px solid ${roleColor[entry.role] || "#64748b"}`,
                }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <span style={{ fontSize: "1rem" }}>{roleIcon[entry.role] || "🔧"}</span>
                    <span style={{ color: roleColor[entry.role] || "#94a3b8", fontWeight: 600, fontSize: "0.85rem" }}>
                      {entry.agent}
                    </span>
                    <span style={{ color: stateColor[entry.state] || "#64748b", fontSize: "0.7rem", padding: "1px 6px", borderRadius: 3, background: "#1e293b" }}>
                      {entry.state}
                    </span>
                    <span style={{ color: "#64748b", fontSize: "0.8rem" }}>{entry.action}</span>
                  </div>
                  <div style={{ color: "#94a3b8", fontSize: "0.78rem", marginLeft: "1.5rem", marginTop: "0.15rem" }}>
                    {entry.detail}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 总结 */}
          {multiResult.summary && (
            <div style={cardStyle}>
              <h3 style={{ marginBottom: "0.75rem", color: "#94a3b8" }}>📝 协作总结</h3>
              <div style={{ color: "#e2e8f0", fontSize: "0.9rem", lineHeight: 1.8 }}>{multiResult.summary}</div>
            </div>
          )}
        </>
      )}

      {/* ============ LangGraph 结果 ============ */}
      {mode === "langgraph" && langgraphResult && !langgraphResult.error && (
        <>
          {/* 框架标识 */}
          <div style={{ ...cardStyle, marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: "1.5rem" }}>🔷</span>
            <span style={{ color: "#7c3aed", fontWeight: 700, fontSize: "1.1rem" }}>LangGraph StateGraph</span>
            <span style={{ color: "#64748b", fontSize: "0.8rem" }}>| {langgraphResult.framework}</span>
            {langgraphResult.retry_count > 0 && (
              <span style={{ marginLeft: "auto", padding: "2px 8px", borderRadius: 4, background: "#7c3aed22", color: "#a78bfa", fontSize: "0.75rem" }}>
                反思重试 {langgraphResult.retry_count} 次
              </span>
            )}
          </div>

          {/* 概览 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>质量评分</div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: langgraphResult.quality_score >= 80 ? "#22c55e" : langgraphResult.quality_score >= 60 ? "#f59e0b" : "#ef4444", fontFamily: "monospace" }}>
                {langgraphResult.quality_score}/100
              </div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>审查结果</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 800, color: langgraphResult.review_passed ? "#22c55e" : "#ef4444" }}>
                {langgraphResult.review_passed ? "✅ 通过" : "❌ 未通过"}
              </div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>测试用例</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#38bdf8", fontFamily: "monospace" }}>{langgraphResult.test_count}</div>
            </div>
            <div style={{ ...cardStyle, textAlign: "center" }}>
              <div style={{ color: "#94a3b8", marginBottom: "0.5rem", fontSize: "0.8rem" }}>耗时</div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#22c55e", fontFamily: "monospace" }}>{langgraphResult.duration_ms}ms</div>
            </div>
          </div>

          {/* StateGraph 结构 */}
          {langgraphResult.graph_structure && (
            <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
              <h3 style={{ marginBottom: "0.75rem", color: "#94a3b8" }}>🔷 StateGraph 结构</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
                <span style={{ padding: "4px 10px", borderRadius: 4, background: "#0f172a", color: "#64748b", fontSize: "0.75rem" }}>START</span>
                <span style={{ fontSize: "0.75rem", color: "#475569" }}>→ analyze → generate → execute → review</span>
                <span style={{ padding: "4px 10px", borderRadius: 4, background: "#7c3aed22", color: "#a78bfa", fontSize: "0.75rem" }}>END</span>
              </div>
              <div style={{ marginTop: "0.5rem", color: "#475569", fontSize: "0.72rem", fontFamily: "monospace" }}>
                review → END (pass) | review → increment_retry → generate (fail, retry &lt; max)
              </div>
            </div>
          )}

          {/* 时间线 */}
          {langgraphResult.timeline && langgraphResult.timeline.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: "1.5rem" }}>
              <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>⏱️ LangGraph 执行时间线</h3>
              {langgraphResult.timeline.map((entry, i) => (
                <div key={i} style={{
                  padding: "0.5rem 0.75rem", marginBottom: "0.3rem", background: "#0f172a", borderRadius: 4,
                  borderLeft: `3px solid ${entry.node === "reviewer" ? "#ec4899" : entry.node === "generator" ? "#22c55e" : entry.node === "executor" ? "#a78bfa" : "#38bdf8"}`,
                }}>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <span style={{ fontSize: "0.85rem" }}>
                      {entry.node === "analyst" ? "🔍" : entry.node === "generator" ? "🧬" : entry.node === "executor" ? "⚡" : entry.node === "reviewer" ? "🛡️" : "🔄"}
                    </span>
                    <span style={{ color: "#7c3aed", fontWeight: 600, fontSize: "0.8rem", fontFamily: "monospace" }}>
                      {entry.node}
                    </span>
                    <span style={{ color: "#64748b", fontSize: "0.75rem" }}>{entry.action}</span>
                  </div>
                  <div style={{ color: "#94a3b8", fontSize: "0.78rem", marginLeft: "1.5rem", marginTop: "0.15rem" }}>
                    {entry.detail}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 审查反馈 */}
          {langgraphResult.review_feedback && Object.keys(langgraphResult.review_feedback).length > 0 && (
            <div style={cardStyle}>
              <h3 style={{ marginBottom: "0.75rem", color: "#94a3b8" }}>🛡️ 审查反馈</h3>
              <pre style={{ color: "#e2e8f0", fontSize: "0.8rem", lineHeight: 1.6, overflow: "auto", maxHeight: 300 }}>
                {JSON.stringify(langgraphResult.review_feedback, null, 2)}
              </pre>
            </div>
          )}
        </>
      )}

      {/* ============ 流式输出结果 ============ */}
      {mode === "stream" && (streamEvents.length > 0 || streamText) && (
        <>
          {/* 实时思考输出 */}
          {streamText && (
            <div style={{ ...cardStyle, marginBottom: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                <h3 style={{ color: "#06b6d4", margin: 0 }}>📡 LLM 实时思考</h3>
                {running && (
                  <span style={{ color: "#06b6d4", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#06b6d4", animation: "pulse 1s infinite" }} />
                    生成中...
                  </span>
                )}
                {streamDone && <span style={{ color: "#22c55e", fontSize: "0.8rem" }}>✅ 完成</span>}
              </div>
              <div style={{
                color: "#e2e8f0", fontSize: "0.88rem", lineHeight: 1.8, whiteSpace: "pre-wrap",
                background: "#0f172a", padding: "1rem", borderRadius: 6, minHeight: 60,
                border: "1px solid #334155",
              }}>
                {streamText}
                {running && <span style={{ color: "#06b6d4" }}>▋</span>}
              </div>
            </div>
          )}

          {/* 事件流 */}
          {streamEvents.length > 0 && (
            <div style={cardStyle}>
              <h3 style={{ marginBottom: "1rem", color: "#94a3b8" }}>⚡ 事件流（SSE）</h3>
              {streamEvents.map((evt, i) => {
                const colors: Record<string, string> = {
                  start: "#06b6d4", thought_start: "#38bdf8", token: "#475569",
                  thought_end: "#38bdf8", tool_call: "#22c55e", tool_result: "#a78bfa",
                  iteration: "#f59e0b", done: "#22c55e", error: "#ef4444",
                };
                const icons: Record<string, string> = {
                  start: "🚀", thought_start: "💭", token: "", thought_end: "✅",
                  tool_call: "🔧", tool_result: "📋", iteration: "🔄", done: "🎉", error: "❌",
                };
                return (
                  <div key={i} style={{
                    padding: "0.4rem 0.6rem", marginBottom: "0.25rem", background: "#0f172a",
                    borderRadius: 4, borderLeft: `3px solid ${colors[evt.type] || "#334155"}`,
                  }}>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      {icons[evt.type] && <span style={{ fontSize: "0.85rem" }}>{icons[evt.type]}</span>}
                      <span style={{ color: colors[evt.type] || "#94a3b8", fontWeight: 600, fontSize: "0.75rem", fontFamily: "monospace" }}>
                        {evt.type}
                      </span>
                      {evt.iteration && (
                        <span style={{ color: "#64748b", fontSize: "0.7rem" }}>iter {evt.iteration}</span>
                      )}
                      {evt.tool && (
                        <span style={{ color: "#22c55e", fontSize: "0.8rem", fontFamily: "monospace" }}>{evt.tool}()</span>
                      )}
                      {evt.current && evt.max && (
                        <span style={{ color: "#f59e0b", fontSize: "0.7rem" }}>{evt.current}/{evt.max}</span>
                      )}
                    </div>
                    {(evt.message || evt.result_preview || evt.summary) && (
                      <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginLeft: "1.2rem", marginTop: "0.15rem" }}>
                        {evt.message || (evt.result_preview ? `结果: ${evt.result_preview}` : evt.summary)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ============ Agent 状态卡片子组件 ============

function AgentCard({ agent }: { agent: AgentStatus }) {
  return (
    <div style={{
      padding: "0.75rem", background: "#0f172a", borderRadius: 6,
      border: `1px solid ${roleColor[agent.role] || "#334155"}33`,
    }}>
      <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", marginBottom: "0.4rem" }}>
        <span style={{ fontSize: "1.2rem" }}>{roleIcon[agent.role] || "🔧"}</span>
        <span style={{ color: roleColor[agent.role] || "#94a3b8", fontWeight: 700, fontSize: "0.9rem" }}>
          {agent.name}
        </span>
        <span style={{
          marginLeft: "auto", padding: "1px 6px", borderRadius: 3, fontSize: "0.65rem", fontWeight: 700,
          background: "#1e293b", color: stateColor[agent.state] || "#64748b",
        }}>
          {agent.state}
        </span>
      </div>
      <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: "0.4rem" }}>{agent.description}</div>
      <div style={{ display: "flex", gap: "0.75rem", fontSize: "0.7rem", color: "#475569" }}>
        <span>📨 {agent.messages_received}</span>
        <span>📤 {agent.messages_sent}</span>
        <span>⚡ {agent.actions_count}</span>
        <span>🧠 {agent.memory.short_term_count}</span>
      </div>
    </div>
  );
}
