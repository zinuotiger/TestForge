import { useState, useEffect } from "react";
import SmtpConfigPanel from "../components/SmtpConfigPanel";
interface Provider {
  id: string;
  name: string;
  icon: string;
  models: string[];
  configured: boolean;
  is_default: boolean;
  is_local?: boolean;
}

interface TestResult {
  provider: string;
  status: string;
  latency_ms: number;
  model: string;
  error?: string;
}

export default function Settings() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [fallbackChain, setFallbackChain] = useState<string[]>([]);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch("/api/settings/providers")
      .then((r) => r.json())
      .then((d) => {
        setProviders(d.providers);
        setFallbackChain(d.fallback_chain);
      });
  }, []);

  const testProvider = async (p: Provider) => {
    setTesting((prev) => ({ ...prev, [p.id]: true }));
    try {
      const res = await fetch("/api/settings/providers/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: p.id,
          api_key: apiKeys[p.id] || "",
          model: p.models[0],
        }),
      });
      const data = await res.json();
      setTestResults((prev) => ({ ...prev, [p.id]: data }));
    } catch (e) {
      setTestResults((prev) => ({
        ...prev,
        [p.id]: { provider: p.id, status: "failed", latency_ms: 0, model: "", error: String(e) },
      }));
    }
    setTesting((prev) => ({ ...prev, [p.id]: false }));
  };

  const statusBadge = (r: TestResult | undefined) => {
    if (!r) return null;
    const colors: Record<string, string> = {
      connected: "#22c55e",
      failed: "#ef4444",
      not_configured: "#64748b",
    };
    const labels: Record<string, string> = {
      connected: "已连接",
      failed: "失败",
      not_configured: "未配置",
    };
    return (
      <span style={{ color: colors[r.status] || "#64748b", fontSize: "0.85rem", fontWeight: 600 }}>
        {labels[r.status] || r.status}
        {r.latency_ms > 0 && r.status === "connected" && (
          <span style={{ color: "#94a3b8" }}> · {r.latency_ms}ms</span>
        )}
      </span>
    );
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h2>⚙️ LLM 设置</h2>
        <span style={{ color: "#94a3b8", fontSize: "0.9rem" }}>
          降级链: {fallbackChain.length > 0 ? fallbackChain.join(" → ") : "未配置"}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1rem" }}>
        {providers.map((p) => (
          <div
            key={p.id}
            style={{
              background: "#1e293b",
              borderRadius: 10,
              padding: "1.25rem",
              border: p.is_default ? "1px solid #3b82f6" : "1px solid #334155",
            }}
          >
            {/* 头部 */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontSize: "1.5rem" }}>{p.icon}</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "1rem" }}>{p.name}</div>
                  <div style={{ color: "#64748b", fontSize: "0.8rem" }}>{p.id}</div>
                </div>
              </div>
              {p.is_default && (
                <span style={{
                  background: "#1e3a5f", color: "#3b82f6",
                  padding: "2px 8px", borderRadius: 4, fontSize: "0.75rem", fontWeight: 600,
                }}>
                  默认
                </span>
              )}
              {p.is_local && (
                <span style={{
                  background: "#14532d", color: "#22c55e",
                  padding: "2px 8px", borderRadius: 4, fontSize: "0.75rem", fontWeight: 600,
                }}>
                  本地
                </span>
              )}
            </div>

            {/* API Key 输入 */}
            {!p.is_local && (
              <div style={{ marginBottom: "0.75rem" }}>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <input
                    type={showKey[p.id] ? "text" : "password"}
                    value={apiKeys[p.id] || ""}
                    onChange={(e) => setApiKeys({ ...apiKeys, [p.id]: e.target.value })}
                    placeholder={p.configured ? "已配置 (使用环境变量)" : "输入 API Key"}
                    style={{
                      flex: 1, padding: "0.5rem", background: "#0f172a",
                      border: "1px solid #334155", borderRadius: 6,
                      color: "#e2e8f0", fontSize: "0.85rem",
                    }}
                  />
                  <button
                    onClick={() => setShowKey({ ...showKey, [p.id]: !showKey[p.id] })}
                    style={{
                      padding: "0.5rem", background: "transparent", border: "1px solid #334155",
                      borderRadius: 6, color: "#94a3b8", cursor: "pointer",
                    }}
                  >
                    {showKey[p.id] ? "🙈" : "👁"}
                  </button>
                </div>
              </div>
            )}

            {/* 模型列表 */}
            <div style={{ marginBottom: "0.75rem" }}>
              <div style={{ color: "#64748b", fontSize: "0.8rem", marginBottom: "0.25rem" }}>可用模型:</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                {p.models.map((m) => (
                  <span key={m} style={{
                    padding: "2px 8px", background: "#0f172a",
                    borderRadius: 4, fontSize: "0.8rem", color: "#94a3b8",
                    fontFamily: "monospace",
                  }}>
                    {m}
                  </span>
                ))}
              </div>
            </div>

            {/* 操作区 */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              {statusBadge(testResults[p.id])}
              <button
                onClick={() => testProvider(p)}
                disabled={testing[p.id]}
                style={{
                  padding: "0.5rem 1rem", border: "none", borderRadius: 6,
                  background: testing[p.id] ? "#334155" : "#3b82f6",
                  color: "#fff", cursor: testing[p.id] ? "default" : "pointer",
                  fontSize: "0.85rem", fontWeight: 600,
                }}
              >
                {testing[p.id] ? "⏳ 测试中..." : "🔌 测试连接"}
              </button>
            </div>

            {/* 错误信息 */}
            {testResults[p.id]?.error && (
              <div style={{
                marginTop: "0.5rem", padding: "0.5rem",
                background: "#7f1d1d", borderRadius: 6,
                fontSize: "0.8rem", color: "#fca5a5", wordBreak: "break-all",
              }}>
                {testResults[p.id]!.error}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 降级链说明 */}
      <div style={{
        marginTop: "1.5rem", padding: "1rem",
        background: "#1e293b", borderRadius: 10, border: "1px solid #334155",
      }}>
        <h3 style={{ marginBottom: "0.5rem", color: "#94a3b8" }}>🔄 智能降级链</h3>
        <p style={{ color: "#64748b", fontSize: "0.9rem", lineHeight: 1.6 }}>
          TestForge 采用多通道降级策略：当主 API 超时或失败时，自动尝试下一个提供商。
          默认顺序：<b style={{ color: "#38bdf8" }}>DashScope → DeepSeek → Ollama 本地</b>。
          每个提供商失败后自动降级，确保 Pipeline 永不中断。
        </p>
        <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {["DashScope", "DeepSeek", "Ollama"].map((name, i) => (
            <span key={name} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                padding: "4px 12px", background: i === 0 ? "#1e3a5f" : "#0f172a",
                borderRadius: 6, fontSize: "0.85rem", color: "#e2e8f0",
              }}>
                {name}
              </span>
              {i < 2 && <span style={{ color: "#64748b" }}>→</span>}
            </span>
          ))}
          <span style={{ padding: "4px 8px", background: "#14532d", borderRadius: 6, fontSize: "0.8rem", color: "#22c55e" }}>
            永不中断
          </span>
        </div>
      </div>
    {/* SMTP Email Configuration */}
      <div style={{ marginTop: "2rem" }}>
        <h2 style={{ marginBottom: "1rem" }}>SMTP Email Configuration</h2>
        <SmtpConfigPanel />
      </div>
    </div>
  );
}
