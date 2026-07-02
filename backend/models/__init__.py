"""数据模型基类"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any, ClassVar
from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    ACTIVE = "active"
    QUARANTINE = "quarantine"
    DEPRECATED = "deprecated"


class TestType(str, Enum):
    __test__ = False  # 避免 pytest 误收集
    FUNCTIONAL = "functional"
    BOUNDARY = "boundary"
    API = "api"
    E2E = "e2e"
    UNIT = "unit"
    PERFORMANCE = "performance"


class StepType(str, Enum):

# Backward compatibility alias
    HTTP_REQUEST = "http_request"
    BROWSER_ACTION = "browser_action"
    CODE_EXEC = "code_exec"
    DB_QUERY = "db_query"
    SCRIPT = "script"
    ASSERTION = "assertion"



class AssertionType(str, Enum):
    STATUS = "status"
    JSON_PATH = "json_path"
    JSON_SCHEMA = "json_schema"
    EQUALS = "equals"
    CONTAINS = "contains"
    REGEX = "regex"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


# ---- 测试用例模型 ----

class Assertion(BaseModel):
    model_config = {"populate_by_name": True}
    type: AssertionType
    expected: Any = None
    path: Optional[str] = None
    json_schema: Optional[dict] = Field(None, alias="schema")


class TestStep(BaseModel):
    __test__ = False  # 避免 pytest 误收集（ClassVar 兼容）
    id: str
    type: StepType
    description: Optional[str] = None
    request: Optional[dict] = None       # HTTP请求体
    action: Optional[str] = None         # 浏览器操作
    connection: Optional[str] = None     # DB连接
    query: Optional[str] = None          # SQL/脚本
    assertions: list[Assertion] = []


class TestCase(BaseModel):
    __test__ = False  # 避免 pytest 误收集
    id: str = Field(default_factory=lambda: f"tc_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    name: str
    type: TestType = TestType.FUNCTIONAL
    tags: list[str] = []
    status: TestStatus = TestStatus.ACTIVE
    flaky_score: float = 0.0
    health_score: float = 100.0
    created_by: str = "manual"
    variables: dict[str, str] = {}
    steps: list[TestStep] = []
    boundary_expansion: Optional[dict] = None
    impact_analysis: Optional[dict] = None


# ---- 执行模型 ----

class ExecutionResult(BaseModel):
    execution_id: str
    test_id: str
    status: ExecutionStatus
    duration_ms: int = 0
    error_message: Optional[str] = None
    logs: list[str] = []
    screenshots: list[str] = []
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class RunRequest(BaseModel):
    path: str = "."
    strategy: str = "smart"       # smart | smoke | full
    test_types: list[str] = []    # 留空=全部
    llm_mode: str = "api"         # api | local


# Backward compatibility alias
TestStepType = StepType
