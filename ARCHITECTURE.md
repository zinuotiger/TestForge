# TestForge 模块开发文档

> TestForge 是一个 AI 驱动的智能测试生成与执行平台，覆盖测试设计、生成、执行、分析、自愈、自进化全生命周期。
>
> - 代码规模：约 34,000 行（后端 Python + 前端 TSX/TS）
> - 后端：~100 个 Python 文件，FastAPI 框架
> - 前端：18 个 TSX/TS 文件，React + Vite
> - API 路由：~120 个端点
> - 前端页面：14 个
>
> 本文档按模块划分，共 12 个后端模块 + 4 个前端模块 + 3 个基础设施模块。

---

## 目录

- [后端模块](#后端模块)
  - [1. API 层 (`backend/api/`)](#1-api-层-backendapi)
  - [2. 核心引擎 (`backend/core/`)](#2-核心引擎-backendcore)
  - [3. 生成器 (`backend/generator/`)](#3-生成器-backendgenerator)
  - [4. 执行器 (`backend/executors/`)](#4-执行器-backendexecutors)
  - [5. 静态分析 (`backend/analyzer/`)](#5-静态分析-backendanalyzer)
  - [6. 安全 (`backend/safety/`)](#6-安全-backendsafety)
  - [7. 质量 (`backend/quality/`)](#7-质量-backendquality)
  - [8. 报告 (`backend/reporter/`)](#8-报告-backendreporter)
  - [9. 集成 (`backend/integrations/`)](#9-集成-backendintegrations)
  - [10. 数据层 (`backend/models/`)](#10-数据层-backendmodels)
  - [11. DSL (`backend/dsl/`)](#11-dsl-backenddsl)
  - [12. 配置 (`backend/config.py`)](#12-配置-backendconfigpy)
- [前端模块](#前端模块)
  - [13. 页面 (`frontend/src/pages/`)](#13-页面-frontendsrcpages)
  - [14. 认证 (`frontend/src/auth.tsx`)](#14-认证-frontendsrcauthtsx)
  - [15. API 客户端 (`frontend/src/api.ts`)](#15-api-客户端-frontendsrcapits)
  - [16. 路由布局 (`frontend/src/App.tsx`)](#16-路由布局-frontendsrcapptsx)
- [基础设施](#基础设施)
  - [17. CLI (`cli/`)](#17-cli-cli)
  - [18. Docker (`docker/`)](#18-docker-docker)
  - [19. 测试 (`tests/`)](#19-测试-tests)
- [附录](#附录)
  - [模块依赖关系图](#模块依赖关系图)
  - [数据流图](#数据流图)
  - [7 个闭环系统图](#7-个闭环系统图)
  - [技术栈一览表](#技术栈一览表)

---

# 后端模块

## 1. API 层 (`backend/api/`)

### 职责描述

API 层是 TestForge 与前端/外部系统的统一入口，基于 FastAPI 实现。负责接收 HTTP/WebSocket 请求、参数校验、鉴权、调用核心引擎、返回结构化响应。所有路由在 `backend/main.py` 中通过 `include_router` 挂载，并统一添加 CORS、限流、TraceID 中间件。

LLM 密集型端点（`/api/website`、`/api/intelligence`）额外挂载独立的 LLM 限流依赖（默认 10 次/60 秒/IP）。

### 文件清单

| 文件 | 行数 | 路由前缀 | 路由数 | 核心职责 |
|------|------|----------|--------|----------|
| `auth_api.py` | 204 | `/api/auth` | 10 | 登录/刷新/登出/用户管理/API Token/容错状态 |
| `tests.py` | 87 | `/api/tests` | 6 | 测试用例 CRUD + 隔离（quarantine） |
| `executions.py` | 364 | `/api/executions` | 11 | 执行触发/查询/影响分析/Flaky/健康度/自愈/取消/日志 |
| `reports.py` | 113 | `/api/reports` | 10 | HTML/JSON/JUnit 报告 + 徽章 + Allure + 趋势 |
| `settings_api.py` | 227 | `/api/settings` | 5 | LLM Provider 配置/测试 + SMTP 邮件配置/测试 |
| `analysis.py` | 46 | `/api/analysis` | 7 | 静态分析/覆盖率/变异 + DSL 解析校验 + Keploy 集成 |
| `website.py` | 669 | `/api/website` | 17 | OpenAPI 扫描/爬虫/自动化测试/Browser Agent（四大功能） |
| `agent_api.py` | 257 | `/api/intelligence` | 21 | Agent 运行/流式/多 Agent/LangGraph/RAG/调度/浏览器 Agent/记忆/E2E |
| `import_export.py` | 336 | `/api/tests` | 2 | 测试用例导入/导出（JSON、Postman、OpenAPI） |
| `recording.py` | 76 | `/api/record` | 7 | 浏览器录制/API 流量录制启停 + 解析 |
| `token_usage.py` | 55 | `/api/token-usage` | 8 | Token 用量统计（按模型/场景/Provider）+ 预算 + 重置 |
| `code_test.py` | 266 | `/api/code` | 4 | 代码综合测试/仅生成/仅执行/项目级测试 |
| `evolution.py` | 129 | `/api` | 11 | 自进化事件上报/知识库/策略推荐/跨项目迁移/统计 |
| `websocket.py` | 41 | `/ws` | 1 | WebSocket 事件推送（pipeline 实时进度） |
| `__init__.py` | 0 | - | - | 包初始化 |

> 合计约 15 个路由文件，~120 个端点。`main.py`（205 行）额外提供 `/api/health`、`/api/health/readiness`、`/api/metrics` 三个全局端点。

### 核心端点说明

#### auth_api.py（认证与用户管理）
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 用户登录，返回 access_token + refresh_token |
| `/api/auth/refresh` | POST | 刷新 access_token |
| `/api/auth/logout` | POST | 登出（吊销 token） |
| `/api/auth/me` | GET | 获取当前用户信息 + 权限 |
| `/api/auth/api-token` | POST | 生成 API Token（长期） |
| `/api/auth/users` | GET/POST | 用户列表/创建用户（Admin） |
| `/api/auth/users/{username}` | PUT/DELETE | 更新/删除用户 |
| `/api/auth/resilience` | GET | 容错模块状态（熔断器/吞吐量监控） |

#### executions.py（执行与分析）
- `POST /api/executions/run` — 触发测试执行（smart/smoke/full 策略）
- `GET /api/executions/{run_id}` — 查询执行结果
- `POST /api/executions/analyze/impact` — 测试影响分析（TIA）
- `GET /api/executions/analyze/flaky` — Flaky 测试检测
- `GET /api/executions/analyze/health` — 健康度评分
- `GET /api/executions/analyze/trend` — 执行趋势
- `POST /api/executions/heal/{test_id}` — 单测试自愈
- `POST /api/executions/heal` — 批量自愈
- `POST /api/executions/{run_id}/cancel` — 取消执行
- `GET /api/executions/{run_id}/log` — 执行日志

#### website.py 四大功能

`website.py` 是 API 层最复杂的文件（669 行），承载四大核心功能：

| 功能 | 端点 | 说明 |
|------|------|------|
| **OpenAPI 扫描** | `POST /scan` | 解析 OpenAPI/Swagger 文档，生成 API 测试用例（支持 v2/v3） |
| **网站爬虫** | `POST /crawl` | 爬取网站页面，提取表单、链接、页面结构（`web_crawler.py`） |
| **自动化测试** | `POST /auto-test`、`POST /comprehensive-test` | 自动化功能测试 + 综合测试（含压测、特性检测） |
| **Browser Agent** | `POST /agent/run`、`POST /agent/multi-run`、`POST /agent/visual-locate`、`POST /browser/execute` | AI 浏览器代理（单/多 Agent + VLM 视觉定位 + Playwright 执行） |

辅助端点：`/parse`（解析 OpenAPI）、`/export`（导出）、`/email`（邮件发送）、`/send-report`（发送报告邮件）、`/agent/browser-status`、`/agent/actions`、`/agent/memory/*`。

#### agent_api.py（智能体编排）
- Agent 系统：`/agent/run`、`/agent/stream`（流式）、`/multi-agent/run`、`/multi-agent/status`
- LangGraph：`/langgraph/available`、`/langgraph/structure`、`/langgraph/run`
- RAG：`/rag/generate`、`/rag/stats`、`/rag/reload`、`/rag/search`
- 调度：`/schedule/tasks`（CRUD）、`/schedule/alerts`
- Browser Agent：`/browser-agent/run`、`/browser-multi-agent/run`、`/browser-agent/status`
- Agent 记忆：`/agent-memory/stats`、`/agent-memory/search`
- E2E：`/e2e/status`、`/e2e/run`

### 数据流

```
HTTP 请求 → CORSMiddleware → RateLimitMiddleware → TraceIDMiddleware
         → 路由匹配 → 依赖注入（鉴权/限流）→ 端点处理函数
         → 调用 core/generator/executors → 返回 JSON/StreamingResponse
```

### 依赖关系

- 向下依赖：`backend.core.*`、`backend.generator.*`、`backend.executors.*`、`backend.analyzer.*`、`backend.safety.*`、`backend.models.*`、`backend.reporter.*`、`backend.integrations.*`、`backend.dsl.*`
- 横向依赖：`backend.config.settings`
- 被依赖：`backend.main`（挂载路由）、前端 `api.ts`、CLI

### 配置项

- `TESTFORGE_RATE_LIMIT_MAX_REQUESTS`：全局限流（默认 200/分钟）
- `TESTFORGE_RATE_LIMIT_WINDOW_SECONDS`：限流窗口（默认 60 秒）
- LLM 端点独立限流：`llm_rate_limit(max_requests=10, window=60)`

---

## 2. 核心引擎 (`backend/core/`)

### 职责描述

核心引擎是 TestForge 的"大脑"，承载 Agent 系统、分析引擎、自愈系统、自进化系统、RAG 检索、流水线编排、调度器等核心能力。共 25 个文件，是代码量最大、复杂度最高的模块。

### 文件清单（按子领域分组）

#### Agent 系统

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `agent.py` | 412 | `TestAgent` | ReAct 单 Agent，最大 8 次迭代，含 LLM 调用与工具执行 |
| `multi_agent.py` | 539 | `OrchestratorAgent`、`AnalystAgent`、`GeneratorAgent`、`ExecutorAgent`、`ReviewerAgent`、`MultiAgentSystem` | 5 角色多 Agent 协作系统 |
| `multi_agent_base.py` | 323 | `BaseAgent`、`AgentRole`、`AgentState`、`AgentMessage`、`AgentMemory` | 多 Agent 基类与共享数据结构 |
| `langgraph_agent.py` | 393 | `AgentState` | 基于 LangGraph StateGraph 的图式 Agent |
| `streaming_agent.py` | 185 | - | 流式 Agent 输出（SSE） |
| `agent_memory.py` | 288 | `AgentMemory`、`Experience`、`ExperienceType` | Agent 经验记忆库 |
| `browser_agent.py` | 778 | `AgentStep`、`AgentResult` | 浏览器自动化 Agent（单 Agent） |
| `browser_multi_agent.py` | 284 | `AnalystAgent`、`ExecutorAgent`、`VerifierAgent`、`MultiAgentReport` | 浏览器多 Agent（分析→执行→验证） |
| `browser_self_healer.py` | 248 | `BrowserSelfHealer`、`HealEvent`、`HealStats` | 浏览器测试自愈（选择器修复） |
| `designer.py` | 244 | `TestDesigner` | 测试设计器（边界用例、场景设计） |
| `dependencies.py` | 64 | - | 依赖分析工具 |

#### 分析引擎

| 文件 | 行数 | 核心类 | 关键方法 |
|------|------|--------|----------|
| `tia_engine.py` | 269 | `TIAEngine` | `build_index()`、`analyze(changed_files)`、`get_diff()`、`_reverse_call_chain()`、`_prioritize()`、`_calc_acceleration()` |
| `flaky_detector.py` | 102 | `FlakyDetector` | Flaky 测试检测（多次重跑稳定性分析） |
| `health_scorer.py` | 79 | `HealthScorer` | 测试健康度评分（0-100） |

#### 自愈系统

| 文件 | 行数 | 核心类 | 关键方法 |
|------|------|--------|----------|
| `self_healer.py` | 257 | `SelfHealer`、`HealLayer` | `heal_ui_selector()`、`heal_api_schema()`、`heal_assertion()`、`_heal_with_playwright()`、`_generate_candidates()` |

> 自愈支持三层：UI 选择器修复（Playwright 验证）、API Schema 修复、断言修复。

#### 自进化系统

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `self_evolution.py` | 466 | `EvolutionEventType`、`StrategyType`、`StrategyPerformance`、`KnowledgeEntry`、`EvolutionDB`、`KnowledgeBuilder`、`StrategyAdapter`、`ProjectTransfer`、`EvolutionLoop` | Thompson 采样 + 知识库 + 跨项目策略迁移 |

> `EvolutionLoop` 是自进化核心，包含策略权重更新（Thompson 采样）、知识库构建、跨项目迁移、事件历史。

#### RAG 检索

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `rag.py` | 284 | `EmbeddingModel`、`ChromaVectorStore`、`TestCaseVectorStore`、`UnifiedVectorStore` | ChromaDB + BGE + TF-IDF 三级降级 |

> 三级降级：BGE 本地模型 → ChromaDB 默认 embedding → TF-IDF 关键词匹配。

#### 流水线与调度

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `pipeline.py` | 227 | `PipelineEngine`、`StageStatus` | 12 阶段流水线编排，支持订阅/暂停/取消/进度推送 |
| `scheduler.py` | 165 | `ScanTask`、`ScanScheduler` | CRON 定时巡检 + 告警 |

#### 其他

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `token_tracker.py` | 248 | `TokenTracker`、`UsageRecord` | Token 用量追踪（按模型/场景/Provider） |
| `visual_locator.py` | 318 | - | VLM 视觉定位（截图→元素坐标） |
| `web_crawler.py` | 646 | `CrawlResult`、`PageInfo`、`FormInfo` | 网站爬虫（页面/表单/链接提取） |
| `web_auto_tester.py` | 898 | `AutoTestResult`、`WebsiteTestCase`、`CheckItem` | 网站自动化测试生成 |
| `website_test_engine.py` | 668 | `ComprehensiveTestResult`、`WebsiteFeature`、`StressResult` | 网站综合测试引擎（含压测） |
| `boundary_engine.py` | 267 | `BoundaryEngine`、`ParameterSpec`、`BoundaryCase` | 边界值测试用例生成 |

### 核心类详解

#### `TestAgent`（单 Agent）
```python
class TestAgent:
    def __init__(self, max_iterations: int = 8)
    async def run(self, source_code: str, task: str = "") -> dict
    async def _call_llm(self) -> dict          # ReAct 推理
    async def _execute_tool(self, name, args)  # 工具调用
```

#### `MultiAgentSystem`（5 角色协作）
- `OrchestratorAgent`：编排者，拆分任务并分派
- `AnalystAgent`：分析者，理解需求与代码
- `GeneratorAgent`：生成者，产出测试用例
- `ExecutorAgent`：执行者，运行测试
- `ReviewerAgent`：审查者，评估质量并反馈

#### `PipelineEngine`（流水线）
- 12 阶段：需求分析 → 静态分析 → 测试设计 → 用例生成 → 去重 → 执行 → 覆盖率 → 变异测试 → 质量门禁 → 报告 → 自愈 → 自进化
- 事件订阅模型：`subscribe(callback)` → 推送 `stage_start/stage_complete/stage_error/stage_progress/test_result/gate_result/alert`
- 进化闭环集成：`run_evolution_cycle()` 在执行后自动调用

### 数据流

```
用户请求 → API 层 → core.pipeline 编排 → 调用 generator 生成用例
         → 调用 executors 执行 → core.tia_engine 影响分析
         → core.self_healer 自愈 → core.self_evolution 进化更新
         → core.rag 向量检索/写入 → WebSocket 推送进度
```

### 依赖关系

- 依赖：`backend.config`、`backend.models`、`backend.generator`、`backend.executors`、`backend.analyzer`、`backend.safety`
- 被依赖：`backend.api`、`backend.main`、`cli`

### 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_AGENT_MAX_ITERATIONS` | 8 | Agent 最大迭代次数 |
| `TESTFORGE_AGENT_TIMEOUT_SECONDS` | 300 | Agent 超时 |
| `TESTFORGE_AGENT_TEMPERATURE` | 0.2 | Agent 推理温度 |
| `TESTFORGE_RAG_EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | RAG embedding 模型 |
| `TESTFORGE_RAG_TOP_K` | 5 | RAG 检索 top K |
| `TESTFORGE_RAG_SIMILARITY_THRESHOLD` | 0.7 | 相似度阈值 |

---

## 3. 生成器 (`backend/generator/`)

### 职责描述

生成器模块实现"五策略"测试用例生成，通过智能路由器按进化权重动态排序策略，融合多策略结果并去重。是 TestForge 测试生成的核心。

### 文件清单

| 文件 | 行数 | 核心类/函数 | 说明 |
|------|------|-------------|------|
| `router.py` | 114 | `route_generation()`、`_get_dynamic_strategy_order()`、`record_strategy()` | 策略路由器（核心入口） |
| `ai_generator.py` | 189 | `generate_tests()`、`_build_prompt()`、`_parse_response()`、`_fallback_test()` | LLM 调用生成 |
| `template_engine.py` | 186 | `match_template()`、`_instantiate_template()` | 模板匹配生成 |
| `property_generator.py` | 95 | `generate_property_tests()`、`_roundtrip_test()`、`_idempotent_test()`、`_commutative_test()`、`_invariant_test()` | 属性测试（4 类性质） |
| `search_generator.py` | 107 | `SearchGenerator` | 模糊测试（随机搜索） |
| `traffic_generator.py` | 391 | `TrafficGenerator` | 流量录制回放生成 |
| `openapi_parser.py` | 143 | `Endpoint`、`ApiSpec`、`parse_openapi_content()`、`_parse_swagger2()`、`_parse_openapi3()` | OpenAPI/Swagger 解析 |
| `api_test_generator.py` | 188 | `generate_api_tests()`、`_make_happy_path()`、`_make_empty_body_test()`、`_make_invalid_id_test()`、`_make_not_found_test()` | API 测试用例生成（4 类场景） |
| `recorder.py` | 153 | `BrowserRecorder` | 浏览器录制 |
| `__init__.py` | 0 | - | 包初始化 |

### 五策略说明

| 策略 | 触发条件 | 实现文件 |
|------|----------|----------|
| `template` | 代码匹配已知模板（函数签名/模式） | `template_engine.py` |
| `property` | 检测到可测性质（roundtrip/idempotent/commutative/invariant） | `property_generator.py` |
| `ai` | 通用场景，调用 LLM 生成 | `ai_generator.py` |
| `search` | 模糊测试场景，随机输入探索 | `search_generator.py` |
| `traffic` | 存在流量录制数据 | `traffic_generator.py` |

### 融合机制

`route_generation()` 流程：
1. **RAG 检索**：从向量库检索相似历史用例，注入生成上下文
2. **动态排序**：调用 `evolution_loop.get_recommended_strategies()` 按 Thompson 采样权重排序策略
3. **顺序执行**：依次调用各策略 handler，结果合并
4. **去重**：按 `TestCase.name` 去重
5. **RAG 写入**：将生成用例写回向量库
6. **进化反馈**：异步调用 `evolution_loop.on_strategy_called()` 更新策略权重

```python
# 默认顺序（无进化数据时回退）
DEFAULT_ORDER = ["template", "property", "ai", "search", "traffic"]
```

### 数据流

```
源代码 → RAG 检索相似用例 → 进化权重排序策略 → 顺序执行五策略
       → 合并去重 → RAG 写入 → 返回 list[TestCase]
       → 异步：进化闭环更新策略权重
```

### 依赖关系

- 依赖：`backend.models.TestCase`、`backend.core.self_evolution`、`backend.core.rag`
- 被依赖：`backend.api.code_test`、`backend.api.website`、`backend.api.agent_api`

---

## 4. 执行器 (`backend/executors/`)

### 职责描述

执行器模块负责真实执行测试用例并收集结果。支持 Python/JS 代码沙箱、REST API、Playwright 浏览器、数据库、Shell 脚本五类执行器。

### 文件清单

| 文件 | 行数 | 核心类/函数 | 说明 |
|------|------|-------------|------|
| `code_executor.py` | 172 | `execute_pytest()`、`execute_code()` | Python/JS 沙箱执行 + pytest 集成 |
| `http_executor.py` | 194 | `execute_http_test()` | REST API 测试执行（aiohttp） |
| `browser_executor.py` | 374 | `is_playwright_available()`、`check_browser_status()`、浏览器执行函数 | Playwright 浏览器执行 |
| `db_executor.py` | 214 | `DBExecutor` | MySQL/PostgreSQL 数据库测试 |
| `script_executor.py` | 158 | `ScriptExecutor` | Shell/Bat 脚本执行 |
| `__init__.py` | 0 | - | 包初始化 |

### 沙箱安全机制

- **代码执行**：`subprocess` + 超时控制（`asyncio.wait_for`），失败/超时自动 kill 进程
- **覆盖率收集**：pytest 集成 `--cov` 参数，输出 JSON 覆盖率报告
- **环境隔离**：执行目录隔离（`cwd=test_path.parent`），避免污染主进程

### 核心执行流程

#### `execute_pytest()`
```
检查文件存在 → 构造 pytest 命令（含 --cov） → subprocess 异步执行
            → 超时 kill → 解析输出（pass/fail/coverage） → 返回结果 dict
```

#### `execute_http_test()`
```
解析 step（method/url/headers/body） → aiohttp 发送请求
         → 收集 response（status/body/headers/duration） → 执行断言 → 返回结果
```

### 数据流

```
TestCase.steps → 按 StepType 分发 → code/http/browser/db/script 执行器
              → 收集 ExecutionResult（status/duration/logs/screenshots）
```

### 依赖关系

- 依赖：`backend.config`、`backend.models`
- 被依赖：`backend.api.executions`、`backend.api.code_test`、`backend.api.website`、`backend.core.pipeline`

### 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_SANDBOX_ENABLED` | true | 是否启用沙箱 |
| `TESTFORGE_MAX_WORKERS` | 4 | 最大并发执行数 |
| `TESTFORGE_TIMEOUT_PER_TEST` | 30 | 单测试超时（秒） |
| `TESTFORGE_TIMEOUT_TOTAL` | 1800 | 总执行超时（秒） |
| `TESTFORGE_HTTP_TEST_MAX_CONCURRENCY` | 10 | HTTP 测试并发数 |
| `TESTFORGE_HTTP_TEST_MAX_TESTS` | 30 | HTTP 测试最大数 |
| `TESTFORGE_HTTP_TEST_TIMEOUT` | 8 | 单 HTTP 请求超时（秒） |

---

## 5. 静态分析 (`backend/analyzer/`)

### 职责描述

静态分析模块提供多语言代码解析能力，基于 tree-sitter（精确 AST）+ 语言适配器架构，支持 6 种语言。tree-sitter 不可用时自动降级为正则匹配。

### 文件清单

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `static_analyzer.py` | 102 | `analyze_file()`、`analyze_code()`、`_detect_smells()` | 统一入口 |
| `languages/base.py` | 193 | `LanguageAdapter`(ABC)、`ASTNode`、`FunctionInfo`、`ClassInfo`、`ImportInfo`、`CallEdge` | 适配器基类与数据结构 |
| `languages/python.py` | 84 | `PythonAdapter` | Python 适配器（tree-sitter + 内置 ast） |
| `languages/javascript.py` | 91 | `JavaScriptAdapter` | JavaScript 适配器 |
| `languages/typescript.py` | 65 | `TypeScriptAdapter` | TypeScript 适配器（继承 JS） |
| `languages/java.py` | 180 | `JavaAdapter` | Java 适配器 |
| `languages/go.py` | 151 | `GoAdapter` | Go 适配器 |
| `languages/cpp.py` | 175 | `CppAdapter` | C/C++ 适配器 |
| `languages/fallback.py` | 12 | `FallbackAdapter` | 正则降级适配器 |
| `languages/__init__.py` | 45 | `FunctionInfo`、`ImportInfo`、`CallEdge`、`ParsedFunction`、`get_adapter()`、`get_adapter_for_file()` | 适配器工厂 |

### AST 解析能力

每个适配器实现 `LanguageAdapter` 接口，提供：
- `parse(code)` → 解析为 `ASTNode` 树
- 函数/类/导入提取
- 调用边（CallEdge）构建
- 代码异味（smells）检测：长函数、复杂度、重复代码等

### 降级策略

```
tree-sitter 可用？ → 是：精确 AST 解析
                  → 否：该语言正则降级（FallbackAdapter）
Python 额外支持内置 ast 模块（零依赖）
```

### 数据流

```
源代码文件 → get_adapter_for_file() 按扩展名选择适配器
          → adapter.parse() 解析 AST → 提取函数/类/导入/调用
          → _detect_smells() 检测异味 → 返回结构化分析结果
```

### 依赖关系

- 依赖：tree-sitter（可选）、Python 内置 ast
- 被依赖：`backend.api.analysis`、`backend.core.tia_engine`、`backend.generator`

---

## 6. 安全 (`backend/safety/`)

### 职责描述

安全模块提供认证授权、限流、沙箱、容错、密钥检测、Prompt 注入防护等企业级安全能力，是 TestForge 生产可用的基础保障。

### 文件清单

| 文件 | 行数 | 核心类/函数 | 说明 |
|------|------|-------------|------|
| `auth.py` | 183 | `create_token()`、`create_refresh_token()`、`validate_token()`、`get_current_user()`、`require_permission()`、`require_role()`、`optional_user()` | JWT 认证 + RBAC 权限 |
| `auth_helpers.py` | 66 | - | 认证辅助函数 |
| `users.py` | 263 | `User`、`UserRole`、`LoginRateLimiter` | 用户管理 + 登录限流（5 次/分钟锁 IP 15 分钟） |
| `passwords.py` | 26 | - | PBKDF2 密码哈希 |
| `rate_limit.py` | 45 | `RateLimitMiddleware` | 滑动窗口限流中间件 |
| `sandbox.py` | 109 | - | Docker 沙箱（隔离执行） |
| `resilience.py` | 312 | `RetryConfig`、`CircuitBreaker`、`CircuitBreakerConfig`、`CircuitState`、`ThroughputMonitor`、`CircuitBreakerOpenError` | 熔断器 + 重试 + 吞吐量监控 |
| `secret_scan.py` | 55 | - | 密钥/凭证检测 |
| `prompt_guard.py` | 138 | `PromptGuard`、`GuardResult` | Prompt 注入防护 |
| `security_checks.py` | 113 | `validate_security_config()`、`get_admin_credentials()`、`check_debug_mode_warnings()`、`validate_cors_config()` | 安全配置校验 |
| `exception_handler.py` | 89 | `AppError`、`NotFoundError`、`ValidationError`、`RateLimitError`、`LLMUnavailableError` | 统一异常处理 |
| `logging_middleware.py` | 57 | `TraceIDMiddleware`、`setup_logging()` | 结构化日志 + trace_id |
| `notifier.py` | 125 | - | 告警通知 |
| `__init__.py` | 0 | - | 包初始化 |

### 核心机制

#### JWT 认证
- access_token：24 小时有效
- refresh_token：7 天有效
- RBAC 三角色：`admin`、`editor`、`viewer`

#### 登录限流
- `LoginRateLimiter`：5 次失败/分钟 → 锁定 IP 15 分钟

#### 熔断器（`CircuitBreaker`）
- 三态：CLOSED → OPEN → HALF_OPEN
- 配置：失败阈值、恢复超时、半开试探次数

### 数据流

```
请求 → RateLimitMiddleware（滑动窗口）→ TraceIDMiddleware（注入 trace_id）
     → auth 依赖（JWT 校验 + 角色检查）→ 业务处理
     → 异常 → exception_handler 统一响应
```

### 依赖关系

- 依赖：`backend.config`
- 被依赖：`backend.main`、`backend.api.*`、所有需要鉴权的端点

### 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_SECRET_KEY` | `change-me-in-production` | JWT 签名密钥（生产必改） |
| `TESTFORGE_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 | access_token 有效期 |
| `TESTFORGE_JWT_REFRESH_TOKEN_EXPIRE_DAYS` | 7 | refresh_token 有效期 |
| `TESTFORGE_ADMIN_USERNAME` | admin | 管理员用户名 |
| `TESTFORGE_ADMIN_PASSWORD_HASH` | （空，启动自动生成） | 管理员密码哈希 |
| `TESTFORGE_SANDBOX_ENABLED` | true | 沙箱开关 |

---

## 7. 质量 (`backend/quality/`)

### 职责描述

质量模块提供代码覆盖率、变异测试、质量门禁、安全质量扫描四大能力，是测试质量评估与门禁控制的核心。

### 文件清单

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `coverage.py` | 127 | - | 覆盖率收集与分析（集成 pytest-cov） |
| `mutation.py` | 339 | - | 变异测试（生成变异体并验证） |
| `gate.py` | 187 | `QualityGate`、`GateCheck`、`GateResult` | 质量门禁（多维度检查） |
| `security.py` | 138 | `SecurityScanner`、`SecurityFinding` | 安全质量扫描 |
| `__init__.py` | 0 | - | 包初始化 |

### 核心机制

#### `QualityGate`
- 多维度检查：覆盖率、变异分数、Flaky 率、通过率、安全发现
- 返回 `GateResult`（passed + 各项 checks）

### 数据流

```
执行结果 → coverage.py 计算覆盖率 → mutation.py 变异测试
         → security.py 安全扫描 → gate.py 综合判定 → GateResult
```

### 依赖关系

- 依赖：`backend.config`
- 被依赖：`backend.api.analysis`、`backend.core.pipeline`

### 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_COVERAGE_THRESHOLD` | 80.0 | 覆盖率门禁阈值（%） |
| `TESTFORGE_MUTATION_THRESHOLD` | 80.0 | 变异分数门禁阈值（%） |
| `TESTFORGE_FLAKY_RERUN_COUNT` | 5 | Flaky 重跑次数 |

---

## 8. 报告 (`backend/reporter/`)

### 职责描述

报告模块生成多格式测试报告，包括 HTML、PDF、Allure、JUnit、JSON，以及徽章（badge）用于 CI 展示。

### 文件清单

| 文件 | 行数 | 核心类/函数 | 说明 |
|------|------|-------------|------|
| `generator.py` | 114 | - | HTML 报告生成 |
| `allure_writer.py` | 114 | - | Allure 格式报告写入 |
| `pdf_generator.py` | 195 | - | PDF 报告生成 |
| `badge.py` | 82 | - | SVG 徽章生成（coverage/health/pass-rate） |
| `__init__.py` | 21 | - | 包初始化与导出 |

### 数据流

```
ExecutionResult 列表 → generator.py 生成 HTML
                     → pdf_generator.py 生成 PDF
                     → allure_writer.py 生成 Allure 结果
                     → badge.py 生成 SVG 徽章
```

### 依赖关系

- 依赖：`backend.models`
- 被依赖：`backend.api.reports`

---

## 9. 集成 (`backend/integrations/`)

### 职责描述

集成模块负责与外部系统集成，包括 GitHub Actions CI/CD、Keploy 流量录制、邮件通知。

### 文件清单

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `github_actions.py` | 131 | `GitHubActionsIntegration` | CI/CD 集成（生成 workflow YAML） |
| `keploy.py` | 99 | - | Keploy 流量录制集成 |
| `notifications.py` | 125 | `NotificationSender` | 邮件通知（SMTP） |
| `__init__.py` | 13 | - | 包初始化 |

### 数据流

```
测试完成 → notifications.py 发送邮件告警
         → github_actions.py 生成 CI 配置
         → keploy.py 录制流量回放
```

### 依赖关系

- 依赖：`backend.config`（SMTP 配置）
- 被依赖：`backend.api.analysis`、`backend.api.website`、`backend.core.scheduler`

### 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_SMTP_HOST` | （空） | SMTP 服务器 |
| `TESTFORGE_SMTP_PORT` | 465 | SMTP 端口 |
| `TESTFORGE_SMTP_USE_TLS` | true | 启用 TLS |
| `TESTFORGE_SMTP_USER` | （空） | SMTP 用户名 |
| `TESTFORGE_SMTP_PASSWORD` | （空） | SMTP 密码 |
| `TESTFORGE_SMTP_TIMEOUT` | 30 | SMTP 超时 |
| `TESTFORGE_SLACK_WEBHOOK_URL` | （空） | Slack Webhook |
| `TESTFORGE_DINGTALK_WEBHOOK_URL` | （空） | 钉钉 Webhook |

---

## 10. 数据层 (`backend/models/`)

### 职责描述

数据层提供持久化能力，支持 SQLite（本地/单用户）与 PostgreSQL（团队/生产）双后端，通过 `DATABASE_URL` 自动切换。提供异步 CRUD、upsert、全文搜索。

### 文件清单

| 文件 | 行数 | 核心类 | 说明 |
|------|------|--------|------|
| `store.py` | 333 | `DatabaseBackend`(ABC)、`SQLiteBackend`、`PostgresBackend`、`_PgRow` | 数据库后端 + CRUD |
| `__init__.py` | 88 | `TestCase`、`TestStep`、`Assertion`、`ExecutionResult`、`RunRequest` 及枚举 | Pydantic 数据模型 |

### 表结构

| 表名 | 主要字段 | 说明 |
|------|----------|------|
| `test_cases` | id(PK)、name、type、tags、status、flaky_score、health_score、created_by、data(JSON)、created_at | 测试用例 |
| `executions` | execution_id(PK)、test_id、status、duration_ms、error_message、logs、started_at、completed_at | 执行记录 |

> 索引：`idx_test_cases_status`、`idx_executions_test_id`、`idx_executions_started`
>
> 用户表（`users`）由 `backend.safety.users.init_users_table()` 创建。
>
> 进化数据、Token 用量、调度任务等由各自模块独立管理（SQLite 文件）。

### 核心数据模型

```python
class TestCase(BaseModel):
    id: str
    name: str
    type: TestType          # functional/boundary/api/e2e/unit/performance
    tags: list[str]
    status: TestStatus      # active/quarantine/deprecated
    flaky_score: float
    health_score: float
    created_by: str
    variables: dict[str, str]
    steps: list[TestStep]
    boundary_expansion: Optional[dict]
    impact_analysis: Optional[dict]

class ExecutionResult(BaseModel):
    execution_id: str
    test_id: str
    status: ExecutionStatus  # pending/running/passed/failed/skipped/error
    duration_ms: int
    error_message: Optional[str]
    logs: list[str]
    screenshots: list[str]
    started_at: datetime
    completed_at: Optional[datetime]
```

### 后端切换

```
DATABASE_URL=sqlite+aiosqlite:///testforge.db        → SQLiteBackend（WAL 模式）
DATABASE_URL=postgresql+asyncpg://user:pass@host/db  → PostgresBackend（连接池 min=5/max=20）
```

- SQLite：单连接 + WAL + asyncio.Lock
- PostgreSQL：asyncpg 连接池，自动占位符转换（`?` → `$N`）

### 数据流

```
业务层调用 → _get_backend() 单例获取 → execute/fetchall/fetchone
           → SQLite 或 PostgreSQL 执行 → 返回 Row → 转换为 Pydantic 模型
```

### 依赖关系

- 依赖：`backend.config`、`aiosqlite`（SQLite）、`asyncpg`（PostgreSQL，可选）
- 被依赖：`backend.api.*`、`backend.main`、`backend.core.rag`

### 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_DATABASE_URL` | `sqlite+aiosqlite:///testforge.db` | 数据库连接 |
| `TESTFORGE_DB_POOL_SIZE` | 5 | PG 连接池大小 |
| `TESTFORGE_DB_MAX_OVERFLOW` | 10 | PG 最大溢出连接 |

---

## 11. DSL (`backend/dsl/`)

### 职责描述

DSL 模块提供 YAML 格式的测试场景定义与解析能力，允许用户以声明式方式编写测试用例。

### 文件清单

| 文件 | 行数 | 核心函数 | 说明 |
|------|------|----------|------|
| `parser.py` | 126 | `parse_dsl()`、`_parse_step()` | DSL 解析器 |
| `examples/user_flow.yaml` | - | - | 示例：用户注册+登录流程 |
| `__init__.py` | 3 | - | 包初始化 |

### DSL 语法示例

```yaml
name: 用户注册流程
description: 完整注册+验证+登录
variables:
  base_url: http://localhost:9876
steps:
  - name: 注册
    request:
      method: POST
      url: /api/auth/register
      body: {username: testuser, password: Test1234}
    assert:
      - status: 201
      - jsonpath: $.user.id
        equals: not_null
  - name: 登录
    request:
      method: POST
      url: /api/auth/login
    extract:
      token: $.access_token
    assert:
      - status: 200
```

### 数据流

```
YAML 字符串 → yaml.safe_load → _parse_step() 逐步骤解析
            → 构建 TestCase + TestStep + Assertion → 返回 TestCase
```

### 依赖关系

- 依赖：`backend.models`、`pyyaml`
- 被依赖：`backend.api.analysis`（`/api/analysis/dsl/parse`、`/api/analysis/dsl/validate`）

---

## 12. 配置 (`backend/config.py`)

### 职责描述

配置模块集中管理所有环境变量，基于 `pydantic-settings`，统一前缀 `TESTFORGE_`，启动时自动校验关键安全配置。

### 文件信息

- 文件：`backend/config.py`（187 行）
- 核心类：`Settings(BaseSettings)`
- 全局实例：`settings = Settings()`

### 配置项分类

#### 应用配置

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_APP_NAME` | TestForge | 应用名 |
| `TESTFORGE_APP_VERSION` | 0.1.0 | 版本 |
| `TESTFORGE_DEBUG` | false | 调试模式 |
| `TESTFORGE_HOST` | 0.0.0.0 | 监听地址 |
| `TESTFORGE_PORT` | 9876 | 监听端口 |

#### LLM 配置

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_LLM_PROVIDER` | dashscope | LiteLLM provider |
| `TESTFORGE_LLM_MODEL` | qwen-plus | 模型名 |
| `TESTFORGE_LLM_API_KEY` | （空） | API Key |
| `TESTFORGE_LLM_API_BASE` | （空） | API Base URL |
| `TESTFORGE_LLM_FALLBACK_CHAIN` | `deepseek-chat,gpt-4o-mini` | 降级链 |
| `TESTFORGE_LLM_TEMPERATURE_CODE` | 0.1 | 代码生成温度 |
| `TESTFORGE_LLM_TEMPERATURE_DESIGN` | 0.3 | 设计温度 |
| `TESTFORGE_LLM_MAX_TOKENS_CODE` | 4096 | 代码生成 max tokens |
| `TESTFORGE_LLM_MAX_TOKENS_DESIGN` | 8192 | 设计 max tokens |

#### 本地 LLM（Ollama）

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_OLLAMA_ENABLED` | true | 启用 Ollama |
| `TESTFORGE_OLLAMA_HOST` | `http://localhost:11434` | Ollama 地址 |
| `TESTFORGE_OLLAMA_MODEL` | `qwen3-coder:7b` | 本地模型 |

#### 数据库配置

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_DATABASE_URL` | `sqlite+aiosqlite:///testforge.db` | 数据库 URL（切换 SQLite/PG） |

#### 安全配置

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_SECRET_KEY` | `change-me-in-production` | JWT 密钥（生产必改，否则启动退出） |
| `TESTFORGE_SANDBOX_ENABLED` | true | 沙箱开关 |
| `TESTFORGE_ADMIN_USERNAME` | admin | 管理员用户名 |
| `TESTFORGE_ADMIN_PASSWORD_HASH` | （空，自动生成） | 管理员密码哈希 |
| `TESTFORGE_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 | access token 有效期 |
| `TESTFORGE_JWT_REFRESH_TOKEN_EXPIRE_DAYS` | 7 | refresh token 有效期 |
| `TESTFORGE_RATE_LIMIT_MAX_REQUESTS` | 200 | 全局限流 |
| `TESTFORGE_RATE_LIMIT_WINDOW_SECONDS` | 60 | 限流窗口 |

#### CORS 配置

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_CORS_ORIGINS` | `http://localhost:3000,http://localhost:9876,http://127.0.0.1:3000` | 允许来源（逗号分隔） |

#### 执行配置

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_MAX_WORKERS` | 4 | 最大并发 |
| `TESTFORGE_TIMEOUT_PER_TEST` | 30 | 单测试超时 |
| `TESTFORGE_TIMEOUT_TOTAL` | 1800 | 总超时 |
| `TESTFORGE_HTTP_TEST_MAX_CONCURRENCY` | 10 | HTTP 并发 |
| `TESTFORGE_HTTP_TEST_MAX_TESTS` | 30 | HTTP 最大数 |
| `TESTFORGE_HTTP_TEST_TIMEOUT` | 8 | HTTP 超时 |

#### 质量门禁

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TESTFORGE_COVERAGE_THRESHOLD` | 80.0 | 覆盖率阈值 |
| `TESTFORGE_MUTATION_THRESHOLD` | 80.0 | 变异分数阈值 |
| `TESTFORGE_FLAKY_RERUN_COUNT` | 5 | Flaky 重跑次数 |

#### RAG / Agent / 性能 / 日志 / 通知 / 邮件

详见各模块章节。

### 启动校验

- `_validate_secret_key()`：生产环境使用默认密钥则 `sys.exit(1)`
- `_validate_cors_origins()`：校验 CORS 配置非空
- `_validate_database_url()`：校验数据库 URL

### 依赖关系

- 被依赖：几乎所有后端模块（`from backend.config import settings`）

---

# 前端模块

## 13. 页面 (`frontend/src/pages/`)

### 职责描述

前端页面模块包含 14 个 React 页面组件，覆盖测试设计、生成、执行、分析、Agent、报告、设置全流程。使用 React + TypeScript + Vite，内联样式（深色主题）。

### 文件清单

| 页面文件 | 行数 | 路由 | 功能说明 |
|----------|------|------|----------|
| `Login.tsx` | 151 | `/login` | 登录页，用户名密码登录 |
| `Dashboard.tsx` | 299 | `/` | 仪表盘，概览统计 + 健康度 + 趋势 |
| `CodeTester.tsx` | 366 | `/code` | 代码测试，输入代码生成+执行测试 |
| `ExecutionCenter.tsx` | 209 | `/execute` | 执行中心，触发执行 + 实时进度（WebSocket） |
| `AgentPlayground.tsx` | 608 | `/agent` | Agent Playground，单/多 Agent 交互 + 流式输出 |
| `WebsiteTester.tsx` | 1977 | `/website` | 网站测试（最大页面），OpenAPI 扫描/爬虫/自动化测试/Browser Agent |
| `EvolutionDashboard.tsx` | 436 | `/evolution` | 自进化报告，策略权重 + 知识库 + 事件历史 |
| `ImpactAnalysis.tsx` | 160 | `/impact` | 影响分析（TIA），变更文件→精准测试 |
| `ScheduleMonitor.tsx` | 110 | `/schedule` | 定时巡察监控，任务 CRUD + 告警 |
| `TestList.tsx` | 199 | `/tests` | 测试列表（测试管理），CRUD + 隔离 |
| `TestDesigner.tsx` | 200 | `/design` | 测试设计器，可视化设计测试用例 |
| `Reports.tsx` | 136 | `/reports` | 报告查看，HTML/PDF/Allure |
| `TokenUsage.tsx` | 338 | `/token` | Token 用量统计，按模型/场景/Provider + 预算 |
| `Settings.tsx` | 228 | `/settings` | 系统设置，LLM Provider + SMTP 邮件配置 |

### 核心组件特性

- **WebsiteTester.tsx**（1977 行）：最复杂页面，集成四大功能 Tab，含 Browser Agent 实时步骤展示
- **AgentPlayground.tsx**（608 行）：支持单 Agent / 多 Agent / LangGraph 切换，SSE 流式输出
- **EvolutionDashboard.tsx**（436 行）：策略权重雷达图 + 知识库检索 + 跨项目迁移
- **TokenUsage.tsx**（338 行）：用量趋势 + 预算告警 + 价格计算

### 数据流

```
页面组件 → api.ts (apiFetch/apiJson) → 后端 API → 返回数据 → setState 渲染
        → WebSocket (ws://host/ws/events) → 实时进度更新
```

### 依赖关系

- 依赖：`frontend/src/api.ts`、`frontend/src/auth.tsx`、React Router、react-router-dom

---

## 14. 认证 (`frontend/src/auth.tsx`)

### 职责描述

认证模块提供全局认证状态管理，基于 React Context，包含 `AuthProvider`、`useAuth` Hook，支持 `BYPASS_AUTH` 本地开发跳过登录。

### 文件信息

- 文件：`frontend/src/auth.tsx`（94 行）
- 核心导出：`AuthProvider`、`useAuth`

### 核心接口

```typescript
interface AuthContextValue {
  user: AuthUser | null;        // 当前用户
  loading: boolean;             // 加载状态
  isAuthenticated: boolean;     // 是否认证
  login: (username, password) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}
```

### BYPASS_AUTH 机制

```typescript
const BYPASS_AUTH = import.meta.env.VITE_BYPASS_AUTH === "true";
// 仅本地开发：.env 设置 VITE_BYPASS_AUTH=true
// 生产构建默认 false
const MOCK_USER = { username: "dev_user", role: "admin", email: "dev@testforge.local" };
```

- 启用 BYPASS_AUTH：直接使用 MOCK_USER，`isAuthenticated` 恒为 true
- 未启用：从 localStorage 读取 token，调用 `/api/auth/me` 获取用户

### 路由守卫

在 `App.tsx` 中实现：
```tsx
if (!isAuthenticated && location.pathname !== "/login") {
  return <Navigate to="/login" replace />;
}
```

### 数据流

```
AuthProvider 加载 → 检查 BYPASS_AUTH → 否：getToken() → fetchCurrentUser()
                 → 设置 user/loading → 通过 Context 暴露
```

### 依赖关系

- 依赖：`frontend/src/api.ts`（login/logout/fetchCurrentUser）
- 被依赖：`frontend/src/App.tsx` 及所有页面

---

## 15. API 客户端 (`frontend/src/api.ts`)

### 职责描述

API 客户端模块封装所有 HTTP 请求，提供 Token 管理、401 自动刷新、统一错误处理。

### 文件信息

- 文件：`frontend/src/api.ts`（140 行）
- 核心导出：`apiFetch`、`apiJson`、`login`、`logout`、`fetchCurrentUser`、Token 管理函数

### Token 管理

| 函数 | 说明 |
|------|------|
| `getToken()` / `getRefreshToken()` | 读取 localStorage |
| `setTokens(access, refresh)` | 写入 localStorage |
| `clearTokens()` | 清除 token + user |
| `setUser()` / `getUser()` | 用户信息存取 |

存储 Key：
- `testforge_access_token`
- `testforge_refresh_token`
- `testforge_user`

### 401 自动刷新机制

```typescript
async function apiFetch(url, options) {
  // 1. 携带 access_token 发请求
  let response = await fetch(url, { ...options, headers });
  // 2. 401 → 尝试刷新
  if (response.status === 401 && getToken()) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshToken();  // 避免并发刷新
    }
    const refreshed = await refreshPromise;
    isRefreshing = false;
    if (refreshed) {
      // 3. 重新发送原请求
      response = await fetch(url, { ...options, headers });
    } else {
      // 4. 刷新失败 → 清除 token，跳转 /login
      clearTokens();
      window.location.href = "/login";
    }
  }
  return response;
}
```

### WebSocket 辅助

通过原生 `WebSocket` 连接 `/ws/events`，接收 pipeline 实时事件。

### 数据流

```
页面调用 apiJson(url) → apiFetch 携带 token → fetch
                     → 401 → refreshToken → 重试 / 跳登录
                     → 200 → res.json() → 返回数据
```

### 依赖关系

- 被依赖：`frontend/src/auth.tsx`、所有页面组件

---

## 16. 路由布局 (`frontend/src/App.tsx`)

### 职责描述

路由布局模块定义前端路由表、侧边栏导航、`ProtectedLayout` 布局壳，是前端应用骨架。

### 文件信息

- 文件：`frontend/src/App.tsx`（260 行）
- 核心组件：`App`、`ProtectedLayout`

### 路由表

| 路径 | 组件 | 导航分组 |
|------|------|----------|
| `/login` | `Login` | - |
| `/` | `Dashboard` | 概览 |
| `/design` | `TestDesigner` | 测试 |
| `/tests` | `TestList` | 测试 |
| `/execute` | `ExecutionCenter` | 测试 |
| `/website` | `WebsiteTester` | 测试 |
| `/code` | `CodeTester` | 测试 |
| `/agent` | `AgentPlayground` | 智能 |
| `/schedule` | `ScheduleMonitor` | 智能 |
| `/evolution` | `EvolutionDashboard` | 智能 |
| `/impact` | `ImpactAnalysis` | 分析 |
| `/token` | `TokenUsage` | 分析 |
| `/reports` | `Reports` | 分析 |
| `/settings` | `Settings` | 系统 |

### 侧边栏导航分组

```
概览: Dashboard
测试: 测试设计器 / 测试列表 / 执行中心 / 网站测试 / 代码测试
智能: Agent Playground / 定时巡察 / 自进化
分析: 影响分析 / Token 用量 / 报告
系统: 设置
```

### ProtectedLayout

- 侧边栏：固定 220px 宽，深色主题（`#0f172a`），含 Logo + 导航分组 + 用户信息 + 登出
- 主内容区：`marginLeft: 220px`，最大宽度 1200px 居中
- 底部状态：Pipeline Ready 指示灯 + 版本号

### 路由守卫逻辑

```tsx
function App() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <加载中/>;
  if (!isAuthenticated && pathname !== "/login") return <Navigate to="/login"/>;
  if (isAuthenticated && pathname === "/login") return <Navigate to="/"/>;
  return <Routes> login + /* → ProtectedLayout </Routes>;
}
```

### 数据流

```
URL 变化 → useAuth 判断认证 → 未认证跳 /login
         → 已认证 → ProtectedLayout 渲染侧边栏 + 匹配路由页面
```

### 依赖关系

- 依赖：`frontend/src/auth.tsx`、`react-router-dom`、所有页面组件

---

# 基础设施

## 17. CLI (`cli/`)

### 职责描述

CLI 模块提供命令行工具，支持测试生成、执行、报告、自进化、录制等操作，通过 HTTP 调用后端 API。

### 文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `main.py` | 390 | CLI 主程序（argparse 子命令） |

### 命令清单

| 命令 | 说明 |
|------|------|
| `design` | 打开可视化设计器（Web UI） |
| `create` | 自然语言创建测试用例 |
| `record browser` | 浏览器录制（Playwright） |
| `record api` | API 流量录制（Keploy） |
| `run` | 触发测试执行（smart/smoke/full） |
| `analyze` | 智能分析（静态/覆盖率/变异） |
| `heal` | 自愈失败的测试 |
| `quarantine` | 隔离 Flaky 测试 |
| `review` | 交互式审查生成结果 |
| `evolution report` | 进化报告（策略权重、知识库统计） |
| `evolution knowledge` | 搜索进化知识库 |
| `evolution strategies` | 推荐策略排序（按进化权重） |
| `evolution events` | 进化事件历史 |
| `evolution stats` | 进化引擎统计概览 |
| `evolution cross-project` | 跨项目知识迁移 |
| `report` | 生成报告 |
| `dashboard` | 打开 Web Dashboard |
| `init` | 初始化项目配置 |

### 数据流

```
CLI 命令 → argparse 解析 → _handle(args) → HTTP 调用后端 API
        → 输出结果到终端 / 打开浏览器
```

### 依赖关系

- 依赖：后端 API（HTTP 调用）、`argparse`、`webbrowser`

---

## 18. Docker (`docker/`)

### 职责描述

Docker 模块提供容器化部署能力，包含 Dockerfile 与 docker-compose 编排。

### 文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `Dockerfile` | 17 | 后端镜像构建 |
| `docker-compose.yml` | 42 | 服务编排 |
| `.dockerignore` | - | 构建忽略 |

### 服务编排

```yaml
services:
  backend:
    build: { context: ., dockerfile: docker/Dockerfile }
    ports: ["9876:9876"]
    environment: TESTFORGE_* 环境变量
    volumes: testforge_data:/app/data
    restart: unless-stopped
    healthcheck: GET /api/health (30s/5s/3retries)
```

### 端口映射

| 端口 | 服务 | 说明 |
|------|------|------|
| 9876 | backend | FastAPI 后端 + 前端静态资源 |

### 环境变量传递

通过 `${VAR:-default}` 从宿主机环境注入：LLM Provider/Model/Key、Database URL、Secret Key、Debug、CORS 等。

### 安全说明

- 注释中明确提示：挂载 `docker.sock` 会赋予容器宿主机 Docker 控制权，已默认移除
- 沙箱如需 Docker，建议宿主机运行 Docker Agent 通过 TCP 连接

---

## 19. 测试 (`tests/`)

### 职责描述

测试模块包含 TestForge 自身的测试套件，覆盖核心、生成器、Agent、边界用例、E2E 集成等。

### 文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `conftest.py` | 48 | pytest 全局夹具 |
| `run_tests.py` | 171 | 测试运行脚本 |
| `add_test_marks.py` | 110 | 测试标记工具 |
| `test_core.py` | 126 | 核心功能测试 |
| `test_modules.py` | 133 | 模块单元测试 |
| `test_generator.py` | 48 | 生成器测试 |
| `test_agent_core.py` | 506 | Agent 核心测试 |
| `test_advanced.py` | 248 | 高级功能测试 |
| `test_boundary_cases.py` | 398 | 边界用例测试 |
| `test_advanced_boundary_cases.py` | 477 | 高级边界用例 |
| `test_all_scenarios_boundary.py` | 1950 | 全场景边界用例（最大测试文件） |
| `test_e2e_browser_agent.py` | 124 | E2E 浏览器 Agent 测试 |
| `test_e2e_integration.py` | 566 | E2E 集成测试 |

### 覆盖范围

- **核心引擎**：Agent、Pipeline、RAG、TIA、自愈、自进化
- **生成器**：五策略路由、模板/属性/AI/搜索/流量
- **执行器**：代码/HTTP/浏览器/DB/脚本
- **边界用例**：`test_all_scenarios_boundary.py`（1950 行）覆盖全场景边界
- **E2E**：浏览器 Agent + 端到端集成

### 运行方式

```bash
pytest tests/                          # 全量
pytest tests/test_agent_core.py        # Agent 测试
python tests/run_tests.py              # 脚本运行
```

---

# 附录

## 模块依赖关系图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        前端 (Frontend)                              │
│   App.tsx ──┬── auth.tsx ── api.ts                                  │
│             └── pages/* (14 页面)                                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     API 层 (backend/api/)                           │
│   auth_api / tests / executions / website / agent_api / ...         │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   安全层      │  │   核心引擎    │  │   生成器      │
│ safety/      │  │  core/       │  │ generator/   │
│ (auth/限流/  │  │ (Agent/自愈/ │  │ (五策略路由/  │
│  沙箱/熔断)  │  │  进化/RAG)   │  │  AI/模板/...) │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       │         ┌───────┴───────┐         │
       │         ▼               ▼         │
       │  ┌────────────┐  ┌──────────┐     │
       │  │  执行器     │  │ 静态分析  │     │
       │  │ executors/ │  │ analyzer/│     │
       │  └─────┬──────┘  └────┬─────┘     │
       │        │              │           │
       │        ▼              ▼           │
       │  ┌─────────────────────────┐      │
       │  │      质量 / 报告 / 集成   │      │
       │  │ quality/ reporter/       │      │
       │  │ integrations/            │      │
       │  └────────────┬─────────────┘      │
       │               │                    │
       ▼               ▼                    ▼
┌──────────────────────────────────────────────────┐
│            数据层 (models/store.py)              │
│      SQLite / PostgreSQL 双后端                  │
│      + DSL (dsl/parser.py) + 配置 (config.py)    │
└──────────────────────────────────────────────────┘
```

### 依赖关系要点

| 模块 | 直接依赖 |
|------|----------|
| API 层 | core、generator、executors、analyzer、safety、models、reporter、integrations、dsl |
| 核心引擎 | config、models、generator、executors、analyzer、safety |
| 生成器 | models、core.self_evolution、core.rag |
| 执行器 | config、models |
| 安全 | config |
| 数据层 | config |

---

## 数据流图

### 主流程：从用户输入到结果输出

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
│ 用户输入  │───▶│ 前端页面  │───▶│ API 客户端 │───▶│ API 层   │
│ (代码/URL)│    │ (React)  │    │ (api.ts)  │    │(FastAPI) │
└──────────┘    └──────────┘    └───────────┘    └────┬─────┘
                                                      │
                    ┌─────────────────────────────────┘
                    ▼
            ┌───────────────┐    ┌───────────────┐
            │  Pipeline 编排 │───▶│  静态分析      │
            │  (12 阶段)    │    │  (AST 解析)    │
            └───────┬───────┘    └───────┬───────┘
                    │                    │
                    ▼                    ▼
            ┌───────────────┐    ┌───────────────┐
            │  RAG 检索      │◀──│  测试生成      │
            │  (相似用例)    │──▶│  (五策略融合)  │
            └───────┬───────┘    └───────┬───────┘
                    │                    │
                    │                    ▼
                    │            ┌───────────────┐
                    │            │  测试执行      │
                    │            │  (5 类执行器)  │
                    │            └───────┬───────┘
                    │                    │
                    │                    ▼
                    │            ┌───────────────┐
                    │            │  质量评估      │
                    │            │  (覆盖/变异)   │
                    │            └───────┬───────┘
                    │                    │
                    ▼                    ▼
            ┌───────────────┐    ┌───────────────┐
            │  自愈系统      │◀──│  自进化闭环    │
            │  (AI 修复)    │    │  (Thompson)   │
            └───────┬───────┘    └───────┬───────┘
                    │                    │
                    ▼                    ▼
            ┌───────────────┐    ┌───────────────┐
            │  报告生成      │    │  RAG 写入      │
            │  (HTML/PDF)   │    │  (向量库)      │
            └───────┬───────┘    └───────────────┘
                    │
                    ▼
            ┌───────────────┐    ┌───────────────┐
            │  WebSocket     │───▶│  前端实时展示  │
            │  (进度推送)    │    │  (结果/趋势)   │
            └───────────────┘    └───────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  数据持久化    │
            │  (SQLite/PG)  │
            └───────────────┘
```

---

## 7 个闭环系统图

### 闭环 1：自进化闭环（Thompson 采样策略权重）

```
┌──────────────┐    策略调用    ┌──────────────┐
│ 生成器路由    │──────────────▶│ EvolutionLoop │
│ (五策略)     │               │ on_strategy_  │
└──────┬───────┘               │ called()      │
       │                       └──────┬────────┘
       │ 反馈权重                     │
       │ (推荐策略排序)               ▼
       │                 ┌──────────────┐
       │                 │ Thompson 采样 │
       │                 │ 更新 Beta 分布│
       │                 └──────┬────────┘
       │                        │
       │  执行结果反馈           ▼
       │                 ┌──────────────┐
       └─────────────────│on_execution_ │
                         │complete()    │
                         └──────────────┘
```
**数据流**：策略调用 → 记录成败 → Thompson 采样更新权重 → 下次生成时按权重排序策略

### 闭环 2：自愈闭环（AI 修复 + Playwright 验证）

```
┌──────────────┐  失败测试   ┌──────────────┐
│  执行器      │────────────▶│ SelfHealer   │
└──────────────┘             │ (三层)       │
                             └──────┬───────┘
                                    │
                     ┌──────────────┼──────────────┐
                     ▼              ▼              ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │UI 选择器  │  │API Schema│  │ 断言修复  │
              │修复      │  │修复      │  │          │
              └────┬─────┘  └──────────┘  └──────────┘
                   │ Playwright 验证
                   ▼
              ┌──────────┐  验证通过?  ┌──────────┐
              │ 重试执行  │────────────▶│ 更新用例  │
              └──────────┘              └──────────┘
```
**数据流**：失败测试 → 诊断失败层 → AI 生成候选修复 → Playwright 验证 → 通过则更新用例

### 闭环 3：RAG 检索闭环（向量检索 + 写入）

```
┌──────────────┐  检索相似    ┌──────────────┐
│ 生成器路由    │────────────▶│ UnifiedVector│
│              │             │ Store.search │
│              │◀────────────│ (BGE/Chroma/ │
│              │ 注入上下文   │  TF-IDF 降级)│
└──────┬───────┘             └──────────────┘
       │
       │ 生成新用例
       ▼
┌──────────────┐  写入向量    ┌──────────────┐
│ 新 TestCase  │────────────▶│ UnifiedVector│
│              │             │ Store.add    │
└──────────────┘             └──────────────┘
```
**数据流**：生成前检索相似用例 → 注入 prompt → 生成 → 新用例写回向量库 → 滚雪球增强

### 闭环 4：TIA 测试影响分析闭环（变更检测 + 精准测试）

```
┌──────────────┐  Git diff   ┌──────────────┐
│ 代码变更      │────────────▶│ TIAEngine    │
│ (changed     │             │ .get_diff()  │
│  files)      │             └──────┬───────┘
└──────────────┘                    │
                                    ▼
                            ┌──────────────┐
                            │ 构建调用图    │
                            │ _reverse_    │
                            │ call_chain() │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ 精准选择测试  │
                            │ _prioritize()│
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ 仅执行受影响  │
                            │ 测试（加速）  │
                            └──────────────┘
```
**数据流**：Git diff 变更文件 → 反向调用链分析 → 定位受影响测试 → 仅执行子集（计算加速比）

### 闭环 5：Flaky 检测闭环（多次重跑 + 健康度评分）

```
┌──────────────┐  执行结果   ┌──────────────┐
│  执行器      │────────────▶│ FlakyDetector│
│              │             │ (多次重跑)   │
└──────────────┘             └──────┬───────┘
                                    │ flaky_score
                                    ▼
                            ┌──────────────┐
                            │ HealthScorer │
                            │ (健康度 0-100)│
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ 高 Flaky →   │
                            │ 自动隔离     │
                            │ (quarantine) │
                            └──────────────┘
```
**数据流**：多次重跑测试 → 计算通过率波动 → Flaky 分数 → 更新健康度 → 超阈值自动隔离

### 闭环 6：调度巡检闭环（CRON 定时扫描 + 告警）

```
┌──────────────┐  定时触发   ┌──────────────┐
│ ScanScheduler│────────────▶│ 网站综合测试  │
│ (CRON)       │             │ (auto-test)  │
└──────┬───────┘             └──────┬───────┘
       │                            │
       │ 上次结果                    ▼
       │                   ┌──────────────┐
       │                   │ 对比上次通过率│
       │                   │ (变更检测)    │
       │                   └──────┬───────┘
       │                          │ 通过率下降
       │                          ▼
       │                   ┌──────────────┐
       │                   │ 发送告警邮件  │
       └───────────────────│ (SMTP)       │
                           └──────────────┘
```
**数据流**：CRON 定时触发 → 执行网站测试 → 对比历史通过率 → 下降则邮件告警

### 闭环 7：知识库构建闭环（执行模式 → 知识提取 → 跨项目迁移）

```
┌──────────────┐  执行事件   ┌──────────────┐
│ 执行结果      │────────────▶│KnowledgeBuilder│
│ (策略/耗时/  │             │ (模式提取)    │
│  成败)       │             └──────┬───────┘
└──────────────┘                    │
                                    ▼
                            ┌──────────────┐
                            │ KnowledgeEntry│
                            │ (写入知识库)  │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ProjectTransfer│
                            │ (跨项目迁移)  │
                            │ 策略指纹匹配  │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ 新项目复用    │
                            │ 推荐策略      │
                            └──────────────┘
```
**数据流**：执行事件 → 提取成功模式 → 写入知识库 → 项目指纹哈希匹配 → 跨项目策略迁移

---

## 技术栈一览表

### 后端

| 类别 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI | 异步 API 框架 |
| ASGI 服务器 | Uvicorn | 开发/生产服务器 |
| 数据校验 | Pydantic + pydantic-settings | 数据模型 + 配置管理 |
| 数据库 | SQLite (aiosqlite) / PostgreSQL (asyncpg) | 双后端切换 |
| LLM 调用 | LiteLLM | 多 Provider 统一接口 |
| 本地 LLM | Ollama | qwen3-coder:7b |
| 向量数据库 | ChromaDB | RAG 检索 |
| Embedding | BAAI/bge-small-zh-v1.5 | 中文 embedding |
| AST 解析 | tree-sitter | 60+ 语言支持 |
| 浏览器自动化 | Playwright | E2E 测试 |
| HTTP 客户端 | aiohttp | 异步 HTTP |
| Agent 编排 | LangGraph | StateGraph 图式 Agent |
| 视觉定位 | VLM | 截图→元素坐标 |
| JWT | python-jose | 认证 |
| 密码哈希 | PBKDF2 | 安全存储 |
| 进程管理 | psutil | 资源监控 |

### 前端

| 类别 | 技术 | 说明 |
|------|------|------|
| 框架 | React 18 | UI 库 |
| 语言 | TypeScript | 类型安全 |
| 构建工具 | Vite | 快速构建 |
| 路由 | React Router v6 | SPA 路由 |
| 状态管理 | React Context | 全局认证状态 |
| 通信 | Fetch API + WebSocket | HTTP + 实时推送 |
| 样式 | 内联 CSS | 深色主题 |

### 基础设施

| 类别 | 技术 | 说明 |
|------|------|------|
| 容器化 | Docker + docker-compose | 部署 |
| CI/CD | GitHub Actions | 持续集成 |
| 流量录制 | Keploy | API 流量录制 |
| 测试框架 | pytest | 单元/集成/E2E |
| 覆盖率 | pytest-cov | 覆盖率收集 |
| 报告 | Allure | 测试报告 |
| 包管理 | pip + requirements.txt | Python 依赖 |
| Lint | ESLint + Prettier | 前端代码规范 |

### 端点统计

| 模块 | 端点数 |
|------|--------|
| auth_api | 10 |
| tests | 6 |
| executions | 11 |
| reports | 10 |
| settings_api | 5 |
| analysis | 7 |
| website | 17 |
| agent_api | 21 |
| import_export | 2 |
| recording | 7 |
| token_usage | 8 |
| code_test | 4 |
| evolution | 11 |
| websocket | 1 |
| 全局（health/metrics） | 3 |
| **合计** | **~123** |

---

> 文档生成时间：2026-07-03
> 文档版本：v1.0
> 适用项目：TestForge
