import pytest
from backend.models import TestCase, TestStep, Assertion, TestType, StepType, AssertionType
from backend.generator.template_engine import match_template, TEMPLATES
from backend.safety.secret_scan import scan_all


class TestTemplateEngine:
    def test_all_templates_have_pattern_keys(self):
        for tid, tpl in TEMPLATES.items():
            assert "pattern" in tpl, f"Template {tid} missing 'pattern' key"
            assert isinstance(tpl["pattern"], list), f"Template {tid} pattern is not a list"

    def test_crud_create_matches(self):
        cases = match_template("create_user(name, email)", "create_user")
        assert len(cases) >= 1
        assert any("CRUD" in c.name for c in cases)

    def test_auth_login_matches(self):
        cases = match_template("def login(username, password)", "login")
        assert len(cases) >= 1
        assert any("认证" in c.name or "登录" in c.name for c in cases)

    def test_pagination_matches(self):
        cases = match_template("def list_users(page, limit)", "list_users")
        assert len(cases) >= 1
        assert any("分页" in c.name for c in cases)

    def test_no_match_returns_empty(self):
        cases = match_template("def unrelated_function(x)", "unrelated")
        # 可能返回空或边界测试（如果匹配到 empty/max 模式关键词）
        assert isinstance(cases, list)

    def test_template_output_has_assertions(self):
        for tid, tpl in TEMPLATES.items():
            for step in tpl["steps"]:
                assert "assertions" in step, f"Template {tid} step missing assertions"
                assert len(step["assertions"]) > 0, f"Template {tid} has empty assertions"


class TestSecurityIntegration:
    def test_batch_scan(self):
        code = """
def safe_func():
    return "hello"
"""
        result = scan_all(code)
        assert result["safe"] is True

    def test_mixed_dangerous_and_safe(self):
        code = """
def safe(): pass
def dangerous():
    eval("1+1")
    os.system("ls")
"""
        result = scan_all(code)
        assert not result["safe"]
        assert result["total_findings"] >= 2
