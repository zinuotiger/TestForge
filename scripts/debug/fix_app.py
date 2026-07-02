# -*- coding: utf-8 -*-
filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\frontend\src\App.tsx"

# Build NAV_ITEMS with proper emoji using named chars
lines = []
lines.append('import { useEffect, useState } from "react";')
lines.append('import { Routes, Route, NavLink, Navigate, useLocation } from "react-router-dom";')
lines.append('import { useAuth } from "./auth";')
lines.append('import Login from "./pages/Login";')
lines.append('import Dashboard from "./pages/Dashboard";')
lines.append('import ExecutionCenter from "./pages/ExecutionCenter";')
lines.append('import TestDesigner from "./pages/TestDesigner";')
lines.append('import Reports from "./pages/Reports";')
lines.append('import Settings from "./pages/Settings";')
lines.append('import WebsiteTester from "./pages/WebsiteTester";')
lines.append('import AgentPlayground from "./pages/AgentPlayground";')
lines.append('import ScheduleMonitor from "./pages/ScheduleMonitor";')
lines.append('import TestList from "./pages/TestList";')
lines.append('import ImpactAnalysis from "./pages/ImpactAnalysis";')
lines.append('import TokenUsage from "./pages/TokenUsage";')
lines.append('import CodeTester from "./pages/CodeTester";')
lines.append('import EvolutionDashboard from "./pages/EvolutionDashboard";')
lines.append('')
lines.append('const sidebarWidth = 220;')
lines.append('')
lines.append('const sidebarStyle: React.CSSProperties = {')
lines.append('  width: sidebarWidth,')
lines.append('  minHeight: "100vh",')
lines.append('  background: "#0f172a",')
lines.append('  borderRight: "1px solid #1e293b",')
lines.append('  padding: "1.25rem 0",')
lines.append('  position: "fixed",')
lines.append('  left: 0,')
lines.append('  top: 0,')
lines.append('  display: "flex",')
lines.append('  flexDirection: "column",')
lines.append('};')
lines.append('')
lines.append('const logoStyle: React.CSSProperties = {')
lines.append('  padding: "0 1.25rem 1.25rem",')
lines.append('  fontWeight: 800,')
lines.append('  color: "#38bdf8",')
lines.append('  fontSize: "1.15rem",')
lines.append('  borderBottom: "1px solid #1e293b",')
lines.append('  marginBottom: "0.75rem",')
lines.append('};')
lines.append('')
lines.append('const navGroupStyle: React.CSSProperties = {')
lines.append('  padding: "0.5rem 1.25rem 0.25rem",')
lines.append('  color: "#475569",')
lines.append('  fontSize: "0.7rem",')
lines.append('  fontWeight: 700,')
lines.append('  textTransform: "uppercase" as const,')
lines.append('  letterSpacing: "0.1em",')
lines.append('};')
lines.append('')
lines.append('const linkBase: React.CSSProperties = {')
lines.append('  display: "flex",')
lines.append('  alignItems: "center",')
lines.append('  gap: "0.6rem",')
lines.append('  padding: "0.6rem 1.25rem",')
lines.append('  color: "#94a3b8",')
lines.append('  textDecoration: "none",')
lines.append('  fontWeight: 500,')
lines.append('  fontSize: "0.9rem",')
lines.append('  borderLeft: "3px solid transparent",')
lines.append('  transition: "all 0.15s",')
lines.append('};')
lines.append('')
lines.append('const activeLink: React.CSSProperties = {')
lines.append('  ...linkBase,')
lines.append('  color: "#38bdf8",')
lines.append('  background: "rgba(56,189,248,0.08)",')
lines.append('  borderLeftColor: "#38bdf8",')
lines.append('};')
lines.append('')
lines.append('const mainStyle: React.CSSProperties = {')
lines.append('  marginLeft: sidebarWidth,')
lines.append('  padding: "2rem",')
lines.append('  minHeight: "100vh",')
lines.append('  background: "#0f172a",')
lines.append('  width: `calc(100vw - ${sidebarWidth}px)`,')
lines.append('  display: "flex",')
lines.append('  justifyContent: "center",')
lines.append('};')
lines.append('')
lines.append('const contentWrapper: React.CSSProperties = {')
lines.append('  maxWidth: 1200,')
lines.append('  width: "100%",')
lines.append('};')
lines.append('')
lines.append('const NAV_ITEMS = [')
lines.append('  {')
lines.append('    group: "\u6982\u89c8",')
lines.append('    items: [{ to: "/", icon: "\U0001f4ca", label: "Dashboard" }],')
lines.append('  },')
lines.append('  {')
lines.append('    group: "\u6d4b\u8bd5",')
lines.append('    items: [')
lines.append('      { to: "/design", icon: "\U0001f3a8", label: "\u6d4b\u8bd5\u8bbe\u8ba1\u5668" },')
lines.append('      { to: "/tests", icon: "\U0001f4f0", label: "\u6d4b\u8bd5\u5217\u8868" },')
lines.append('      { to: "/execute", icon: "\U0001f680", label: "\u6267\u884c\u4e2d\u5fc3" },')
lines.append('      { to: "/website", icon: "\U0001f310", label: "\u7f51\u7ad9\u6d4b\u8bd5" },')
lines.append('      { to: "/code", icon: "\U0001f4bb", label: "\u4ee3\u7801\u6d4b\u8bd5" },')
lines.append('    ],')
lines.append('  },')
lines.append('  {')
lines.append('    group: "\u667a\u80fd",')
lines.append('    items: [')
lines.append('      { to: "/agent", icon: "\U0001f916", label: "Agent Playground" },')
lines.append('      { to: "/schedule", icon: "\u23f0", label: "\u5b9a\u65f6\u5de1\u5bdf" },')
lines.append('      { to: "/evolution", icon: "\U0001f9e0", label: "\u81ea\u8fdb\u5316" },')
lines.append('    ],')
lines.append('  },')
lines.append('  {')
lines.append('    group: "\u5206\u6790",')
lines.append('    items: [')
lines.append('      { to: "/impact", icon: "\U0001f3af", label: "\u5f71\u54cd\u5206\u6790" },')
lines.append('      { to: "/token", icon: "\U0001f4b5", label: "Token \u7528\u91cf" },')
lines.append('      { to: "/reports", icon: "\U0001f4f1", label: "\u62a5\u544a" },')
lines.append('    ],')
lines.append('  },')
lines.append('  {')
lines.append('    group: "\u7cfb\u7edf",')
lines.append('    items: [{ to: "/settings", icon: "\u2699\ufe0f", label: "\u8bbe\u7f6e" }],')
lines.append('  },')
lines.append('];')
lines.append('')

# roleColor, ProtectedLayout, App
rest = '''const roleColor: Record<string, string> = {
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
        <div style={logoStyle}>\u26a1 TestForge</div>

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
                title="\u767b\u51fa"
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
                \u9000\u51fa
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
        \u52a0\u8f7d\u4e2d...
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
'''

# Write using binary to avoid surrogate issues
content = '\n'.join(lines) + '\n' + rest

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print('App.tsx written successfully!')
