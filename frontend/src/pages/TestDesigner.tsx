import { useState } from "react";

const STEP_TYPES = [
  { key: "http_request", label: "HTTP 请求", icon: "🌐" },
  { key: "browser_action", label: "浏览器操作", icon: "🖥️" },
  { key: "code_exec", label: "代码执行", icon: "⚡" },
  { key: "db_query", label: "数据库查询", icon: "🗄️" },
  { key: "script", label: "脚本", icon: "📜" },
];

const ASSERTION_TYPES = [
  { key: "status", label: "状态码" },
  { key: "json_path", label: "JSON路径" },
  { key: "equals", label: "等于" },
  { key: "contains", label: "包含" },
];

export default function TestDesigner() {
  const [name, setName] = useState("");
  const [steps, setSteps] = useState<any[]>([]);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const addStep = (type: string) => {
    setSteps([
      ...steps,
      {
        id: `step_${Date.now()}`,
        type,
        method: "GET",
        url: "/api/",
        body: "",
        assertions: [{ type: "status", expected: "200" }],
      },
    ]);
  };

  const updateStep = (idx: number, field: string, value: any) => {
    const updated = [...steps];
    updated[idx] = { ...updated[idx], [field]: value };
    setSteps(updated);
  };

  const addAssertion = (stepIdx: number) => {
    const updated = [...steps];
    updated[stepIdx].assertions.push({ type: "status", expected: "200" });
    setSteps(updated);
  };

  const removeStep = (idx: number) => setSteps(steps.filter((_, i) => i !== idx));

  const save = async () => {
    setError("");
    let parsedBody;
    try {
      // 预校验所有步骤的 JSON body
      const mappedSteps = steps.map((s) => {
        let body = undefined;
        if (s.type === "http_request" && s.body) {
          body = JSON.parse(s.body);
        }
        return {
          id: s.id,
          type: s.type,
          description: `${s.method} ${s.url}`,
          request: s.type === "http_request" ? { method: s.method, url: s.url, body } : undefined,
          assertions: s.assertions.map((a: any) => ({
            type: a.type,
            expected: a.type === "status" ? parseInt(a.expected) : a.expected,
          })),
        };
      });

      const testCase = {
        name: name || "未命名测试",
        type: "functional",
        tags: ["designed"],
        created_by: "visual",
        steps: mappedSteps,
      };

      const res = await fetch("/api/tests/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(testCase),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        setError(`保存失败: HTTP ${res.status}`);
      }
    } catch (e) {
      if (e instanceof SyntaxError) {
        setError("JSON 格式错误，请检查请求体输入");
      } else {
        setError(`保存失败: ${String(e)}`);
      }
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h2>🎨 测试设计器</h2>
        <button onClick={save} style={{
          padding: "0.75rem 2rem", border: "none", borderRadius: 8,
          background: saved ? "#22c55e" : "#3b82f6", color: "#fff",
          fontWeight: 700, cursor: "pointer", fontSize: "1rem",
        }}>
          {saved ? "✅ 已保存" : "💾 保存"}
        </button>
      </div>

      {error && (
        <div style={{
          padding: "0.75rem 1rem", marginBottom: "1rem", background: "#7f1d1d",
          borderRadius: 8, color: "#fca5a5", fontSize: "0.9rem",
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* 测试名称 */}
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="测试名称，如：用户登录-密码错误"
        style={{
          width: "100%", padding: "0.75rem", marginBottom: "1rem",
          background: "#1e293b", border: "1px solid #334155", borderRadius: 8,
          color: "#e2e8f0", fontSize: "1rem",
        }}
      />

      {/* 步骤列表 */}
      {steps.map((step, idx) => (
        <div key={step.id} style={{
          background: "#1e293b", borderRadius: 8, padding: "1rem", marginBottom: "0.75rem",
          border: "1px solid #334155",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem" }}>
            <span style={{ fontWeight: 600, color: "#38bdf8" }}>步骤 {idx + 1}</span>
            <button onClick={() => removeStep(idx)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer" }}>✕</button>
          </div>

          {step.type === "http_request" && (
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <select value={step.method} onChange={(e) => updateStep(idx, "method", e.target.value)}
                style={selectStyle}>
                {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => <option key={m}>{m}</option>)}
              </select>
              <input value={step.url} onChange={(e) => updateStep(idx, "url", e.target.value)}
                placeholder="/api/endpoint" style={inputStyle} />
            </div>
          )}

          {step.type === "http_request" && (
            <textarea value={step.body} onChange={(e) => updateStep(idx, "body", e.target.value)}
              placeholder='{"key": "value"}'
              rows={3} style={{ ...inputStyle, width: "100%", marginBottom: "0.5rem", fontFamily: "monospace" }} />
          )}

          {/* 断言 */}
          <div style={{ marginTop: "0.5rem" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "0.25rem" }}>断言:</div>
            {step.assertions.map((a: any, ai: number) => (
              <div key={ai} style={{ display: "flex", gap: "0.5rem", marginBottom: "0.25rem" }}>
                <select value={a.type}
                  onChange={(e) => {
                    const updated = [...steps];
                    updated[idx].assertions[ai].type = e.target.value;
                    setSteps(updated);
                  }}
                  style={selectStyle}>
                  {ASSERTION_TYPES.map((at) => <option key={at.key} value={at.key}>{at.label}</option>)}
                </select>
                <input value={a.expected}
                  onChange={(e) => {
                    const updated = [...steps];
                    updated[idx].assertions[ai].expected = e.target.value;
                    setSteps(updated);
                  }}
                  placeholder="期望值" style={inputStyle} />
              </div>
            ))}
            <button onClick={() => addAssertion(idx)} style={{
              padding: "0.25rem 0.75rem", border: "1px dashed #334155", borderRadius: 4,
              background: "transparent", color: "#94a3b8", cursor: "pointer", fontSize: "0.8rem",
            }}>
              + 断言
            </button>
          </div>
        </div>
      ))}

      {/* 添加步骤 */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "1rem" }}>
        {STEP_TYPES.map((st) => (
          <button key={st.key} onClick={() => addStep(st.key)} style={{
            padding: "0.5rem 1rem", border: "1px dashed #334155", borderRadius: 8,
            background: "transparent", color: "#94a3b8", cursor: "pointer",
          }}>
            {st.icon} {st.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  flex: 1, padding: "0.5rem", background: "#0f172a", border: "1px solid #334155",
  borderRadius: 6, color: "#e2e8f0", fontSize: "0.9rem",
};
const selectStyle: React.CSSProperties = {
  padding: "0.5rem", background: "#0f172a", border: "1px solid #334155",
  borderRadius: 6, color: "#e2e8f0",
};
