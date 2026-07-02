"""新增模块测试 — OpenAPI解析器 / HTTP执行器 / RAG / Scheduler / Agent"""

import pytest
import asyncio
from backend.generator.openapi_parser import (
    parse_openapi_content, _build_endpoint, Endpoint, ApiSpec,
)
from backend.generator.api_test_generator import (
    generate_api_tests, _make_happy_path, _make_empty_body_test,
    _make_not_found_test, _generate_sample_body, _generate_sample_value,
)
from backend.executors.http_executor import (
    _check_assertion, _extract_json_path, execute_http_test,
)
from backend.core.rag import TestCaseVectorStore as VectorStore
from backend.core.scheduler import ScanTask, ScanScheduler
from backend.core.agent import AGENT_TOOLS, TestAgent as AgentEngine


# ==== OpenAPI 解析器 ====

class TestOpenAPIParser:
    def test_parse_swagger2_json(self):
        swagger = """
        {
          "swagger": "2.0",
          "info": {"title": "Test API", "version": "1.0.0"},
          "host": "api.example.com",
          "basePath": "/v1",
          "paths": {
            "/users": {
              "get": {"summary": "List users", "responses": {"200": {"description": "OK"}}},
              "post": {"summary": "Create user", "responses": {"201": {"description": "Created"}}}
            },
            "/users/{id}": {
              "get": {"summary": "Get user", "responses": {"200": {"description": "OK"}}}
            }
          }
        }
        """
        spec = parse_openapi_content(swagger, base_url="")
        assert spec.title == "Test API"
        assert spec.version == "1.0.0"
        assert spec.base_url == "http://api.example.com/v1"
        assert len(spec.endpoints) == 3
        assert spec.endpoints[0].method == "GET"
        assert spec.endpoints[0].path == "/users"

    def test_parse_openapi3_yaml(self):
        openapi = """
        openapi: 3.0.0
        info:
          title: My API
          version: 2.0.0
        servers:
          - url: https://api.test.com
        paths:
          /items:
            get:
              summary: List items
              responses:
                '200':
                  description: OK
        """
        spec = parse_openapi_content(openapi, base_url="")
        assert spec.title == "My API"
        assert spec.version == "2.0.0"
        assert spec.base_url == "https://api.test.com"
        assert len(spec.endpoints) == 1
        assert spec.endpoints[0].method == "GET"

    def test_parse_invalid_content(self):
        with pytest.raises(ValueError):
            parse_openapi_content("not a valid document")

    def test_build_endpoint(self):
        spec = {
            "summary": "Test",
            "operationId": "testOp",
            "parameters": [{"name": "id", "in": "path"}],
            "responses": {"200": {"description": "OK"}, "404": {"description": "NF"}},
            "tags": ["users"],
        }
        ep = _build_endpoint("/test", "get", spec)
        assert ep.path == "/test"
        assert ep.method == "GET"
        assert ep.summary == "Test"
        assert ep.operation_id == "testOp"
        assert len(ep.parameters) == 1
        assert ep.tags == ["users"]


# ==== API 测试生成器 ====

class TestApiTestGenerator:
    def _make_spec(self):
        return ApiSpec(
            title="Test",
            version="1.0",
            base_url="https://api.test.com",
            endpoints=[
                Endpoint(path="/users", method="GET", responses={"200": {}}),
                Endpoint(path="/users", method="POST", responses={"201": {}}, request_body={"type": "object"}),
                Endpoint(path="/users/{id}", method="GET", responses={"200": {}},
                         parameters=[{"name": "id", "in": "path"}]),
            ],
        )

    def test_generate_api_tests(self):
        spec = self._make_spec()
        cases = generate_api_tests(spec)
        assert len(cases) > 0
        # GET /users: happy + 404 = 2
        # POST /users: happy + empty_body + 404 = 3
        # GET /users/{id}: happy + invalid_id + 404 = 3
        assert len(cases) >= 8

    def test_happy_path(self):
        ep = Endpoint(path="/test", method="GET", responses={"200": {}})
        tc = _make_happy_path("https://api.test.com", ep)
        assert tc.type.value == "api"
        assert tc.created_by == "openapi"
        assert len(tc.steps) == 1
        assert tc.steps[0].request["method"] == "GET"
        assert tc.steps[0].assertions[0].expected == 200

    def test_empty_body_test(self):
        ep = Endpoint(path="/test", method="POST", responses={"201": {}})
        tc = _make_empty_body_test("https://api.test.com", ep)
        assert tc.steps[0].request["body"] == ""
        assert isinstance(tc.steps[0].assertions[0].expected, list)

    def test_not_found_test(self):
        ep = Endpoint(path="/test", method="GET")
        tc = _make_not_found_test("https://api.test.com", ep)
        assert "/nonexistent_deep_path" in tc.steps[0].request["url"]
        assert tc.steps[0].assertions[0].expected == 404

    def test_generate_sample_value(self):
        assert _generate_sample_value({"type": "string"}) == "test_value"
        assert _generate_sample_value({"type": "string", "format": "email"}) == "test@example.com"
        assert _generate_sample_value({"type": "integer"}) == 1
        assert _generate_sample_value({"type": "boolean"}) is True
        assert _generate_sample_value({"type": "array"}) == []
        assert _generate_sample_value({"type": "string", "example": "custom"}) == "custom"

    def test_generate_sample_body_object(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        body = _generate_sample_body(schema)
        assert body["name"] == "test_value"
        assert body["age"] == 1


# ==== HTTP 执行器 ====

class TestHttpExecutor:
    def test_check_assertion_status_pass(self):
        a = {"type": "status", "expected": 200}
        r = _check_assertion(a, {"status": 200})
        assert r["passed"] is True

    def test_check_assertion_status_fail(self):
        a = {"type": "status", "expected": 200}
        r = _check_assertion(a, {"status": 404})
        assert r["passed"] is False

    def test_check_assertion_status_list(self):
        a = {"type": "status", "expected": [200, 201]}
        assert _check_assertion(a, {"status": 200})["passed"] is True
        assert _check_assertion(a, {"status": 201})["passed"] is True
        assert _check_assertion(a, {"status": 400})["passed"] is False

    def test_check_assertion_contains(self):
        a = {"type": "contains", "expected": "hello"}
        r = _check_assertion(a, {"response_body": "say hello world"})
        assert r["passed"] is True

    def test_extract_json_path(self):
        body = '{"user": {"name": "Alice", "age": 30}}'
        assert _extract_json_path(body, "$.user.name") == "Alice"
        assert _extract_json_path(body, "$.user.age") == 30
        assert _extract_json_path(body, "$.user.email") is None

    def test_extract_json_path_invalid_json(self):
        assert _extract_json_path("not json", "$.test") is None

    @pytest.mark.asyncio
    async def test_execute_http_test_empty_url(self):
        result = await execute_http_test({"request": {}, "assertions": []})
        assert result["passed"] is False
        assert "URL" in result["error"]


# ==== RAG ====

class TestRAG:
    def test_vector_store_add_and_search(self):
        store = VectorStore()
        tc1 = {"name": "用户登录测试", "type": "api", "tags": ["auth"],
               "steps": [{"description": "POST /login", "request": {"method": "POST", "url": "/api/login"},
                          "assertions": [{"type": "status", "expected": 200}]}]}
        tc2 = {"name": "商品搜索测试", "type": "api", "tags": ["search"],
               "steps": [{"description": "GET /search", "request": {"method": "GET", "url": "/api/search"},
                          "assertions": [{"type": "status", "expected": 200}]}]}
        store.add_batch([tc1, tc2])
        assert store.size() == 2

        # 搜索登录相关
        results = store.search("login auth POST", top_k=2)
        assert len(results) > 0
        # 第一个结果应该是登录测试
        assert "login" in results[0]["tc"]["name"].lower() or "登录" in results[0]["tc"]["name"]

    def test_vector_store_empty_search(self):
        store = VectorStore()
        assert store.search("anything") == []
        assert store.size() == 0

    def test_vector_store_clear(self):
        store = VectorStore()
        store.add({"name": "test"})
        assert store.size() == 1
        store.clear()
        assert store.size() == 0


# ==== Scheduler ====

class TestScheduler:
    def test_scan_task_creation(self):
        task = ScanTask(
            task_id="t1", name="Test", url="https://api.test.com/swagger.json",
            interval_minutes=30, alert_emails=["test@test.com"],
        )
        assert task.task_id == "t1"
        assert task.name == "Test"
        assert task.interval == 30
        assert task.alert_emails == ["test@test.com"]
        assert task.enabled is True
        assert task.run_count == 0

    def test_scan_task_to_dict(self):
        task = ScanTask(task_id="t1", name="Test", url="https://api.test.com")
        d = task.to_dict()
        assert d["task_id"] == "t1"
        assert d["name"] == "Test"
        assert d["interval_minutes"] == 60
        assert d["enabled"] is True

    def test_scheduler_add_remove_task(self):
        scheduler = ScanScheduler()
        task = ScanTask(task_id="t1", name="Test", url="https://api.test.com")
        scheduler.add_task(task)
        assert scheduler.get_task("t1") is not None
        assert len(scheduler.list_tasks()) == 1

        scheduler.remove_task("t1")
        assert scheduler.get_task("t1") is None
        assert len(scheduler.list_tasks()) == 0

    def test_scheduler_alerts_initial_empty(self):
        scheduler = ScanScheduler()
        assert scheduler.get_alerts() == []


# ==== Agent ====

import pytest

class TestAgent:
    @pytest.mark.agent
    def test_agent_tools_defined(self):
        tool_names = [t["function"]["name"] for t in AGENT_TOOLS]
        assert "analyze_code" in tool_names
        assert "generate_tests" in tool_names
        assert "execute_tests" in tool_names
        assert "scan_security" in tool_names
        assert "finish" in tool_names

    @pytest.mark.agent
    def test_agent_init(self):
        agent = AgentEngine(max_iterations=5)
        assert agent.max_iterations == 5
        assert agent.conversation == []
        assert agent.tool_calls_log == []
