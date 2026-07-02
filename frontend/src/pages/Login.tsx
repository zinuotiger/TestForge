import { useState, FormEvent } from "react";
import { useAuth } from "../auth";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0f172a",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          width: 380,
          maxWidth: "90%",
          background: "#1e293b",
          borderRadius: 12,
          padding: "2.5rem 2rem",
          boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>⚒️</div>
          <h1 style={{ color: "#38bdf8", fontSize: "1.5rem", fontWeight: 800, margin: 0 }}>
            TestForge
          </h1>
          <p style={{ color: "#64748b", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            全类型智能测试平台
          </p>
        </div>

        {/* 登录表单 */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem", display: "block", marginBottom: "0.4rem" }}>
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoFocus
              required
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 8,
                color: "#e2e8f0",
                fontSize: "0.9rem",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem", display: "block", marginBottom: "0.4rem" }}>
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 8,
                color: "#e2e8f0",
                fontSize: "0.9rem",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <div
              style={{
                padding: "0.6rem 0.8rem",
                marginBottom: "1rem",
                background: "#7f1d1d",
                borderRadius: 6,
                color: "#fca5a5",
                fontSize: "0.85rem",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            style={{
              width: "100%",
              padding: "0.8rem",
              border: "none",
              borderRadius: 8,
              background: loading || !username || !password ? "#334155" : "#3b82f6",
              color: "#fff",
              fontSize: "1rem",
              fontWeight: 700,
              cursor: loading || !username || !password ? "default" : "pointer",
              transition: "background 0.15s",
            }}
          >
            {loading ? "登录中..." : "登录"}
          </button>
        </form>

        {/* 提示 */}
        <div
          style={{
            marginTop: "1.5rem",
            paddingTop: "1rem",
            borderTop: "1px solid #334155",
            textAlign: "center",
            color: "#475569",
            fontSize: "0.78rem",
            lineHeight: 1.6,
          }}
        >
          开发模式默认账户: admin / testforge<br />
          生产模式启动时控制台打印随机密码
        </div>
      </div>
    </div>
  );
}
