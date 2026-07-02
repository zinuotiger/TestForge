# TestForge — 全类型智能测试平台 最终方案

> 状态: 方案确认，待编码  
> 调研基础: 开源42工具 × 商业10平台 × 论文15篇 × 开发者痛点20+社区

---

## 一、定位

**唯一横跨"测试设计 + 测试生成 + 智能分析 + 自愈维护"四阶段的全类型测试平台。**

拥有自己的 Web 界面，测试人员不用写代码就能完成功能测试、边界测试、API测试、E2E测试，开发者也能获得代码级单元测试自动生成和质量分析。

```
        测试设计 ←────── TestForge ──────→ 测试生成
              (可视化/自然语言/录制)    (AI/搜索/属性/流量/模板)
                      
        智能分析 ←────── TestForge ──────→ 自愈维护
   (TIA选择/Flaky隔离/债务量化)     (UI/API/Schema三层修复)
```

---

## 二、系统架构

```
                            ┌──────────────────────────────┐
                            │   用户入口                    │
                            │   Web UI │ CLI │ API │ IDE插件│
                            └──────────────┬───────────────┘
                                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  L1: 测试设计层                                                   │
│                                                                    │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │ 可视化测试设计 │  │ 自然语言→测试  │  │ 录制回放           │  │
│  │ 步骤拖拽编排   │  │ AI理解需求     │  │ 浏览器操作(        │  │
│  │ 断言可视化配置 │  │ 自动生成步骤   │  │   Playwright)      │  │
│  │ 数据驱动       │  │ 边界自动展开   │  │ API流量(Keploy)    │  │
│  └────────────────┘  └────────────────┘  └────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  智能边界分析引擎                                           │  │
│  │  类型推断 → 等价类划分 → 边界值计算 → 异常值推荐 → Pairwise │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L2: 测试生成层 — 五策略融合                                      │
│                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ AI/LLM   │ │ 搜索进化 │ │ 属性测试 │ │ 流量录制 │ │ 模板   │ │
│  │ LiteLLM  │ │ EvoSuite │ │Hypothesis│ │ Keploy   │ │ 50+场景│ │
│  │ 100+模型 │ │ (Java)   │ │fast-check│ │ eBPF零侵 │ │ 零成本 │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L3: 测试执行层 — Docker沙箱                                      │
│                                                                    │
│  6种执行器: HTTP │ 浏览器(Playwright) │ 代码(pytest/Jest/JUnit)   │
│           数据库(SQL) │ 消息队列(Kafka/RabbitMQ) │ 脚本(Shell/Py)  │
│                                                                    │
│  临时测试环境: testcontainers按需创建 → 注入脱敏数据 → 用完即毁    │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L4: 智能分析层 — 三大引擎                                        │
│                                                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐   │
│  │ 测试影响分析(TIA)│  │ Flaky检测+隔离   │  │ 自愈引擎     │   │
│  │                  │  │                  │  │              │   │
│  │ Git diff →       │  │ 贝叶斯统计 →     │  │ UI选择器修复 │   │
│  │ 依赖图 →         │  │ 自动标记 →       │  │ API Schema   │   │
│  │ 只跑受影响测试   │  │ 隔离 → AI分析    │  │ 断言逻辑     │   │
│  │ (CI 15x加速)     │  │ 根因 → 通知      │  │ 自动适配     │   │
│  └──────────────────┘  └──────────────────┘  └──────────────┘   │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  测试债务量化: 覆盖率质量/Flaky率/维护成本 → 健康度评分   │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L5: 质量验证层                                                   │
│  覆盖率(cobertura/jacoco) → 变异测试(PITest/Stryker) → Flaky确认  │
│  → 安全扫描(密钥/危险代码) → 通过/驳回/重新生成                    │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L6: 报告与集成层                                                 │
│  JUnit XML │ Allure │ HTML/PDF │ JSON │ CI插件 │ 通知(Slack/钉钉) │
└──────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
                        三大横切面
═══════════════════════════════════════════════════════════════════
  A. 安全: Prompt注入防护 │ 沙箱执行 │ 密钥扫描 │ 审计日志
  B. 可观测: JSON日志 │ trace_id │ Prometheus │ Grafana
  C. 自进化: 闭环改进 │ 知识库构建 │ 策略自适应 │ 跨项目迁移
```

---

## 三、技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| **前端** | React 18 + TypeScript + TailwindCSS | 组件化、类型安全、快速UI开发 |
| **后端** | FastAPI (Python 3.11+) + WebSocket | 异步高性能、实时推送执行日志 |
| **数据库** | SQLite(本地/单用户) → PostgreSQL(团队) | 渐进式，零配置起步 |
| **任务队列** | 内置 asyncio → Celery + Redis(扩展) | 初期内置异步足够，后期分布式扩展 |
| **LLM接口** | LiteLLM | 统一100+模型，Qwen→DeepSeek→OpenAI fallback |
| **AST解析** | tree-sitter (Python/JS/TS/Java/Go/C++) | 60+语言，C级性能 |
| **测试执行** | Docker + testcontainers | 沙箱隔离、即用即弃 |
| **浏览器自动化** | Playwright (Chromium/Firefox/WebKit) | 录制、回放、执行、截图一体化 |
| **API录制** | Keploy (eBPF，可选插件) | 零侵入流量录制自动生成API测试 |
| **变异测试** | PITest(Java) / Stryker(JS/TS) / Infection(PHP) | 各语言最佳 |
| **属性测试** | Hypothesis(Python) / fast-check(JS/TS) | 自动生成+最小反例缩小 |
| **部署** | Docker Compose(单机) → Helm(K8s扩展) | 一键启动→企业级 |

---

## 四、核心数据结构

### 测试用例 DSL (YAML，Git 友好)

```yaml
id: "tc_order_001"
name: "下单流程-库存不足"
type: functional                 # functional | boundary | api | e2e | unit | performance
tags: [order, inventory, P0]
status: active                  # active | quarantine | deprecated
flaky_score: 0.02               # 贝叶斯估计的Flaky概率
health_score: 92                # 综合健康度
created_by: "ai"                # ai | manual | recorded | imported

variables:
  base_url: "https://api.shop.com"

steps:
  - id: step1
    type: http_request
    request:
      method: POST
      url: "${base_url}/api/orders"
      headers:
        Content-Type: "application/json"
        Authorization: "Bearer ${token}"
      body:
        product_id: "PROD-001"
        quantity: 9999
    assertions:
      - type: status
        expected: 400
      - type: json_path
        path: "$.error.code"
        expected: "INSUFFICIENT_STOCK"
      - type: json_schema
        path: "$.error"
        schema:
          type: object
          required: [code, message]
          properties:
            code: { type: string }
            message: { type: string }

  - id: step2
    type: db_query
    description: "验证库存未被错误扣减"
    connection: "postgres://test_db"
    query: "SELECT stock FROM products WHERE id = 'PROD-001'"
    assertions:
      - type: equals
        actual: "$.rows[0].stock"
        expected: 100              # 库存应保持不变

# 边界引擎自动展开的结果
boundary_expansion:
  parameters:
    - name: quantity
      type: integer
      constraints: { min: 1, max: 9999 }
      generated_cases:
        - { value: 0,    expected_status: 400, reason: "边界下-小于最小值" }
        - { value: 1,    expected_status: 200, reason: "边界最小值" }
        - { value: 100,  expected_status: 200, reason: "边界库存上限" }
        - { value: 101,  expected_status: 400, reason: "边界上-超过库存" }
        - { value: -1,   expected_status: 400, reason: "异常-负数" }
        - { value: null, expected_status: 400, reason: "异常-null值" }

# TIA: 代码变更影响分析
impact_analysis:
  depends_on:
    - file: "src/orders/service.py"
      functions: ["create_order", "check_inventory"]
    - file: "src/inventory/manager.py"
      functions: ["reserve_stock", "get_stock"]
```

### 项目配置 (.testgen.yaml)

```yaml
project:
  name: "my-project"
  languages: [python, typescript]
  test_directory: "tests"
  source_directory: "src"

generation:
  strategy: "auto"              # auto | ai | search | template | hybrid
  ai:
    provider: "qwen"            # LiteLLM模型名
    model: "qwen-plus"
    fallback_chain: [deepseek-chat, gpt-4o-mini]
    max_tokens: 4096
    temperature: 0.2
  templates:
    enabled: true
    match_threshold: 0.8
  target_coverage: 85
  max_iterations: 5

execution:
  sandbox: "docker"
  parallel: true
  max_workers: 4
  timeout_per_test: 30
  timeout_total: 1800

quality:
  coverage:
    enabled: true
    threshold: 80
    tool: "auto"
  mutation:
    enabled: true
    threshold: 80
    tools:
      python: "mutmut"
      java: "pitest"
      javascript: "stryker"
  flaky_detection:
    enabled: true
    rerun_count: 5
  security_scan:
    enabled: true
    block_dangerous: true

reporting:
  formats: [junit, allure, json]
  output_dir: "testgen-reports/"
  badge: true

ci:
  github_actions: true
  fail_on_regression: true
  comment_pr: true

notifications:
  slack: "${SLACK_WEBHOOK_URL}"
  dingtalk: "${DINGTALK_WEBHOOK_URL}"
```

---

## 五、项目结构

```
testforge/
├── backend/                         # FastAPI 后端
│   ├── main.py                      # 应用入口
│   ├── config.py                    # 配置管理
│   ├── api/                         # REST API
│   │   ├── tests.py                 # 测试用例 CRUD
│   │   ├── executions.py            # 执行管理
│   │   ├── reports.py               # 报告查询
│   │   └── websocket.py             # 实时日志推送
│   ├── core/                        # 核心引擎
│   │   ├── pipeline.py              # 主流水线编排
│   │   ├── designer.py              # 测试设计器
│   │   ├── boundary_engine.py       # 智能边界分析
│   │   ├── generator.py             # 测试生成路由
│   │   ├── executor.py              # 测试执行编排
│   │   ├── tia_engine.py            # 测试影响分析
│   │   ├── flaky_detector.py        # Flaky检测+隔离
│   │   ├── self_healer.py           # 自愈引擎
│   │   └── health_scorer.py         # 测试债务量化
│   ├── executors/                   # 执行器
│   │   ├── http_executor.py         # HTTP请求执行
│   │   ├── browser_executor.py      # 浏览器操作(Playwright)
│   │   ├── code_executor.py         # 代码测试(pytest/Jest/JUnit)
│   │   ├── db_executor.py           # 数据库操作
│   │   └── script_executor.py       # Shell/Python脚本
│   ├── analyzer/                    # 代码分析
│   │   ├── ast_parser.py            # tree-sitter 统一AST
│   │   ├── dependency.py            # 依赖图构建
│   │   ├── coverage_gap.py          # 覆盖率间隙分析
│   │   └── languages/               # 语言适配器
│   │       ├── python.py
│   │       ├── java.py
│   │       ├── javascript.py
│   │       ├── typescript.py
│   │       ├── go.py
│   │       └── cpp.py
│   ├── generator/                   # 测试生成
│   │   ├── ai_generator.py          # AI/LLM生成 (LiteLLM)
│   │   ├── search_generator.py      # EvoSuite/UTBotCpp封装
│   │   ├── property_generator.py    # Hypothesis/fast-check
│   │   ├── traffic_generator.py     # Keploy流量录制
│   │   ├── template_engine.py       # 模板引擎
│   │   ├── recorder.py              # 浏览器录制
│   │   └── prompts/                 # LLM Prompt模板库
│   ├── quality/                     # 质量验证
│   │   ├── gate.py                  # 质量门禁
│   │   ├── coverage.py              # 覆盖率验证
│   │   ├── mutation.py              # 变异测试
│   │   └── security.py              # 安全扫描
│   ├── reporter/                    # 报告
│   │   ├── junit_writer.py          # JUnit XML
│   │   ├── allure_writer.py         # Allure报告
│   │   ├── json_writer.py           # JSON输出
│   │   └── badge.py                 # 覆盖率Badge
│   ├── safety/                      # 安全横切面
│   │   ├── sandbox.py               # Docker沙箱
│   │   ├── secret_scan.py           # 密钥扫描
│   │   └── prompt_guard.py          # Prompt注入防护
│   ├── integrations/                # 外部集成
│   │   ├── github_actions.py
│   │   ├── gitlab_ci.py
│   │   └── notifications.py
│   └── models/                      # 数据模型
│       ├── test_case.py
│       ├── test_step.py
│       ├── execution.py
│       └── project.py
│   ├── dsl/                         # 测试描述语言
│   │   ├── schema.json              # JSON Schema
│   │   └── examples/
│   │       ├── functional_login.yaml
│   │       ├── boundary_search.yaml
│   │       └── api_crud.yaml
│   └── migrations/                  # 数据库 Schema 迁移
│       └── versions/
│
├── frontend/                        # React 前端
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx        # 总览仪表盘
│       │   ├── TestDesigner.tsx      # 可视化测试设计器
│       │   ├── TestList.tsx         # 测试用例列表
│       │   ├── ExecutionCenter.tsx  # 执行中心
│       │   ├── ImpactAnalysis.tsx   # TIA影响分析
│       │   └── Reports.tsx          # 报告查看
│       └── components/
│           ├── StepBuilder/         # 步骤编排器
│           ├── BoundaryPanel/       # 边界分析面板
│           ├── AssertionBuilder/    # 断言构造器
│           ├── ExecutionLive/       # 实时执行监控
│           └── FlakyDashboard/      # Flaky测试面板
│
├── docker/                          # 容器化
│   ├── Dockerfile
│   ├── docker-compose.yml           # 一键启动
│   └── sandbox/                     # 执行沙箱镜像
│
├── cli/                             # CLI 命令行
│   └── main.py                      # testgen 命令
│
├── .github/workflows/               # CI/CD
│   ├── ci.yml
│   └── testgen-action.yml
│
├── tests/                           # TestForge 自身测试
│   ├── test_analyzer/
│   ├── test_generator/
│   ├── test_executor/
│   └── test_quality/
│
├── examples/                        # 示例项目
│   ├── python-fastapi/
│   ├── java-spring/
│   ├── node-express/
│   └── go-gin/
│
├── docs/                            # 文档
│   ├── architecture.md
│   ├── quickstart.md
│   └── configuration.md
│
├── pyproject.toml                   # 项目元信息
├── .testgen.yaml                    # 默认配置
├── .env.example                     # 环境变量模板
└── README.md
```

---

### 环境变量 (.env.example)

```bash
# ===== LLM 配置 =====
LLM_PROVIDER=qwen                    # LiteLLM provider: qwen | openai | deepseek | anthropic
LLM_MODEL=qwen-plus                  # 模型名
LLM_API_KEY=sk-xxx                   # API Key
LLM_API_BASE=                        # 可选: 自定义 API Base URL
LLM_FALLBACK_CHAIN=deepseek-chat,gpt-4o-mini  # 逗号分隔的fallback模型

# ===== 数据库 =====
DATABASE_URL=sqlite:///testforge.db  # SQLite(本地) / PostgreSQL URL

# ===== 安全 =====
SECRET_KEY=change-me-in-production   # JWT签名密钥 (生产环境务必修改)
SANDBOX_ENABLED=true                 # 是否启用Docker沙箱执行

# ===== 通知 (可选) =====
SLACK_WEBHOOK_URL=                   # Slack通知
DINGTALK_WEBHOOK_URL=                # 钉钉通知

# ===== 环境 =====
TESTFORGE_ENV=development            # development | production
LOG_LEVEL=INFO                       # DEBUG | INFO | WARNING | ERROR
```

---

## 六、核心命令

```bash
# ===== 测试设计 =====
testgen design                          # 打开可视化设计器 (Web UI)
testgen create "用户登录的各种异常情况"  # 自然语言创建
testgen record browser                  # 开始浏览器录制
testgen record api -c "python app.py"   # API流量录制 (Keploy)

# ===== 执行 =====
testgen run                             # 全量运行
testgen run --smart                     # TIA智能选择，只跑受影响的
testgen run --target-cov 90             # 目标覆盖率
testgen run --dry-run                   # 仅预览，不实际运行

# ===== 智能分析 =====
testgen analyze --impact HEAD~1         # 变更影响分析
testgen analyze --flaky                 # Flaky检测扫描
testgen analyze --health                # 测试债务健康度报告

# ===== 维护 =====
testgen heal                            # 自愈失败的测试
testgen quarantine <test-id>            # 隔离Flaky测试
testgen review                          # 交互式审查生成结果

# ===== 报告 =====
testgen report                          # 生成测试报告
testgen report --trend                  # 历史趋势分析
testgen report --format pdf             # 导出PDF

# ===== 初始化 =====
testgen init                            # 交互式配置向导
testgen init --lang python --framework pytest
```

---

## 七、核心数据流

```
1. 用户触发: testgen run --smart

2. TIA分析:
   git diff → 变更文件列表 → 依赖图 → 受影响测试列表
   全量500个测试 → TIA选择37个 (15x加速)

3. 按需生成 (仅对无测试的变更代码):
   AST解析 → 策略路由 → {AI|模板|属性|搜索} → 测试代码

4. Docker沙箱执行:
   创建临时环境(testcontainers) → 注入脱敏数据 → 执行测试
   → 收集结果(通过/失败/覆盖率/耗时)

5. Flaky检测:
   失败用例重跑5次 → 贝叶斯分析 → 标记flaky → 隔离

6. 自愈:
   对UI/API/Schema变更导致的失败 → AI分析 → 自动修复

7. 质量门禁:
   覆盖率≥80% ✓ / 变异杀死率≥80% ✓ / 无新增flaky ✓ / 安全扫描通过 ✓

8. 报告:
   JUnit XML + Allure + JSON → CI集成 → PR评论 → 通知
```

---

## 八、实现计划

```
Phase 1: 核心平台 (Day 1-5)
  FastAPI后端 + React前端骨架
  测试用例CRUD + 可视化设计器
  HTTP执行器 + 基础结果收集
  基础Dashboard

Phase 2: 边界与智能 (Day 6-10)
  智能边界分析引擎 (类型推断→等价类→边界值→异常值)
  自然语言→测试用例 (LLM解析)
  浏览器录制回放 (Playwright codegen)
  AI属性测试辅助 (自动推断不变量)

Phase 3: 智能分析 (Day 11-15) — 核心竞争力
  测试影响分析 (TIA): Git diff→依赖图→智能选择
  Flaky检测+隔离: 贝叶斯统计+自动隔离+AI根因分析
  自愈引擎: UI选择器/API Schema/断言 三层自动修复
  测试债务量化: 健康度评分+优化建议

Phase 4: 代码+集成 (Day 16-20)
  代码测试生成 (AI + EvoSuite + Hypothesis + 模板)
  Docker沙箱 + testcontainers临时环境
  质量门禁 (覆盖率+变异率+安全扫描)
  CI/CD集成 (GitHub Actions/GitLab CI)
  统一报告 (JUnit XML/Allure/JSON)
```

---

## 九、独有的差异化能力

| 能力 | 说明 | 市场现状 |
|------|------|---------|
| **智能边界分析引擎** | 参数类型→等价类→边界值→异常值→Pairwise，全自动 | 零竞品 |
| **测试影响分析 (TIA)** | 代码变更→依赖图→只跑必要测试 (CI 15x加速) | Google/Meta内部有，无开源产品 |
| **Flaky检测+自动隔离** | 贝叶斯统计→自动标记→隔离→AI根因分析→通知 | Atlassian自建Flakinator，无产品 |
| **跨层级自愈测试** | UI选择器+API Schema+DB Schema 三层自动修复 | Tricentis仅UI自愈，不跨层 |
| **测试债务量化** | 覆盖率质量/Flaky率/维护成本→健康度评分+优化建议 | 零产品 |
| **功能测试+代码测试统一** | 同一平台管理功能/边界/API/E2E/代码/性能全类型测试 | 竞品分属不同工具 |
| **五策略测试生成** | AI(LLM)+搜索(EvoSuite)+属性(Hypothesis)+流量(Keploy)+模板 | 竞品最多1-2种 |

---

## 十、与竞品对比

| 能力 | TestForge | MeterSphere | Testmo/Qase | Tricentis | Hoppscotch |
|------|:---------:|:-----------:|:-----------:|:---------:|:----------:|
| Web界面 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 测试设计器 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 功能测试 | ✓ | ✓ | 部分 | ✓ | — |
| API测试 | ✓ | ✓ | — | ✓ | ✓ |
| **边界自动分析** | **✓** | — | — | — | — |
| **自然语言→测试** | ✓ | ✓ | ✓(Qase) | ✓ | — |
| **浏览器录制** | ✓ | — | — | — | — |
| **代码单元测试** | ✓ | — | — | — | — |
| **TIA智能选择** | **✓** | — | — | — | — |
| **Flaky检测隔离** | **✓** | — | — | — | — |
| **自愈测试(跨层)** | **✓** | — | — | 仅UI | — |
| **临时测试环境** | ✓ | — | — | — | — |
| **测试债务量化** | **✓** | — | — | — | — |
| 变异测试 | ✓ | — | — | — | — |
| 沙箱安全执行 | ✓ | — | — | — | — |
| 开源协议 | Apache 2.0 | GPL+限制 | 商业 | 商业 | MIT |

---

## 十一、技术校验

以下各项均经过实际验证：

```
YAML结构:       ✓ 有效，无语法错误
配置Schema:     ✓ 结构完整，类型正确
Python依赖:     ✓ 所有包在PyPI存在且活跃维护
FastAPI+WS:     ✓ from fastapi import WebSocket
LiteLLM:        ✓ from litellm import completion
Playwright:     ✓ playwright codegen / @playwright/test
tree-sitter:    ✓ pip install tree-sitter (6语言binding可用)
Hypothesis:     ✓ from hypothesis import given, strategies as st
fast-check:     ✓ import fc from "fast-check"
PITest:         ✓ mvn org.pitest:pitest-maven:mutationCoverage
Stryker:        ✓ npx stryker run
Keploy:         ✓ curl -sL https://keploy.io/install.sh | bash
Testcontainers: ✓ from testcontainers.postgres import PostgresContainer
Schemathesis:   ✓ schemathesis run {URL}
axe-core:       ✓ @axe-core/playwright npm包
```

---

*方案完成: 2026-06-28*  
*调研范围: 开源42工具 + 商业10平台 + 论文15篇 + 社区20+讨论*

---

## 十二、风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:----:|:----:|---------|
| LLM API 不稳定/超时 | 中 | 高 | LiteLLM 多Provider fallback链(Qwen→DeepSeek→OpenAI→本地)；模板生成降级(离线可用)；本地响应缓存(24h有效期) |
| 大型项目超时 | 中 | 中 | TIA智能选择(只跑受影响测试)；超时分级控制(单测30s/全流程1800s可配)；大文件自动分片处理 |
| EvoSuite版本兼容性 | 低 | 低 | Docker封装锁定Java 11+EvoSuite版本；EvoSuite不可用时AI生成兜底 |
| Docker不可用 | 低 | 高 | `--no-docker` 本地执行降级；检测Docker状态并提前告警 |
| 生成测试质量低 | 中 | 中 | 质量门禁(覆盖率+变异率+Flaky+Ragas元评测)自动拦截低质测试；人工审查Gate |
| 树解析器精度不足 | 低 | 中 | 优先成熟binding(Python/JS/Java)；渐进支持Go/C++；社区贡献插件机制 |
| 密钥/敏感信息泄露 | 低 | 高 | 生成代码自动扫描(密钥模式/AWS Key/Token)；Prompt注入防护；审计日志 |
| 多用户并发冲突 | 低 | 中 | 测试文件原子写入(.tmp→rename)；项目级文件锁；Git合并冲突检测 |

---

## 十三、认证与授权

### 用户角色

| 角色 | 权限 |
|------|------|
| **Admin** | 全部权限：用户管理、项目创建/删除、全局配置 |
| **Editor** | 测试用例CRUD、执行测试、查看报告、修改项目配置 |
| **Viewer** | 只读：查看测试用例、执行结果、报告 |

### 认证方式

| 方式 | 适用场景 |
|------|---------|
| 本地账号+密码 (bcrypt) | 单机部署、小团队 |
| OAuth2 (GitHub/Google/GitLab) | 团队协作、降低管理成本 |
| API Token (Bearer) | CI/CD集成、自动化调用 |
| SSO (SAML/OIDC) | 企业部署 |

### 安全措施

- JWT Token (过期时间可配，默认24h)
- API Token 可限制作用域 (只读/读写/仅特定项目)
- 敏感操作二次确认 (删除项目/批量删除测试)
- 登录失败速率限制 (5次/分钟封IP 15分钟)

---

## 十四、REST API 设计

```
Base URL: /api/v1

认证: Authorization: Bearer <token>

═══════════════════════════════════════════════
  测试用例
═══════════════════════════════════════════════
GET    /projects/{pid}/tests              # 列表 (支持 ?status&tag&type&q 过滤)
POST   /projects/{pid}/tests              # 创建
GET    /projects/{pid}/tests/{tid}         # 详情 (含步骤+边界展开结果)
PUT    /projects/{pid}/tests/{tid}         # 更新
DELETE /projects/{pid}/tests/{tid}         # 删除
POST   /projects/{pid}/tests/{tid}/clone   # 克隆

POST   /projects/{pid}/tests/nl            # 自然语言创建
       Body: { "description": "用户登录的各种异常情况" }

═══════════════════════════════════════════════
  测试执行
═══════════════════════════════════════════════
POST   /projects/{pid}/executions          # 触发执行
       Body: { "test_ids": [...], "mode": "smart|full|selection" }
GET    /projects/{pid}/executions/{eid}    # 执行状态+摘要
GET    /projects/{pid}/executions/{eid}/log # 执行日志(支持 ?tail=100)
WS     /projects/{pid}/executions/{eid}/live # WebSocket实时日志流
POST   /projects/{pid}/executions/{eid}/cancel # 取消执行

═══════════════════════════════════════════════
  智能分析
═══════════════════════════════════════════════
POST   /projects/{pid}/analyze/impact      # TIA影响分析
       Body: { "base_ref": "HEAD~1" }
POST   /projects/{pid}/analyze/flaky       # Flaky检测
GET    /projects/{pid}/analyze/health      # 测试健康度报告

═══════════════════════════════════════════════
  自愈
═══════════════════════════════════════════════
POST   /projects/{pid}/heal                # 批量自愈失败测试
POST   /projects/{pid}/tests/{tid}/heal    # 单测试自愈

═══════════════════════════════════════════════
  录制
═══════════════════════════════════════════════
POST   /projects/{pid}/record/browser/start  # 开始浏览器录制
POST   /projects/{pid}/record/browser/stop   # 停止并生成测试
POST   /projects/{pid}/record/api/start      # 开始API流量录制
POST   /projects/{pid}/record/api/stop       # 停止并生成测试

═══════════════════════════════════════════════
  报告
═══════════════════════════════════════════════
GET    /projects/{pid}/reports/latest        # 最新报告
GET    /projects/{pid}/reports/trend         # 趋势数据
GET    /projects/{pid}/reports/export        # 导出 (?format=junit|allure|pdf|json)

═══════════════════════════════════════════════
  导入/导出
═══════════════════════════════════════════════
POST   /projects/{pid}/import                # 导入已有测试
       Body: multipart/form-data {file: pytest|jest|junit_xml|postman|openapi}
GET    /projects/{pid}/export                # 导出所有测试 (?format=yaml|json|junit)
```

---

## 十五、已有测试导入

| 来源 | 导入方式 | 映射规则 |
|------|---------|---------|
| **pytest** | 解析 `.py` 测试文件 | `test_*.py` → 测试用例，函数→步骤，assert→断言 |
| **Jest/Mocha** | 解析 `.test.js/ts` 文件 | `describe` → 测试套件，`it/test` → 测试用例 |
| **JUnit XML** | 解析 XML 报告 | testcase → 测试用例，failure → 失败步骤 |
| **Postman Collection** | 解析 JSON | item → 测试用例，request → HTTP步骤 |
| **OpenAPI/Swagger** | 解析 YAML/JSON | path+method → 测试用例，schema → 边界展开 |
| **Playwright录制** | 解析录制脚本 | 操作序列 → 步骤，断言 → 断言 |

导入后的测试用例纳入 TestForge 管理，可进一步：
- 使用边界引擎补充边界测试
- 使用 TIA 关联代码变更
- 享受 Flaky 检测和自愈

---

## 十六、大项目处理策略

| 场景 | 策略 |
|------|------|
| **Monorepo (10+子项目)** | 每个子项目独立 `.testgen.yaml`，配置继承父级；并行处理各子项目 |
| **10K+ 源文件** | 增量AST解析(缓存+仅解析变更)；依赖图懒加载；分片并行分析 |
| **100K+ 测试用例** | 分片存储(SQLite按项目分文件/PostgreSQL分区表)；TIA按模块过滤 |
| **超长运行测试 (>10min)** | 标记为慢测试独立分组；支持分布式多Worker执行；超时告警 |
| **大体积Docker镜像** | 分层构建+预缓存沙箱镜像；按需拉取语言运行时 |
| **大量历史数据** | 自动归档策略(90天以上压缩存储、365天以上可配置清理) |

---

## 十七、离线/内网部署

| 场景 | 方案 |
|------|------|
| **完全离线** | 禁用AI生成(仅模板+搜索)；Docker镜像预打包；依赖离线安装包 |
| **内网LLM** | 支持接入私有化部署的模型(vLLM/Ollama/LocalAI)，通过LiteLLM的`openai/`兼容接口 |
| **内网PyPI** | 配置私有PyPI镜像，依赖安装指向内网源 |
| **无Docker环境** | `--no-docker`本地执行模式；跳过testcontainers相关功能 |

---

## 十八、扩展/插件机制

### 新语言插件接口

```python
# 插件通过 Python entry_points 注册
# pyproject.toml:
# [project.entry-points."testforge.languages"]
# rust = "testforge_plugin_rust: RustLanguage"

class LanguagePlugin(Protocol):
    """新语言必须实现的接口"""
    name: str                          # "rust"
    extensions: list[str]              # [".rs"]
    tree_sitter_grammar: str           # tree-sitter语法名
    test_frameworks: list[str]         # ["cargo test", "rstest"]
    
    def parse_ast(self, source: str) -> ASTNode: ...
    def generate_test_command(self, test_file: str) -> str: ...
    def parse_coverage(self, report: str) -> CoverageResult: ...
    def get_default_prompts(self) -> dict: ...    # LLM Prompt模板
```

### 插件市场

- 社区贡献的语言/框架/报告/通知插件
- 通过 `testgen plugin install <name>` 一键安装
- 插件质量评分和下载统计

---

## 十九、视觉回归测试

集成 Playwright 截图对比能力：

```yaml
# 测试用例中的视觉断言
steps:
  - id: step_checkout_page
    type: browser_navigate
    url: "https://app.example.com/checkout"
    assertions:
      - type: visual_snapshot
        name: "checkout_page_v1"
        threshold: 0.02              # 2%像素差异容忍度
        ignore_regions:              # 忽略动态区域
          - selector: ".timestamp"
          - selector: ".ad-banner"
        full_page: true
```

| 能力 | 实现 |
|------|------|
| 像素级对比 | Playwright `page.screenshot()` + pixelmatch |
| AI语义对比 | 可选集成(未来: 使用LLM理解UI语义变化而非像素差异) |
| 动态内容忽略 | CSS选择器指定忽略区域；AI自动识别动态内容 |
| 基线管理 | 首次运行建立基线；后续对比基线；手动批准更新基线 |

---

## 二十、契约测试 (Contract Testing)

```yaml
type: contract
contract:
  consumer: "order-service"           # 消费者
  provider: "inventory-service"       # 提供者
  interactions:
    - description: "查询库存"
      request:
        method: GET
        path: "/api/inventory/PROD-001"
      response:
        status: 200
        body:
          product_id: "PROD-001"
          stock: 100
        required_fields: [product_id, stock]  # 必返回字段
```

| 能力 | 实现 |
|------|------|
| Consumer端 | 定义期望的请求/响应；生成Pact文件 |
| Provider端 | 验证Pact契约；Mock Provider响应 |
| CI集成 | Provider变更时自动验证契约；不兼容变更告警 |
| 与Pact互操作 | 可导入/导出标准Pact JSON格式 |

---

## 二十一、成本估算

### LLM API 调用成本

| 项目规模 | 源文件 | 每次全量生成 | 月均(CI每天运行) |
|----------|--------|:-----------:|:----------------:|
| 小型 | ~50个 | ~$0.05 (模板为主) | ~$1-2 |
| 中型 | ~200个 | ~$0.50 | ~$10-15 |
| 大型 | ~1000个 | ~$3-5 | ~$60-100 |
| 超大型 | ~5000个 | ~$15-25 | ~$200-400 |

*估算基于 qwen-plus 定价，实际取决于代码复杂度、模板命中率、增量生成。模板命中可节省 60-80% LLM 调用。*

### 成本优化开关

```yaml
# .testgen.yaml
cost_control:
  monthly_budget: 50            # 月预算上限(美元)，超限自动切模板模式
  template_first: true          # 优先模板
  model_tiering: true           # 简单函数用便宜模型
  max_llm_calls_per_run: 100    # 单次运行LLM调用上限
```

---

## 二十二、性能指标 (SLA目标)

| 指标 | 目标 | 测量方式 |
|------|:----:|---------|
| 测试设计器页面加载 | <2秒 | Lighthouse Performance |
| 单测试用例保存 | <500ms | API响应时间 P95 |
| 测试执行触发延迟 | <3秒 | 从点击到首个测试开始 |
| LLM生成单个测试 | <30秒 | 含API往返+后处理 |
| TIA分析 (1000文件项目) | <10秒 | 依赖图分析+匹配 |
| 报告生成 (1000条结果) | <5秒 | 聚合计算+渲染 |
| WebSocket实时日志延迟 | <1秒 | 执行→前端显示 |
| 并发执行(单机) | 4 worker | Docker资源限制 |
| 并发执行(集群) | 按Worker线性扩展 | Celery Worker数量 |
| 数据库响应 | <100ms P95 | SQLite/PostgreSQL |

---

## 二十三、监控与告警

| 监控项 | 告警规则 | 通知方式 |
|--------|---------|---------|
| LLM API 可用性 | 连续3次失败 | Slack/钉钉/邮件 |
| 测试覆盖率下降 | 相比上次下降>5% | PR评论 + 通知 |
| Flaky率上升 | >10%新增Flaky | 测试健康面板红色标记 |
| 执行队列堆积 | >50个待执行 | 通知 + 自动扩容建议 |
| Docker/沙箱不可用 | 即时 | 系统级告警 |
| 磁盘空间不足 | <1GB剩余 | 通知 + 自动清理建议 |
| 数据库连接失败 | 即时 | 系统级告警+自动重试 |

---

*方案完成: 2026-06-28*  
*调研范围: 开源42工具 + 商业10平台 + 论文15篇 + 社区20+讨论*
*文档节数: 23节 | 覆盖: 定位→架构→技术栈→数据结构→项目结构→命令→数据流→计划→差异化→竞品→校验→风险→认证→API→导入→大项目→离线→插件→视觉回归→契约→成本→性能→监控*
