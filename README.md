# TestForge

> AI 驱动的全类型智能测试平台 —— 代码分析 → 测试生成 → 自动执行 → 智能修复，覆盖 Web/API/CLI 三种入口

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-195-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Lines](https://img.shields.io/badge/backend-24k_lines-9cf.svg)]()

**TestForge 解决的问题**：开发者写测试太慢、AI 工具只能生成不能执行验证、现有测试平台缺少多策略融合。TestForge 把代码分析、多策略测试生成、沙箱执行、安全扫描、AI Agent 串成一个闭环，你只需要提供代码，它帮你完成从"没有测试"到"有测试且通过了"的全流程。

---

## 架构

```
Users
 │
 ├── Web UI (React + TypeScript)   ── 可视化设计器、执行中心、Agent Playground
 ├── CLI  (testgen 命令)           ── 命令行触发生成/执行/分析/报告
 └── API  (REST + WebSocket)       ── CI/CD 集成、外部调用
         │
         ▼
┌──────────────────────────────────────────────────┐
│            FastAPI Backend (Port 9876)            │
│                                                   │
│  ┌──────────┬──────────┬──────────┐              │
│  │ Analyzer │Generator │ Executor │  多语言 AST   │
│  │ 静态分析  │ 五策略生成 │ 沙箱执行  │  安全扫描     │
│  ├──────────┼──────────┼──────────┤              │
│  │  Safety  │ Reporter │  Quality │  覆盖率/变异   │
│  │ 认证/限流  │ 多格式报告 │  健康度   │  Flaky检测   │
│  └──────────┴──────────┴──────────┘              │
│                                                   │
│  ┌──────────────────────────────────────┐        │
│  │         Multi-Agent 协作系统           │        │
│  │  Orchestrator → Analyst → Generator   │        │
│  │                  ↓         ↓          │        │
│  │               Reviewer ← Executor     │        │
│  │   (ReAct + Function Calling + 反思自纠) │        │
│  └──────────────────────────────────────┘        │
│                                                   │
│  ChromaDB (RAG)   SQLite / PostgreSQL             │
└──────────────────────────────────────────────────┘
```

---

## 核心能力

**五策略融合测试生成**

| 策略 | 引擎 | 成本 | 适用场景 |
|------|------|:--:|------|
| AI/LLM | LiteLLM 100+ 模型 (DashScope / DeepSeek / Ollama) | API | 复杂逻辑、多步骤场景 |
| 搜索进化 | EvoSuite (Java) | 算力 | 分支覆盖、边界值 |
| 属性测试 | Hypothesis / fast-check | 零 | 数据处理、fuzzing |
| 流量录制 | Keploy (eBPF) + 内置代理降级 | 零 | API 接口、集成测试 |
| 模板引擎 | 11 预置场景模板 | 零 | CRUD、认证、分页 |

**AI Agent 自主测试**

- 5 个协作 Agent：Orchestrator → Analyst → Generator → Executor → Reviewer
- ReAct + Function Calling，LLM 自主决策每一步
- 反思自纠：Reviewer 不通过 → 反馈给 Generator 重新生成（最多重试 2 次）
- 三种 Agent 框架可切换对比：自研 ReAct / 自研多 Agent / LangGraph StateGraph

**多语言 AST 分析**

- tree-sitter 精确解析（C 级性能）：Python / JavaScript / TypeScript / Java / Go / C++
- 代码异味检测：高复杂度 / 长函数 / 过多参数 / 硬编码密钥 / TODO
- 函数级调用图提取，支持 TIA 影响分析

**智能分析与自愈**

- **TIA**（Test Impact Analysis）：Git diff → 调用链追踪 → 只跑受影响的测试
- **Flaky 检测**：贝叶斯统计后验估计
- **变异测试**：mutmut (Python) / PITest (Java) / Stryker (JS/TS) + 内置降级方案
- **自愈引擎**：UI 选择器修复 / API Schema 适配 / 断言语义修正

**RAG 检索增强**（ChromaDB）

- BGE 中文 embedding 模型，语义级检索
- 三级降级：BGE → LiteLLM API → TF-IDF（零依赖可用）
- 测试用例自动入库，生成时检索相似用例参考

**企业级认证与安全**

- JWT 认证 (access_token 24h + refresh_token 7d)
- RBAC 三级权限：Admin / Editor / Viewer
- 密码 PBKDF2-SHA256 (200k 迭代)
- 登录速率限制、全局异常处理 + trace_id 追踪

**网站自动测试**

- OpenAPI/Swagger 文档导入 → 自动解析所有端点 → 生成测试用例
- 网页爬虫：死链检测 / 表单测试 / SEO 检查 / 性能审计 / JS 错误捕获
- 综合健康评分 0-100

---

## 项目规模

| 模块 | 行数 | 文件数 |
|------|-----:|------:|
| Backend (Python) | 24,173 | 106 |
| Frontend (React/TS) | 6,504 | 20 |
| CLI (Python) | 451 | 1 |
| Tests (pytest) | 5,209 | 14 |
| **总计** | **36,337** | **141** |

**195 个测试用例，全部通过。**

---

## 为什么这样设计

这些是面试中会真正被问到的问题：

**为什么有三个入口（Web UI / CLI / API）而不是合在一起？**
不同场景需要不同交互方式：开发者本地调试用 CLI，团队可视化查看用 Web UI，CI/CD 流水线用 REST API。三者共享同一套后端，但互不依赖，各自可以独立演进。

**为什么用 FastAPI 而不是 Django？**
项目核心是异步 IO 密集型任务（LLM 调用、代码执行、并发测试），FastAPI 的 asyncio 原生支持比 Django 的同步模型更适合。同时 Pydantic 类型系统天然适配项目中的 Schema 定义。

**为什么用 LiteLLM 而不是直接调 OpenAI SDK？**
避免供应商锁定。通过 LiteLLM 统一接口可以随时切换 DeepSeek / DashScope / Ollama 等 100+ 模型，还能做三通道降级（API → 本地 → 模板），控制成本。

**为什么 5 个 Agent 协作而不是 1 个大 Agent？**
单一 Agent 面对复杂测试任务容易遗漏步骤或产生幻觉。拆分为 5 个专职 Agent 各司其职，外加 Reviewer 的反思自纠机制，大幅提升生成质量和可观测性。

**为什么用 tree-sitter 做 AST 分析？**
正则表达式无法处理多语言语法差异和嵌套结构。tree-sitter 是 C 级性能的增量解析器，不会因代码量增大而线性变慢。

---

## 快速启动

```bash
# 前提: Python 3.12+, Node.js 18+

# 1. 安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key（可选，不填则使用模板引擎降级）

# 3. 启动后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 9876 --reload

# 4. 启动前端（新终端）
cd frontend && npm run dev

# 5. 打开浏览器
# 前端: http://localhost:3000
# API 文档: http://localhost:9876/api/docs
```

CLI 用法：

```bash
python cli/main.py design                # 打开可视化设计器
python cli/main.py create "用户登录的异常情况"  # 自然语言生成测试
python cli/main.py run --smart           # TIA 智能选择执行
python cli/main.py analyze --impact HEAD~1  # 变更影响分析
python cli/main.py dashboard --port 9876 # 启动 Web Dashboard
```

---

## 前端页面

| 页面 | 功能 |
|------|------|
| Dashboard | 流水线实时进度、WebSocket 日志流 |
| 测试设计器 | 可视化编排测试步骤 |
| 执行中心 | 选择策略触发生成+执行 |
| 网站测试 | 输入 URL → 自动扫描+测试+PDF 报告 |
| Agent Playground | AI Agent 自主测试演示 |
| Code Tester | 单文件/项目级代码综合测试 |
| 报告 | 统计图表 + 多格式下载 (HTML/JSON/JUnit/PDF) |
| 设置 | LLM 提供商配置 |

---

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | JWT 登录 |
| `/api/code/comprehensive-test` | POST | 代码综合测试（分析+生成+执行+安全） |
| `/api/code/project-test` | POST | 项目级批量测试 |
| `/api/tests/` | CRUD | 测试用例管理 |
| `/api/executions/run` | POST | 触发执行 |
| `/api/executions/analyze/*` | GET/POST | TIA / Flaky / 健康度 |
| `/api/reports/html\|json\|junit\|pdf` | GET | 多格式报告 |
| `/api/website/scan` | POST | 网站自动测试 |
| `/api/intelligence/agent/run` | POST | Agent 自主测试 |
| `/api/intelligence/rag/generate` | POST | RAG 增强生成 |
| `/ws/events` | WebSocket | 实时事件推送 |

---

## 项目结构

```
testforge/
├── backend/                  # FastAPI 后端 (24,173 行)
│   ├── main.py               # 应用入口
│   ├── config.py             # Pydantic Settings 配置
│   ├── api/                  # REST API 路由 (15 模块)
│   ├── core/                 # Pipeline / TIA / Agent / RAG / Scheduler
│   ├── generator/            # 五策略生成器 + OpenAPI 解析器
│   ├── executors/            # 代码执行器 / HTTP 执行器 / 浏览器执行器
│   ├── safety/               # 认证 / 限流 / 日志 / 沙箱 / 密钥扫描
│   ├── analyzer/             # 多语言静态分析器 (tree-sitter)
│   ├── reporter/             # JUnit / JSON / HTML / PDF 报告
│   ├── quality/              # 覆盖率 / 变异测试 / Flaky 检测
│   ├── integrations/         # Keploy 流量录制
│   ├── models/               # 数据模型
│   ├── migrations/           # 数据库迁移
│   └── dsl/                  # 测试场景 DSL
├── frontend/                 # React 18 + TypeScript (6,504 行, 8 页面)
│   └── src/
│       ├── pages/            # 页面组件
│       └── components/       # 通用组件
├── cli/                      # testgen CLI (451 行)
├── tests/                    # pytest 测试 (5,209 行, 195 用例)
├── docker/                   # Docker Compose 部署
├── docs/                     # 文档与 SOP
└── examples/                 # 多语言示例项目
```

---

## 运行测试

```bash
# 全部测试
python -m pytest tests/ -v

# 带覆盖率报告
python -m pytest tests/ -v --cov=backend --cov-report=html

# 只跑核心模块
python -m pytest tests/test_core.py tests/test_agent_core.py -v
```

---

## License

Apache 2.0  (c) 2026
