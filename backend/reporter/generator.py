"""报告生成模块 — JUnit XML / JSON / HTML 多格式"""

import json
from datetime import datetime
from xml.etree import ElementTree as ET


def generate_junit_xml(executions: list[dict], output_path: str = "") -> str:
    """生成 JUnit XML 报告。

    Args:
        executions: 执行记录列表（来自 store.list_executions）
        output_path: 写入文件路径；为空则仅返回 XML 字符串

    Returns:
        JUnit XML 字符串
    """
    testsuites = ET.Element("testsuites")
    total = len(executions)
    failures = sum(1 for e in executions if e.get("status") == "failed")
    errors = sum(1 for e in executions if e.get("status") == "error")
    elapsed = sum(e.get("duration_ms", 0) for e in executions) / 1000.0

    suite = ET.SubElement(testsuites, "testsuite", {
        "name": "TestForge",
        "tests": str(total),
        "failures": str(failures),
        "errors": str(errors),
        "time": f"{elapsed:.2f}",
        "timestamp": datetime.now().isoformat(),
    })

    for e in executions:
        case = ET.SubElement(suite, "testcase", {
            "name": e.get("execution_id", "unknown"),
            "classname": e.get("test_id", "batch"),
            "time": f"{e.get('duration_ms', 0) / 1000.0:.3f}",
        })
        status = e.get("status", "")
        if status == "failed":
            ET.SubElement(case, "failure", {
                "message": e.get("error_message", "测试失败"),
            })
        elif status == "error":
            ET.SubElement(case, "error", {
                "message": e.get("error_message", "执行错误"),
            })
        elif status == "skipped":
            ET.SubElement(case, "skipped")

    xml_str = ET.tostring(testsuites, encoding="unicode")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)

    return xml_str


def generate_json_report(executions: list[dict], tests: list = None) -> str:
    """生成 JSON 格式报告"""
    total = len(executions)
    passed = sum(1 for e in executions if e.get("status") == "passed")
    failed = sum(1 for e in executions if e.get("status") == "failed")
    errors = sum(1 for e in executions if e.get("status") == "error")
    pass_rate = round(passed / total * 100, 1) if total else 0.0

    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": pass_rate,
            "total_test_cases": len(tests) if tests else 0,
        },
        "executions": executions,
    }
    return json.dumps(report, ensure_ascii=False, indent=2)


def generate_html_report(executions: list[dict], tests: list = None) -> str:
    """生成 HTML 格式报告"""
    total = len(executions)
    passed = sum(1 for e in executions if e.get("status") == "passed")
    failed = sum(1 for e in executions if e.get("status") == "failed")
    errors = sum(1 for e in executions if e.get("status") == "error")
    pass_rate = round(passed / total * 100, 1) if total else 0.0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_count = len(tests) if tests else 0

    rows = ""
    for e in executions[:20]:
        status = e.get("status", "unknown")
        color = {"passed": "#22c55e", "failed": "#ef4444", "error": "#f59e0b"}.get(status, "#64748b")
        rows += f"""
        <tr>
          <td style="padding:6px;border-bottom:1px solid #1e293b;">{e.get('execution_id', '')}</td>
          <td style="padding:6px;border-bottom:1px solid #1e293b;color:{color};font-weight:600;">{status}</td>
          <td style="padding:6px;border-bottom:1px solid #1e293b;">{e.get('duration_ms', 0)}ms</td>
          <td style="padding:6px;border-bottom:1px solid #1e293b;">{(e.get('started_at') or '')[:19]}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>TestForge Report</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; margin: 2rem; }}
  h1 {{ color: #38bdf8; }}
  .cards {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 1rem; margin: 1.5rem 0; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; text-align: center; }}
  .card .num {{ font-size: 2rem; font-weight: 800; font-family: monospace; }}
  .card .label {{ color: #94a3b8; margin-bottom: 0.5rem; }}
  table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
  th {{ text-align: left; padding: 8px; color: #94a3b8; border-bottom: 2px solid #334155; }}
</style></head><body>
<h1>TestForge 测试报告</h1>
<p style="color:#64748b;">生成时间: {now}</p>
<div class="cards">
  <div class="card"><div class="label">执行总数</div><div class="num" style="color:#e2e8f0">{total}</div></div>
  <div class="card"><div class="label">通过</div><div class="num" style="color:#22c55e">{passed}</div></div>
  <div class="card"><div class="label">失败</div><div class="num" style="color:#ef4444">{failed}</div></div>
  <div class="card"><div class="label">通过率</div><div class="num" style="color:#38bdf8">{pass_rate}%</div></div>
</div>
<p>测试用例数: {test_count}</p>
<h3>执行详情 (最近 {min(total, 20)} 条)</h3>
<table>
  <tr><th>ID</th><th>状态</th><th>耗时</th><th>开始时间</th></tr>
  {rows}
</table>
</body></html>"""
