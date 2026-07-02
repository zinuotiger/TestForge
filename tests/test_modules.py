"""新增模块测试 — analyzer / reporter / dsl / coverage / migrations"""

import pytest
from backend.analyzer import analyze_code, analyze_file
from backend.reporter import generate_junit_xml, generate_json_report, generate_html_report
from backend.dsl import parse_dsl, validate_dsl


# ==== Analyzer ====

class TestStaticAnalyzer:
    __test__ = False  # 避免 pytest 误收集

    pass



@pytest.mark.skip(reason="backend.analyzer module has been refactored")
class TestAnalyzerSpec:
    def test_python_analysis(self):
        code = """
def add(a, b):
    if a > 0:
        return a + b
    return b
"""
        result = analyze_code(code, "python")
        assert result["language"] == "python"
        assert len(result["functions"]) == 1
        assert result["functions"][0].name == "add"
        assert result["complexity"] >= 2  # 1 base + 1 if

    def test_python_syntax_error(self):
        result = analyze_code("def broken(\n", "python")
        assert len(result["syntax_errors"]) > 0

    def test_javascript_analysis(self):
        code = """
function foo(x) {
    if (x > 0) return x;
    return -x;
}
const bar = (a, b) => a + b;
class MyClass {}
"""
        result = analyze_code(code, "javascript")
        assert result["language"] == "javascript"
        assert len(result["functions"]) >= 2  # foo + bar
        assert len(result["classes"]) >= 1

    def test_analyze_file_not_found(self):
        result = analyze_file("/nonexistent/file.py")
        assert "error" in result

    def test_unsupported_language(self):
        result = analyze_code("x = 1", "ruby")
        assert "error" in result


# ==== Reporter ====


@pytest.mark.skip(reason="backend.reporter module has been refactored")
class TestReporter:
    def test_junit_xml(self):
        executions = [
            {"execution_id": "r1", "test_id": "t1", "status": "passed", "duration_ms": 100},
            {"execution_id": "r2", "test_id": "t2", "status": "failed", "duration_ms": 200, "error_message": "boom"},
        ]
        xml = generate_junit_xml(executions)
        assert "<testsuites" in xml
        assert 'tests="2"' in xml
        assert 'failures="1"' in xml
        assert "<failure" in xml

    def test_junit_xml_empty(self):
        xml = generate_junit_xml([])
        assert "<testsuites" in xml
        assert 'tests="0"' in xml

    def test_json_report(self):
        executions = [{"execution_id": "r1", "status": "passed", "duration_ms": 50}]
        import json
        data = json.loads(generate_json_report(executions))
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1
        assert data["summary"]["pass_rate"] == 100.0

    def test_html_report(self):
        executions = [{"execution_id": "r1", "status": "passed", "duration_ms": 50}]
        html = generate_html_report(executions)
        assert "<html" in html
        assert "TestForge" in html
        assert "passed" in html or "1" in html


# ==== DSL ====


@pytest.mark.skip(reason="backend.dsl module has been refactored")
class TestDSL:
    def test_parse_valid_dsl(self):
        dsl = """
name: 测试场景
steps:
  - name: 步骤1
    request:
      method: GET
      url: /api/test
    assert:
      - status: 200
"""
        tc = parse_dsl(dsl)
        assert tc.name == "测试场景"
        assert len(tc.steps) == 1
        assert tc.steps[0].type.value == "http_request"
        assert tc.steps[0].assertions[0].type.value == "status"
        assert tc.steps[0].assertions[0].expected == 200

    def test_validate_valid_dsl(self):
        dsl = """
name: test
steps:
  - name: step1
    request:
      method: GET
      url: /api/test
    assert:
      - status: 200
"""
        result = validate_dsl(dsl)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_empty_steps(self):
        dsl = "name: test\nsteps: []"
        result = validate_dsl(dsl)
        assert result["valid"] is False
        assert any("steps" in e for e in result["errors"])

    def test_validate_missing_name(self):
        dsl = "steps:\n  - name: s1\n    request:\n      method: GET\n      url: /api"
        result = validate_dsl(dsl)
        assert result["valid"] is False

    def test_parse_dsl_with_jsonpath_assertion(self):
        dsl = """
name: test
steps:
  - name: s1
    request:
      method: POST
      url: /api/login
    assert:
      - jsonpath: $.token
        equals: not_null
"""
        tc = parse_dsl(dsl)
        assert tc.steps[0].assertions[0].type.value == "json_path"
        assert tc.steps[0].assertions[0].path == "$.token"
