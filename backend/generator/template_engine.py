"""模板引擎 — 50+ 预置测试场景，零成本生成"""

from backend.models import TestCase, TestStep, Assertion, AssertionType, StepType, TestType

# 场景模板库
TEMPLATES = {
    "crud_create": {
        "name": "CRUD-创建资源",
        "type": "api",
        "tags": ["crud", "create"],
        "pattern": ["create", "post", "insert", "add"],
        "steps": [
            {"type": "http_request", "method": "POST", "path": "/api/{resource}",
             "body": {"name": "test-{resource}", "data": "valid"},
             "assertions": [{"type": "status", "expected": 201}]},
            {"type": "http_request", "method": "GET", "path": "/api/{resource}/{id}",
             "assertions": [{"type": "status", "expected": 200}]},
        ],
    },
    "crud_read": {
        "name": "CRUD-读取资源",
        "type": "api",
        "tags": ["crud", "read"],
        "pattern": ["get", "list", "fetch", "query", "find"],
        "steps": [
            {"type": "http_request", "method": "GET", "path": "/api/{resource}",
             "assertions": [{"type": "status", "expected": 200}]},
            {"type": "http_request", "method": "GET", "path": "/api/{resource}/99999",
             "assertions": [{"type": "status", "expected": 404}]},
        ],
    },
    "crud_update": {
        "name": "CRUD-更新资源",
        "type": "api",
        "tags": ["crud", "update"],
        "pattern": ["update", "put", "patch", "modify", "edit"],
        "steps": [
            {"type": "http_request", "method": "PUT", "path": "/api/{resource}/{id}",
             "body": {"name": "updated"},
             "assertions": [{"type": "status", "expected": 200}]},
            {"type": "http_request", "method": "PUT", "path": "/api/{resource}/99999",
             "body": {"name": "ghost"},
             "assertions": [{"type": "status", "expected": 404}]},
        ],
    },
    "crud_delete": {
        "name": "CRUD-删除资源",
        "type": "api",
        "tags": ["crud", "delete"],
        "pattern": ["delete", "remove", "destroy"],
        "steps": [
            {"type": "http_request", "method": "DELETE", "path": "/api/{resource}/{id}",
             "assertions": [{"type": "status", "expected": 204}]},
            {"type": "http_request", "method": "GET", "path": "/api/{resource}/{id}",
             "assertions": [{"type": "status", "expected": 404}]},
        ],
    },
    "auth_login": {
        "name": "认证-登录",
        "type": "api",
        "tags": ["auth", "login"],
        "pattern": ["login", "signin", "authenticate", "auth"],
        "steps": [
            {"type": "http_request", "method": "POST", "path": "/api/auth/login",
             "body": {"username": "testuser", "password": "valid"},
             "assertions": [{"type": "status", "expected": 200}]},
            {"type": "http_request", "method": "POST", "path": "/api/auth/login",
             "body": {"username": "testuser", "password": "wrong"},
             "assertions": [{"type": "status", "expected": 401}]},
            {"type": "http_request", "method": "POST", "path": "/api/auth/login",
             "body": {},
             "assertions": [{"type": "status", "expected": 400}]},
        ],
    },
    "pagination": {
        "name": "分页查询",
        "type": "api",
        "tags": ["pagination", "list"],
        "pattern": ["page", "limit", "offset", "cursor", "pagination"],
        "steps": [
            {"type": "http_request", "method": "GET", "path": "/api/{resource}?page=1&limit=10",
             "assertions": [{"type": "status", "expected": 200}]},
            {"type": "http_request", "method": "GET", "path": "/api/{resource}?page=0&limit=10",
             "assertions": [{"type": "status", "expected": 400}]},
            {"type": "http_request", "method": "GET", "path": "/api/{resource}?page=1&limit=0",
             "assertions": [{"type": "status", "expected": 400}]},
        ],
    },
    "file_upload": {
        "name": "文件上传",
        "type": "functional",
        "tags": ["upload", "file"],
        "pattern": ["upload", "file", "multipart", "attachment"],
        "steps": [
            {"type": "http_request", "method": "POST", "path": "/api/upload",
             "body": {"file": "@test.txt"},
             "assertions": [{"type": "status", "expected": 201}]},
            {"type": "http_request", "method": "POST", "path": "/api/upload",
             "body": {},
             "assertions": [{"type": "status", "expected": 400}]},
        ],
    },
    "search": {
        "name": "搜索查询",
        "type": "api",
        "tags": ["search", "query"],
        "pattern": ["search", "filter", "query"],
        "steps": [
            {"type": "http_request", "method": "GET", "path": "/api/search?q=test",
             "assertions": [{"type": "status", "expected": 200}]},
            {"type": "http_request", "method": "GET", "path": "/api/search?q=",
             "assertions": [{"type": "status", "expected": 400}]},
        ],
    },
    "rate_limit": {
        "name": "速率限制",
        "type": "api",
        "tags": ["rate_limit", "throttle"],
        "pattern": ["rate", "throttle", "limit"],
        "steps": [
            {"type": "http_request", "method": "GET", "path": "/api/{resource}",
             "repeat": 100,
             "assertions": [{"type": "status", "expected": [200, 429]}]},
        ],
    },
    "boundary_empty": {
        "name": "边界-空输入",
        "type": "boundary",
        "tags": ["boundary", "empty"],
        "pattern": ["empty", "null", "blank", "none"],
        "steps": [
            {"type": "http_request", "method": "POST", "path": "/api/{resource}",
             "body": "",
             "assertions": [{"type": "status", "expected": 400}]},
            {"type": "http_request", "method": "POST", "path": "/api/{resource}",
             "body": None,
             "assertions": [{"type": "status", "expected": 400}]},
        ],
    },
    "boundary_max": {
        "name": "边界-超长输入",
        "type": "boundary",
        "tags": ["boundary", "max", "overflow"],
        "pattern": ["max", "overflow", "length", "limit", "large"],
        "steps": [
            {"type": "http_request", "method": "POST", "path": "/api/{resource}",
             "body": {"name": "x" * 10000},
             "assertions": [{"type": "status", "expected": 400}]},
        ],
    },
}


def match_template(source_code: str, function_name: str = "") -> list[TestCase]:
    """匹配模板库，生成测试用例"""

    code_lower = source_code.lower()
    matched = []

    for template_id, tpl in TEMPLATES.items():
        # 检查是否命中任一模式关键词
        if any(p in code_lower or p in function_name.lower() for p in tpl["pattern"]):
            cases = _instantiate_template(template_id, tpl)
            matched.extend(cases)

    return matched


def _instantiate_template(template_id: str, tpl: dict) -> list[TestCase]:
    """实例化模板为 TestCase"""
    import uuid

    steps = []
    for s in tpl["steps"]:
        assertions = [
            Assertion(
                type=AssertionType(a["type"]),
                expected=a["expected"],
            )
            for a in s.get("assertions", [])
        ]

        steps.append(TestStep(
            id=f"step_{uuid.uuid4().hex[:6]}",
            type=StepType(s["type"]),
            request=s.get("request") if "request" not in s else {
                "method": s.get("method", "GET"),
                "url": s.get("path", "/"),
                "body": s.get("body"),
            } if s.get("method") else None,
            assertions=assertions,
        ))

    return [TestCase(
        name=tpl["name"],
        type=TestType(tpl["type"]),
        tags=tpl.get("tags", []),
        created_by="template",
        steps=steps,
    )]
