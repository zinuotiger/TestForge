# TestForge — 全自动测试生成流水线 最终方案

> 版本: v1.0-final  
> 日期: 2026-06-28  
> 状态: 方案确认中，待编码

---

## 一、项目定位

**TestForge** 是一套多语言、多策略、全自动的测试生成与质量验证流水线。覆盖 **Python / Java / JavaScript / TypeScript / Go / C++** 六种语言，整合 **AI(LLM)生成 + 搜索生成 + 属性测试 + 流量录制回放** 四类策略，形成"生成→执行→验证→改进"闭环。

---

## 二、最终架构 (5层 + 2横切面)

```
                            ┌──────────────────────┐
                            │    📥 输入层          │
                            │ 源码│API Spec│PR Diff │
                            │ 流量│Proto│DB Schema  │
                            └──────────┬───────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  L1: 代码分析层 (Code Analysis)                                    │
│  ┌─────────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ tree-sitter      │  │ 依赖图构建   │  │ 覆盖率间隙分析   │    │
│  │ 统一AST IR       │  │ (import/call)│  │ (cobertura基准)  │    │
│  └─────────────────┘  └──────────────┘  └──────────────────┘    │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L2: 测试生成引擎 (Generation Engine)                              │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              策略路由器 (Strategy Router)                  │    │
│  │        代码复杂度/类型/覆盖率→自动选择最优策略               │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────┐ │
│  │ AI/LLM 路径  │ │ 搜索/进化    │ │ 属性测试     │ │流量录制 │ │
│  │              │ │              │ │              │ │         │ │
│  │ • qodo-cover │ │ • EvoSuite   │ │ • Hypothesis │ │• Keploy │ │
│  │ • LSPRAG     │ │   (Java)     │ │   (Python)   │ │  eBPF   │ │
│  │ • symflower  │ │ • UTBotCpp   │ │ • fast-check │ │ 录制回放│ │
│  │ • aider模式  │ │   (C/C++)    │ │   (JS/TS)    │ │         │ │
│  │ • LiteLLM    │ │              │ │ • quickcheck │ │         │ │
│  │   统一接口   │ │              │ │   (Rust)     │ │         │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────┬────┘ │
│         └────────────────┼───────────────┼───────────────┘      │
│                          ▼               ▼                       │
│              ┌──────────────────────────────────┐                │
│              │  测试模板库 (Template Library)    │                │
│              │  CRUD/认证/分页/文件上传/Webhook  │                │
│              │  → 直接填充，零LLM成本             │                │
│              └──────────────────────────────────┘                │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L3: 测试执行引擎 (Execution Engine) — Docker沙箱                  │
│                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │
│  │ pytest   │ │ JUnit 5  │ │ Jest/Mocha│ │ Playwright+Cypress│   │
│  │ (Python) │ │ (Java)   │ │ (JS/TS)   │ │ (E2E/浏览器)      │   │
│  ├──────────┤ ├──────────┤ ├──────────┤ ├──────────────────┤    │
│  │ k6/locust│ │ test-    │ │ Keploy   │ │ Robot Framework   │    │
│  │ (性能)   │ │ containers│ │ (API回放)│ │ (验收/BDD)        │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘    │
│                                                                    │
│  环境: testcontainers 动态创建DB/Cache/MQ/依赖服务                  │
│  隔离: 每个执行单元独立Docker容器，网络+文件系统隔离                 │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L4: 质量验证层 (Quality Gate)                                     │
│                                                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│  │ 覆盖率验证   │ │ 变异测试     │ │ Flaky检测    │              │
│  │ cobertura    │ │ PIT/Stryker  │ │ 重跑5次      │              │
│  │ jacoco/cov   │ │ Infection    │ │ 确定性       │              │
│  │ 门禁: ≥80%  │ │ 杀死率:≥80%  │ │ 不一致=拒绝  │              │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘              │
│         └────────────────┼───────────────┘                      │
│                          ▼                                       │
│              ┌──────────────────────┐                            │
│              │ Ragas 元评测层       │ ← LLM评估LLM生成的测试质量 │
│              │ 忠实度/相关性/覆盖度 │                            │
│              └──────────────────────┘                            │
│                          │                                       │
│                    质量不达标 → 反馈回L2重新生成                    │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  L5: 报告与集成层 (Reporting & Integration)                        │
│                                                                    │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌────────────────┐    │
│  │JUnit XML │ │Allure报告 │ │JSON结构化  │ │覆盖率Badge     │    │
│  │(CI标准)  │ │(可视化)   │ │(API消费)   │ │(README自动更新)│    │
│  └────┬─────┘ └─────┬─────┘ └─────┬──────┘ └───────┬────────┘    │
│       └─────────────┴─────────────┴───────────────┘              │
│                          ▼                                       │
│   GitHub Actions │ GitLab CI │ Jenkins │ 本地CLI │ Web Dashboard │
└──────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
                        横切面
═══════════════════════════════════════════════════════════════════
┌──────────────────────────────────────────────────────────────────┐
│  A. 安全横切面 (贯穿L1-L5)                                        │
│  • Prompt注入防护(L2) • 沙箱执行(L3) • 密钥泄露扫描(L2/L4)         │
│  • 危险代码检测(L4)  • 审计日志(全部)                              │
├──────────────────────────────────────────────────────────────────┤
│  B. 可观测性横切面 (贯穿L1-L5)                                     │
│  • 结构化JSON日志 • trace_id链路 • Prometheus Metrics              │
│  • 各阶段耗时分布 • 失败根因自动分类 • 告警规则                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 三、技术栈决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| **核心语言** | Python 3.11+ | 生态最完整(pytest/hypothesis/keploy SDK/Playwright SDK) |
| **AST解析** | tree-sitter (统一IR) | 支持60+语言，统一接口，C语言性能，比每种语言单独写解析器低10倍维护成本 |
| **LLM接口** | LiteLLM (100+模型) | qodo-cover验证过的方案，一行配置切换provider |
| **测试执行** | Docker + testcontainers | 环境隔离、即用即弃、防环境污染、安全沙箱 |
| **执行并行** | Python asyncio + Semaphore | 并行生成+串行写入，文件锁防冲突 |
| **任务队列** | Celery + Redis (v2.0) | v1.0异步足够，v2.0分布式扩展 |
| **数据库** | SQLite (本地) + ClickHouse (v2.0分析) | v1.0零依赖，v2.0时序分析 |
| **报告格式** | JUnit XML (主) + Allure (可视化) + JSON (API) | JUnit XML是CI工具通用标准 |
| **配置文件** | YAML (.testgen.yaml) | 人类可读，IDE支持好 |
| **包管理** | uv (pip/poetry双支持) | 速度快，用户已安装 |

---

## 四、策略路由器规则 (L2核心)

```
策略选择 = f(语言, 代码复杂度, 现有覆盖率, 函数类型)

┌────────────────────┬──────────┬──────────────────────────────┐
│ 场景               │ 策略     │ 实现工具                      │
├────────────────────┼──────────┼──────────────────────────────┤
│ 纯函数/工具函数    │ 模板     │ 内置Template库 (零成本)       │
│ Python 业务逻辑    │ AI+属性  │ qodo-cover + Hypothesis       │
│ Java 复杂类        │ 搜索+AI  │ EvoSuite + LiteLLM           │
│ JS/TS 业务模块     │ AI       │ Pythagora模式 + fast-check    │
│ Go 服务            │ AI       │ qodo-cover (Go模式)           │
│ C/C++ 关键路径     │ 符号执行 │ UTBotCpp + AFL++ Fuzz         │
│ REST API           │ 流量录制 │ Keploy eBPF录制回放           │
│ Web E2E            │ 录制     │ Playwright Codegen            │
│ 安全关键代码       │ Fuzz     │ AFL++ + OSS-Fuzz模式          │
│ 覆盖率低(<50%)     │ 搜索+AI  │ 进化优先→AI补充              │
│ 覆盖率中(50-80%)   │ AI       │ LLM迭代提升                  │
│ 覆盖率高(>80%)     │ AI+属性  │ 边界+异常补充                │
└────────────────────┴──────────┴──────────────────────────────┘
```

---

## 五、v1.0 范围定义

### 支持的语言和框架

| 语言 | AST解析 | 测试框架 | 生成策略 | Mock框架 | 覆盖率工具 |
|------|---------|---------|---------|---------|-----------|
| **Python** | ✅ tree-sitter-python | pytest | AI+属性+模板 | unittest.mock | pytest-cov |
| **Java** | ✅ tree-sitter-java | JUnit 5 | 搜索(EvoSuite)+AI | Mockito | JaCoCo |
| **JavaScript** | ✅ tree-sitter-javascript | Jest | AI+属性+模板 | jest.mock | istanbul/nyc |
| **TypeScript** | ✅ tree-sitter-typescript | Jest/Vitest | AI+属性 | jest.mock | istanbul |
| **Go** | ✅ tree-sitter-go | go test | AI+模板 | testify/mock | go coverage |
| **C++** | ✅ tree-sitter-cpp | Catch2/GoogleTest | 符号(UTBotCpp)+AI | GoogleMock | gcov/lcov |

### v1.0 包含的核心功能 (Phase 1-4)

```
✅ = v1.0实现    🔮 = v2.0规划    — = 暂无计划

Phase 1: 核心流水线 (Day 1-3)
  ✅ 统一AST IR (tree-sitter)               ✅ 策略路由器
  ✅ AI生成 (LiteLLM + qodo-cover模式)      ✅ 模板生成 (50+场景)
  ✅ 增量生成 (Git diff驱动)                ✅ 依赖感知生成
  ✅ 断言强度检测                            ✅ 人工审查Gate + Diff视图
  ✅ LLM→模板 Fallback                      ✅ 部分失败不阻塞
  ✅ 原子文件写入                            ✅ 多Provider Fallback
  ✅ 测试影响分析 (TIA)

Phase 2: 安全与质量 (Day 4-6)
  ✅ Docker沙箱执行                          ✅ 危险代码检测
  ✅ Prompt注入防护                           ✅ 密钥泄露扫描
  ✅ 测试数据脱敏                            ✅ 代码注入防御
  ✅ 多维度质量评分                          ✅ 独立性检查
  ✅ 确定性检查 (Flaky检测)                  ✅ 变异杀死率门禁
  ✅ 自动Fixture生成                         ✅ 测试数据隔离

Phase 3: 环境与性能 (Day 7-9)
  ✅ Docker Compose环境                      ✅ Testcontainers集成
  ✅ 并行生成+串行写入                       ✅ 增量AST解析 (缓存)
  ✅ 全量依赖锁定                            ✅ 三OS CI矩阵
  ✅ Python版本矩阵                          ✅ 一键命令 `testgen run`
  ✅ 清晰错误信息                            ✅ 多项目独立配置

Phase 4: 集成与进化 (Day 10-12)
  ✅ OpenAPI→测试生成                        ✅ Keploy流量录制回放
  ✅ GitHub Actions Action                   ✅ JUnit XML输出
  ✅ Allure报告                              ✅ 结构化JSON日志
  ✅ Prompt版本管理                          ✅ 闭环改进 (失败→分析→重生成)
  ✅ 插件化语言支持                          ✅ Playwright代码录制→测试
  ✅ 幂等性保证                              ✅ 合约测试生成

🔮 v2.0 规划:
  🔮 Celery分布式执行                        🔮 Web Dashboard
  🔮 VS Code/JetBrains插件                  🔮 自然语言需求输入
  🔮 多Agent协作                             🔮 性能基线+回归检测
  🔮 Visual Regression测试                  🔮 a11y无障碍测试
  🔮 gRPC/GraphQL测试生成                   🔮 移动端(Appium)测试
  🔮 安全专项(OWASP Top 10)                  🔮 跨项目知识迁移
  🔮 覆盖率趋势Dashboard                    🔮 SonarQube/W&B集成
```

---

## 六、核心命令设计

```bash
# 一键启动
testgen run                          # 自动检测语言/框架, 全项目生成

# 精确控制
testgen run --path src/auth.py       # 单文件
testgen run --func login_handler     # 单函数
testgen run --target-cov 90          # 目标覆盖率90%
testgen run --dry-run                # 只分析, 预览将生成的测试

# 增量模式
testgen run --since HEAD~1           # 只处理变更的代码
testgen run --diff main              # 相对main分支的变更

# 审查模式
testgen review                       # 交互式审查生成的测试 (accept/reject/edit)
testgen undo                         # 回滚上次生成

# 仅执行
testgen exec                         # 只运行已有测试 (不生成)

# 质量检查
testgen quality                      # 覆盖率+变异率+Flaky检测

# 初始化
testgen init                         # 交互式配置向导
testgen init --lang python --framework pytest

# API录制
testgen record --app "python main.py"  # Keploy模式录制API流量
testgen replay                        # 回放录制的API测试
```

---

## 七、配置文件设计 (.testgen.yaml)

```yaml
# TestForge 项目配置
version: "1.0"

project:
  name: "my-project"
  languages: ["python", "typescript"]
  test_directory: "tests"
  source_directory: "src"

generation:
  # 全局策略偏好
  strategy: "auto"  # auto | ai | search | template | hybrid
  
  # AI配置
  ai:
    provider: "qwen"  # 使用LiteLLM模型名
    model: "qwen-plus"
    fallback_chain: ["deepseek-chat", "gpt-4o-mini"]
    max_tokens: 4096
    temperature: 0.2
    
  # 模板匹配规则
  templates:
    enabled: true
    match_threshold: 0.8  # 相似度>0.8使用模板
    
  # 覆盖率目标
  target_coverage: 85
  max_iterations: 5  # LLM生成最大迭代轮数

execution:
  sandbox: "docker"  # docker | local
  parallel: true
  max_workers: 4
  timeout_per_test: 30  # 秒
  timeout_total: 1800   # 秒

quality:
  coverage:
    enabled: true
    threshold: 80         # 覆盖率门禁
    tool: "auto"          # auto | pytest-cov | jacoco | istanbul
    
  mutation:
    enabled: true         # 变异测试
    threshold: 80         # 杀死率门禁
    tools:                # 按语言
      python: "mutmut"
      java: "pitest"
      javascript: "stryker"
      
  flaky_detection:
    enabled: true
    rerun_count: 5        # flaky检测重跑次数

reporting:
  formats: ["junit", "allure", "json"]
  output_dir: "testgen-reports/"
  badge: true             # 自动更新README覆盖率徽章

ci:
  github_actions: true
  fail_on_regression: true
  comment_pr: true        # PR中评论测试结果

safety:
  sandbox: true
  scan_secrets: true
  block_dangerous: true   # 拦截危险代码

plugins:
  # 自定义策略/报告插件
  - "testforge-plugin-sonarqube"
  
ignore:
  # 跳过生成的文件/目录
  - "**/migrations/**"
  - "**/vendor/**"
  - "**/*.pb.go"
```

---

## 八、项目结构

```
testforge/
├── pyproject.toml              # 项目元信息 + 依赖
├── .testgen.yaml               # 默认全局配置
├── README.md
├── LICENSE
│
├── src/testforge/
│   ├── __init__.py
│   ├── cli/                    # CLI入口
│   │   ├── __init__.py
│   │   ├── main.py             # `testgen` 命令入口
│   │   ├── run.py              # run 子命令
│   │   ├── review.py           # review 子命令
│   │   └── init.py             # init 子命令
│   │
│   ├── core/                   # 核心流水线
│   │   ├── pipeline.py         # 主流水线编排器
│   │   ├── context.py          # 流水线上下文 (跨阶段状态)
│   │   └── checkpoint.py       # 检查点/断点续传
│   │
│   ├── analyzer/               # L1: 代码分析
│   │   ├── ast_parser.py       # tree-sitter 统一AST
│   │   ├── ir.py               # 统一中间表示 (IR)
│   │   ├── dependency.py       # 依赖图构建
│   │   ├── coverage_gap.py     # 覆盖率间隙分析
│   │   └── languages/          # 语言特定适配
│   │       ├── python.py
│   │       ├── java.py
│   │       ├── javascript.py
│   │       ├── typescript.py
│   │       ├── go.py
│   │       └── cpp.py
│   │
│   ├── generator/              # L2: 测试生成
│   │   ├── router.py           # 策略路由器
│   │   ├── ai_generator.py     # AI/LLM生成
│   │   ├── search_generator.py # EvoSuite/UTBotCpp封装
│   │   ├── property_generator.py # Hypothesis/fast-check
│   │   ├── traffic_generator.py  # Keploy流量录制
│   │   ├── template_engine.py  # 模板生成引擎
│   │   ├── templates/          # 内置模板库
│   │   │   ├── crud.py
│   │   │   ├── auth.py
│   │   │   ├── pagination.py
│   │   │   └── ...
│   │   └── prompts/            # LLM Prompt模板
│   │       ├── python_v1.md
│   │       ├── java_v1.md
│   │       └── ...
│   │
│   ├── executor/               # L3: 测试执行
│   │   ├── runner.py           # 执行编排
│   │   ├── docker.py           # Docker沙箱管理
│   │   ├── testcontainers_mgr.py # Testcontainers集成
│   │   └── adapters/           # 测试框架适配器
│   │       ├── pytest_adapter.py
│   │       ├── junit_adapter.py
│   │       ├── jest_adapter.py
│   │       └── ...
│   │
│   ├── quality/                # L4: 质量验证
│   │   ├── gate.py             # 质量门禁编排
│   │   ├── coverage.py         # 覆盖率验证
│   │   ├── mutation.py         # 变异测试集成
│   │   ├── flaky.py            # Flaky检测
│   │   ├── scoring.py          # 多维度质量评分
│   │   └── ragas_eval.py       # Ragas元评测
│   │
│   ├── reporter/               # L5: 报告
│   │   ├── junit_writer.py     # JUnit XML生成
│   │   ├── allure_writer.py    # Allure报告
│   │   ├── json_writer.py      # 结构化JSON
│   │   ├── badge.py            # 覆盖率徽章
│   │   └── dashboard.py        # 终端Dashboard
│   │
│   ├── safety/                 # 安全横切面
│   │   ├── sandbox.py          # 沙箱策略
│   │   ├── secret_scan.py      # 密钥扫描
│   │   ├── dangerous.py        # 危险代码检测
│   │   └── prompt_guard.py     # Prompt注入防护
│   │
│   ├── observability/          # 可观测性横切面
│   │   ├── logger.py           # 结构化日志
│   │   ├── metrics.py          # Prometheus指标
│   │   ├── tracing.py          # trace_id管理
│   │   └── alerts.py           # 告警规则
│   │
│   └── integrations/           # 外部集成
│       ├── github_actions.py   # GitHub Actions
│       ├── gitlab_ci.py        # GitLab CI
│       ├── pr_comment.py       # PR评论
│       └── evosuite_bridge.py  # EvoSuite JVM桥接
│
├── tests/                      # TestForge自身的测试
│   ├── test_analyzer/
│   ├── test_generator/
│   ├── test_executor/
│   ├── test_quality/
│   └── fixtures/
│
├── docker/                     # Docker相关
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── sandbox/                # 沙箱镜像
│
├── .github/                    # CI/CD
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── testgen-action.yml
│   └── actions/
│       └── testgen/
│
├── docs/                       # 文档
│   ├── architecture.md
│   ├── quickstart.md
│   ├── configuration.md
│   └── plugins.md
│
└── examples/                   # 示例项目
    ├── python-fastapi/
    ├── java-spring/
    ├── node-express/
    └── go-gin/
```

---

## 九、核心数据流

```
1. 用户执行: testgen run --path src/auth.py

2. Analyzer:
   - tree-sitter解析 → 提取函数签名/参数/返回类型/依赖/复杂度
   - 查询已有测试和覆盖率
   - 输出: IR (函数元信息列表)

3. Generator (Router):
   - 对每个函数计算: 复杂度得分 + 当前覆盖率 + 函数类型
   - 路由到最优策略:
     * 纯函数+低复杂度 → Template
     * 业务逻辑+中复杂度 → AI (LiteLLM)
     * Java类+低覆盖率 → Search (EvoSuite)
     * Python+高覆盖率 → Property (Hypothesis)
     * API端点 → Traffic (Keploy)
   - 生成测试代码 + Fixture

4. Executor:
   - 创建Docker沙箱
   - 注入测试文件 + 依赖
   - 运行测试框架
   - 收集: 通过/失败/stdout/stderr/覆盖率/执行时间

5. Quality Gate:
   - 覆盖率是否达标? (≥80%)
   - 变异杀死率是否达标? (≥80%)
   - 是否有flaky测试? (5次重跑一致)
   - 是否有危险代码? (安全扫描)
   - 不达标 → 返回Generator (重新生成, 最多5轮)

6. Reporter:
   - 生成JUnit XML + Allure HTML + JSON
   - 更新覆盖率Badge
   - CI模式: PR评论
   - 终端输出摘要

7. 人工审查Gate (非CI模式):
   - 展示新增/修改的测试列表
   - Diff视图逐条review
   - accept/reject/edit
   - 确认后写入文件
```

---

## 十、v1.0 实现里程碑

```
Day 1-3 ──── Phase 1: 核心流水线
  交付: testgen run 命令可生成Python测试
  验收: 用pytest项目演示: 覆盖率从0→≥50%

Day 4-6 ──── Phase 2: 安全与质量
  交付: 沙箱执行 + 质量门禁 + Flaky检测
  验收: 生成的测试100%通过安全扫描, 0 flaky

Day 7-9 ──── Phase 3: 环境与性能
  交付: 多语言支持 + Docker环境 + 并行执行
  验收: Python/Java/JS三语言演示通过

Day 10-12 ── Phase 4: 集成与进化
  交付: GitHub Action + JUnit XML + 闭环改进
  验收: CI中自动生成测试并评论PR
```

---

## 十一、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM API不稳定 | 生成中断 | Fallback链+模板降级+本地缓存 |
| EvoSuite兼容性 | Java生成失败 | v1.0支持Java 11+, Docker封装版本锁定 |
| eBPF权限(Keploy) | API录制失败 | v1.0 Keploy为可选特性, 非核心路径 |
| tree-sitter解析精度 | 部分语言解析不准 | 优先支持成熟binding(Python/JS/Java), 其他渐进完善 |
| 生成测试质量低 | 人工审查负担重 | 质量门禁拦截低质测试, Ragas元评测辅助 |
| Docker不可用 | 执行环境缺失 | --no-docker降级到本地执行 |
| 大型项目超时 | CI超时 | 增量生成+TIA(测试影响分析)只处理变更 |

---

## 十二、竞品差异化

| 对比维度 | TestForge | qodo-cover | EvoSuite | Pythagora | aider |
|----------|-----------|------------|----------|-----------|-------|
| 多语言 | ✅ 6语言 | ⚠️ 4语言 | ❌ 仅Java | ❌ 仅JS | ✅ 多语言 |
| 多策略融合 | ✅ AI+搜索+属性+流量 | ❌ 仅AI | ❌ 仅搜索 | ❌ 仅AI | ❌ 仅AI |
| 质量闭环 | ✅ 覆盖率+变异+Flaky+Ragas | ⚠️ 仅覆盖率 | ❌ 无 | ❌ 无 | ⚠️ 仅lint+test |
| 安全沙箱 | ✅ Docker隔离 | ❌ 无 | ❌ 无 | ❌ 无 | ❌ 无 |
| 流量录制 | ✅ Keploy eBPF | ❌ 无 | ❌ 无 | ⚠️ 手动录制 | ❌ 无 |
| 统一报告 | ✅ JUnit+Allure+JSON | ⚠️ HTML | ⚠️ HTML | ⚠️ Jest输出 | ❌ 无 |
| CI原生 | ✅ GitHub Action | ⚠️ 需Pro版 | ⚠️ Maven插件 | ❌ 无 | ⚠️ CLI |
| 增量生成 | ✅ Git diff驱动 | ❌ 无 | ❌ 无 | ❌ 无 | ⚠️ 手动范围 |
| 插件化 | ✅ 新语言插件 | ❌ 无 | ❌ 无 | ❌ 无 | ❌ 无 |
| 维护状态 | ✅ 活跃(新项目) | ❌ 已停维护 | ✅ 活跃 | ❌ 已迁移 | ✅ 活跃 |
