import { useState, useEffect } from "react";

interface SmtpStatus {
  configured: boolean;
  host: string;
  port: number;
  use_tls: boolean;
  user: string;
  has_password: boolean;
}

interface TestResult {
  success: boolean;
  latency_ms?: number;
  error?: string;
}

const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: "0.5rem",
  background: "#0f172a",
  border: "1px solid #334155",
  borderRadius: 6,
  color: "#e2e8f0",
  fontSize: "0.85rem",
  width: "100%",
  boxSizing: "border-box",
};

export default function SmtpConfigPanel() {
  const [host, setHost] = useState("");
  const [port, setPort] = useState(465);
  const [useTls, setUseTls] = useState(true);
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<SmtpStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch("/api/settings/email")
      .then((r) => r.json())
      .then((d) => {
        setStatus(d);
        setHost(d.host || "");
        setPort(d.port || 465);
        setUseTls(d.use_tls !== false);
        setUser(d.user || "");
      })
      .catch(() => {});
  }, []);

  const saveConfig = async () => {
    setSaving(true);
    setMsg("Saving...");
    try {
      const res = await fetch("/api/settings/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host, port, use_tls: useTls, user, password }),
      });
      const d = await res.json();
      setMsg(d.success ? "Config saved. Restart server to apply." : d.error || "Save failed");
      if (d.success) setPassword("");
    } catch (e) {
      setMsg("Save failed: " + String(e));
    }
    setSaving(false);
  };

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch("/api/settings/email/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host, port, use_tls: useTls, user, password }),
      });
      const d = await res.json();
      setTestResult(d);
    } catch (e) {
      setTestResult({ success: false, error: String(e) });
    }
    setTesting(false);
  };

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {/* Status indicator */}
      {status !== null && (
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: 8,
            background: status.configured ? "#14532d" : "#451a03",
            border: "1px solid " + (status.configured ? "#22c55e" : "#d97706"),
            color: status.configured ? "#86efac" : "#fcd34d",
            fontSize: "0.9rem",
          }}
        >
          {status.configured
            ? `SMTP configured: ${status.user} via ${status.host}`
            : "SMTP not configured. Fill in your email credentials below."}
        </div>
      )}

      {/* Form fields */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <div>
          <label style={labelStyle}>SMTP Host</label>
          <input type="text" value={host} onChange={(e) => setHost(e.target.value)} placeholder="smtp.qq.com" style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Port</label>
          <input type="number" value={port} onChange={(e) => setPort(Number(e.target.value))} placeholder="465" style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Email Address</label>
          <input type="email" value={user} onChange={(e) => setUser(e.target.value)} placeholder="your@email.com" style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Password / Auth Code</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={status?.has_password ? "(already set)" : "Enter SMTP password"}
            style={inputStyle}
          />
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", color: "#cbd5e1", fontSize: "0.85rem", cursor: "pointer" }}>
          <input type="checkbox" checked={useTls} onChange={(e) => setUseTls(e.target.checked)} /> Use SSL/TLS
        </label>
      </div>

      {/* Buttons */}
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
        <button
          onClick={saveConfig}
          disabled={saving || !host || !user}
          style={{
            padding: "0.6rem 1.25rem",
            border: "none",
            borderRadius: 6,
            background: saving || !host || !user ? "#334155" : "#3b82f6",
            color: "#fff",
            cursor: saving || !host || !user ? "default" : "pointer",
            fontSize: "0.85rem",
            fontWeight: 600,
          }}
        >
          {saving ? "Saving..." : "Save Config"}
        </button>
        <button
          onClick={testConnection}
          disabled={testing || !host || !user}
          style={{
            padding: "0.6rem 1.25rem",
            border: "1px solid #334155",
            borderRadius: 6,
            background: "transparent",
            color: testing ? "#94a3b8" : "#38bdf8",
            cursor: testing || !host || !user ? "default" : "pointer",
            fontSize: "0.85rem",
            fontWeight: 600,
          }}
        >
          {testing ? "Testing..." : "Test Connection"}
        </button>
        {msg && (
          <span style={{ color: testResult?.success ? "#22c55e" : "#fbbf24", fontSize: "0.85rem" }}>{msg}</span>
        )}
      </div>

      {/* Test result */}
      {testResult && (
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: 8,
            background: testResult.success ? "#14532d" : "#7f1d1d",
            border: "1px solid " + (testResult.success ? "#22c55e" : "#ef4444"),
            color: testResult.success ? "#86efac" : "#fca5a5",
            fontSize: "0.85rem",
          }}
        >
          {testResult.success
            ? `Connection successful! Latency: ${testResult.latency_ms}ms`
            : `Test failed: ${testResult.error || "Unknown error"}`}
        </div>
      )}
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  color: "#94a3b8",
  fontSize: "0.8rem",
  display: "block",
  marginBottom: "0.25rem",
};
