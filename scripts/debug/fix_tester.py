import sys
sys.stdout.reconfigure(encoding="utf-8")

filepath = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\frontend\src\pages\CodeTester.tsx"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add "project" to mode union type
content = content.replace(
    'useState<"comprehensive" | "generate" | "execute">("comprehensive")',
    'useState<"comprehensive" | "generate" | "execute" | "project">("comprehensive")'
)

# 2. Add folderPath state after funcName state
content = content.replace(
    'const [funcName, setFuncName] = useState("");\n',
    'const [funcName, setFuncName] = useState("");\n  const [folderPath, setFolderPath] = useState("");\n'
)

# 3. Add project result state after generateResult
content = content.replace(
    'const [generateResult, setGenerateResult] = useState<GenerateResult | null>(null);\n',
    'const [generateResult, setGenerateResult] = useState<GenerateResult | null>(null);\n  const [projectResult, setProjectResult] = useState<any>(null);\n'
)

# 4. Add runProject function after runExecute
old_func = '''  const runExecute = async () => {
    if (!execCode) { setError("请先生成测试代码或粘贴测试代码"); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch("/api/code/execute-only", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: execCode, language, timeout: 60 }),
      });
      const data = await res.json();
      const partial: CodeTestResult = {
        status: "completed", analysis: { function_count: 0, class_count: 0, complexity: "", smells: 0 }, generated_test_count: 0, test_cases: [],
        execution: data, security: { risks_found: 0, risks: [] }, summary: {} as CodeTestSummary, duration_ms: 0, error: "",
      };
      setResult(partial);
    } catch (e) {
      setError(`执行失败: ${String(e)}`);
    }
    setLoading(false);
  };'''

new_func = old_func + """

  // 项目文件夹测试
  const runProject = async () => {
    if (!folderPath) { setError("\u8bf7\u8f93\u5165\u9879\u76ee\u6587\u4ef6\u5939\u8def\u5f84"); return; }
    setLoading(true); setError(""); setProjectResult(null);
    try {
      const res = await fetch("/api/code/project-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_path: folderPath, language, timeout: 300 }),
      });
      const data = await res.json();
      setProjectResult(data);
    } catch (e) {
      setError(`\u9879\u76ee\u6d4b\u8bd5\u5931\u8d25: ${String(e)}`);
    }
    setLoading(false);
  };"""

content = content.replace(old_func, new_func)

# 5. Add "project" button to mode selector
content = content.replace(
    '(["comprehensive", "generate", "execute"] as const).map((m) => (',
    '(["comprehensive", "generate", "execute", "project"] as const).map((m) => ('
)

content = content.replace(
    '{"comprehensive" ? "\ud83d\udd2c \u7efc\u5408\u6d4b\u8bd5" : m === "generate" ? "\ud83e\uddec \u4ec5\u751f\u6210" : "\u26a1 \u4ec5\u6267\u884c"}\n',
    '{"comprehensive" ? "\ud83d\udd2c \u7efc\u5408\u6d4b\u8bd5" : m === "generate" ? "\ud83e\uddec \u4ec5\u751f\u6210" : m === "execute" ? "\u26a1 \u4ec5\u6267\u884c" : "\ud83d\udcc1 \u9879\u76ee\u6d4b\u8bd5"}\n'
)

# 6. Add folder path input for project mode (after language selector, before source code)
old_input_area = '        <div style={labelStyle}>\u6e90\u4ee3\u7801</div>'
new_input_area = '''        {(mode === "project") && (
          <div>
            <div style={labelStyle}>\u9879\u76ee\u6587\u4ef6\u5939\u8def\u5f84</div>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
              <input
                placeholder="C:\\path\\to\\your\\project"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                style={{ ...inputStyle, flex: 1 }}
              />
            </div>
            <p style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "-0.5rem", marginBottom: "1rem" }}>
              \u81ea\u52a8\u626b\u63cf\u6240\u6709 .py \u6587\u4ef6\uff0c\u9010\u4e2a\u8fdb\u884c\u5206\u6790 \u2192 \u751f\u6210 \u2192 \u6267\u884c \u2192 \u5b89\u5168\u626b\u63cf
            </p>
          </div>
        )}

        <div style={labelStyle}>\u6e90\u4ee3\u7801</div>'''

content = content.replace(old_input_area, new_input_area)

# 7. Update the action button
old_button = "<button onClick={mode === \"comprehensive\" ? runComprehensive : mode === \"generate\" ? runGenerate : runExecute} disabled={loading}"
new_button = "<button onClick={mode === \"comprehensive\" ? runComprehensive : mode === \"generate\" ? runGenerate : mode === \"execute\" ? runExecute : runProject} disabled={loading}"

content = content.replace(old_button, new_button)

# 8. Update the button text
old_btn_text = '{loading ? "\u23f3 \u6267\u884c\u4e2d..." : mode === "comprehensive" ? "\ud83d\ude80 \u4e00\u952e\u6d4b\u8bd5" : mode === "generate" ? "\ud83e\uddec \u751f\u6210\u6d4b\u8bd5" : "\u26a1 \u6267\u884c\u6d4b\u8bd5"}'
new_btn_text = '{loading ? "\u23f3 \u6267\u884c\u4e2d..." : mode === "comprehensive" ? "\ud83d\ude80 \u4e00\u952e\u6d4b\u8bd5" : mode === "generate" ? "\ud83e\uddec \u751f\u6210\u6d4b\u8bd5" : mode === "execute" ? "\u26a1 \u6267\u884c\u6d4b\u8bd5" : "\ud83d\udcc1 \u9879\u76ee\u6d4b\u8bd5"}'

content = content.replace(old_btn_text, new_btn_text)

# 9. Add project result display before the closing </div> of the return block
# Find the last </div> before export default
# Insert project results display after the error display
old_error_section = '{error && (\n        <div style={{ ...cardStyle, marginTop: "1rem", border: "1px solid #ef4444", color: "#ef4444" }}>\u274c {error}</div>\n      )}'

project_display = '''{projectResult && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3 style={{ color: "#e2e8f0", fontSize: "1.1rem", marginBottom: "0.75rem" }}>
            \u2705 \u9879\u76ee\u6d4b\u8bd5\u7ed3\u679c ({projectResult.total_files} \u4e2a\u6587\u4ef6)
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            {projectResult.files?.map((f: any) => (
              <div key={f.filepath} style={{
                ...cardStyle,
                borderLeft: `4px solid ${f.status === "completed" ? (f.summary?.pass_rate >= 80 ? "#22c55e" : f.summary?.pass_rate >= 50 ? "#f59e0b" : "#ef4444") : "#ef4444"}`,
                padding: "0.75rem 1rem",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span style={{ color: "#cbd5e1", fontWeight: 600, fontSize: "0.85rem" }}>{f.filename}</span>
                    {f.summary?.functions > 0 && (
                      <span style={{ marginLeft: "1rem", color: "#64748b", fontSize: "0.75rem" }}>
                        {f.summary.functions} \u51fd\u6570 | {f.summary.test_count} \u6d4b\u8bd5 | \u901a\u8fc7 {f.summary.passed}/{f.summary.passed + f.summary.failed}
                      </span>
                    )}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {f.status === "completed" ? (
                      <span style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: "0.75rem", fontWeight: 600,
                        background: f.summary?.pass_rate >= 80 ? "#14532d" : f.summary?.pass_rate >= 50 ? "#422006" : "#451a03",
                        color: f.summary?.pass_rate >= 80 ? "#86efac" : f.summary?.pass_rate >= 50 ? "#fde68a" : "#fca5a5",
                      }}>
                        {f.summary?.pass_rate ?? 0}%
                      </span>
                    ) : (
                      <span style={{ color: "#ef4444", fontSize: "0.75rem" }}>{f.error || "\u5931\u8d25"}</span>
                    )}
                    <span style={{ color: "#475569", fontSize: "0.7rem" }}>{(f.duration_ms / 1000).toFixed(1)}s</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}'''

content = content.replace(old_error_section, old_error_section + "\n\n      " + project_display)

# Also hide source code input in project mode - wrap it conditionally
content = content.replace(
    '        <div style={labelStyle}>\u6e90\u4ee3\u7801</div>\n        <textarea',
    '{mode !== "project" && (<>\n        <div style={labelStyle}>\u6e90\u4ee3\u7801</div>\n        <textarea'
)

# Find the end of textarea to close the conditional
old_textarea_end = 'placeholder="粘贴你的源代码..."\n        />'
# We need to close </> correctly. Let's search for the pattern after textarea
content = content.replace(
    'placeholder="\u7c98\u8d34\u4f60\u7684\u6e90\u4ee3\u7801..."\n        />',
    'placeholder="\u7c98\u8d34\u4f60\u7684\u6e90\u4ee3\u7801..."\n        />\n        </>)}'
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("CodeTester.tsx updated!")
