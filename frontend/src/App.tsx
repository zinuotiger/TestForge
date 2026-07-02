import { useEffect, useState } from "react";
import { Routes, Route, NavLink, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import ExecutionCenter from "./pages/ExecutionCenter";
import TestDesigner from "./pages/TestDesigner";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import WebsiteTester from "./pages/WebsiteTester";
import AgentPlayground from "./pages/AgentPlayground";
import ScheduleMonitor from "./pages/ScheduleMonitor";
import TestList from "./pages/TestList";
import ImpactAnalysis from "./pages/ImpactAnalysis";
import TokenUsage from "./pages/TokenUsage";
import CodeTester from "./pages/CodeTester";
import EvolutionDashboard from "./pages/EvolutionDashboard";

const sidebarWidth = 220;

const sidebarStyle: React.CSSProperties = {
  width: sidebarWidth,
  minHeight: "100vh",
  background: "#0f172a",
  borderRight: "1px solid #1e293b",
  padding: "1.25rem 0",
  position: "fixed",
  left: 0,
  top: 0,
  display: "flex",
  flexDirection: "column",
};

const logoStyle: React.CSSProperties = {
  padding: "0 1.25rem 1.25rem",
  fontWeight: 800,
  color: "#38bdf8",
  fontSize: "1.15rem",
  borderBottom: "1px solid #1e293b",
  marginBottom: "0.75rem",
};

const navGroupStyle: React.CSSProperties = {
  padding: "0.5rem 1.25rem 0.25rem",
  color: "#475569",
  fontSize: "0.7rem",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.1em",
};

const linkBase: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.6rem",
  padding: "0.6rem 1.25rem",
  color: "#94a3b8",
  textDecoration: "none",
  fontWeight: 500,
  fontSize: "0.9rem",
  borderLeft: "3px solid transparent",
  transition: "all 0.15s",
};

const activeLink: React.CSSProperties = {
  ...linkBase,
  color: "#38bdf8",
  background: "rgba(56,189,248,0.08)",
  borderLeftColor: "#38bdf8",
};

const mainStyle: React.CSSProperties = {
  marginLeft: sidebarWidth,
  padding: "2rem",
  minHeight: "100vh",
  background: "#0f172a",
  width: `calc(100vw - ${sidebarWidth}px)`,
  display: "flex",
  justifyContent: "center",
};

const contentWrapper: React.CSSProperties = {
  maxWidth: 1200,
  width: "100%",
};

const NAV_ITEMS = [
  {
    group: "概览",
    items: [{ to: "/", icon: "📊", label: "Dashboard" }],
  },
  {
    group: "测试",
    items: [
      { to: "/design", icon: "🎨", label: "测试设计器" },
      { to: "/tests", icon: "📰", label: "测试列表" },
      { to: "/execute", icon: "🚀", label: "执行中心" },
      { to: "/website", icon: "🌐", label: "网站测试" },
      { to: "/code", icon: "💻", label: "代码测试" },
    ],
  },
  {
    group: "智能",
    items: [
      { to: "/agent", icon: "🤖", label: "Agent Playground" },
      { to: "/schedule", icon: "⏰", label: "定时巡察" },
      { to: "/evolution", icon: "🧠", label: "自进化" },
    ],
  },
  {
    group: "分析",
    items: [
      { to: "/impact", icon: "🎯", label: "影响分析" },
      { to: "/token", icon: "💵", label: "Token 用量" },
      { to: "/reports", icon: "📱", label: "报告" },
    ],
  },
  {
    group: "系统",
    items: [{ to: "/settings", icon: "⚙️", label: "设置" }],
  },
];

const roleColor: Record<string, string> = {
  admin: "#f59e0b",
  editor: "#38bdf8",
  viewer: "#94a3b8",
};

function ProtectedLayout() {
  const { user, logout } = useAuth();
  const [version, setVersion] = useState("v0.1.0");

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.version) setVersion(`v${d.version}`);
      })
      .catch(() => {});
  }, []);

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside style={sidebarStyle}>
        <div style={logoStyle}>⚡ TestForge</div>

        {NAV_ITEMS.map((group) => (
          <div key={group.group}>
            <div style={navGroupStyle}>{group.group}</div>
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                style={({ isActive }) => (isActive ? activeLink : linkBase)}
              >
                <span style={{ fontSize: "1.1rem" }}>{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}

        <div style={{ marginTop: "auto", padding: "1rem 1.25rem", borderTop: "1px solid #1e293b" }}>
          <div style={{ color: "#22c55e", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e" }} />
            Pipeline Ready
          </div>
          <div style={{ color: "#475569", fontSize: "0.7rem", marginTop: "0.25rem" }}>{version}</div>

          {user && (
            <div
              style={{
                marginTop: "0.75rem",
                paddingTop: "0.75rem",
                borderTop: "1px solid #1e293b",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ color: "#e2e8f0", fontSize: "0.8rem", fontWeight: 600 }}>
                  {user.username}
                </div>
                <span
                  style={{
                    display: "inline-block",
                    padding: "1px 6px",
                    borderRadius: 3,
                    fontSize: "0.65rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    background: "#1e293b",
                    color: roleColor[user.role] || "#94a3b8",
                    marginTop: "2px",
                  }}
                >
                  {user.role}
                </span>
              </div>
              <button
                onClick={logout}
                title="登出"
                style={{
                  padding: "4px 8px",
                  border: "1px solid #334155",
                  borderRadius: 4,
                  background: "transparent",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: "0.75rem",
                }}
              >
                退出
              </button>
            </div>
          )}
        </div>
      </aside>

      <main style={mainStyle}>
        <div style={contentWrapper}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/design" element={<TestDesigner />} />
            <Route path="/tests" element={<TestList />} />
            <Route path="/execute" element={<ExecutionCenter />} />
            <Route path="/impact" element={<ImpactAnalysis />} />
            <Route path="/token" element={<TokenUsage />} />
            <Route path="/website" element={<WebsiteTester />} />
            <Route path="/code" element={<CodeTester />} />
            <Route path="/agent" element={<AgentPlayground />} />
            <Route path="/evolution" element={<EvolutionDashboard />} />
            <Route path="/schedule" element={<ScheduleMonitor />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#0f172a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#475569",
          fontSize: "0.9rem",
        }}
      >
        加载中...
      </div>
    );
  }

  if (!isAuthenticated && location.pathname !== "/login") {
    return <Navigate to="/login" replace />;
  }

  if (isAuthenticated && location.pathname === "/login") {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<ProtectedLayout />} />
    </Routes>
  );
}
