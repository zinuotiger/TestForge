# TestForge 🚧

> AI 驱动的全类型智能测试平台 —— 代码分析 → 测试生成 → 自动执行 → 智能修复

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

## 项目状态

**当前阶段：早期开发 / MVP 验证**

| 状态 | 功能 |
|:--:|------|
| ✅ | **网站测试** — URL 输入 → 自动爬虫扫描 → 综合测试 → PDF 报告 |
| ✅ | **代码测试** — 代码/项目输入 → 分析 → 生成 → 执行 → 安全扫描 |
| ✅ | **Token 用量** — LLM 调用量统计与追踪 |
| ✅ | **系统设置** — LLM / SMTP / 应用配置管理 |
| 🚧 | 测试设计器 — 仅路由存在，交互未完 |
| 🚧 | 执行中心 — 仅路由存在，执行流程未闭环 |
| 🔮 | Multi-Agent 协作 — 架构已搭建，待集成调试 |
| 🔮 | 自进化引擎 — 框架存在，未接入实际流水线 |
| 🔮 | TIA 影响分析 — 调用链已实现，未接入 CI |
| 🔮 | RAG 检索增强 — ChromaDB 已集成，知识库未填充 |
| 🔮 | 定时巡检 — 调度器框架存在，未配置任务 |
| 🔮 | 报告中心 — 后端就绪，前端统计页未完成 |

> **面试说明**：本项目为个人全栈 Demo，核心已验证功能为网站测试 + 代码测试闭环。其余功能为架构预留代码，展示了模块化扩展能力。独立精简版见 [TestForge-Core](https://github.com/zinuotiger/TestForge-Core)。

---

## 架构

```
Users
 │
 ├── Web UI (React + TypeScript)   ── 可视化设计器、执行中心
 └── API  (REST + WebSocket)       ── CI/CD 集成、外部调用
         │
         ▼
┌──────────────────────────────────────────────────┐
│            FastAPI Backend (Port 9876)            │
│                                                   │
│  ┌──────────┬──────────┬──────────┐ ✅ 已实现    │
│  │ Analyzer │Generator │ Executor │  安全扫描     │
│  ├──────────┼──────────┼──────────┤              │
│  │  Safety  │ Reporter │  Quality │ 认证+限流      │
│  └──────────┴──────────┴──────────┘              │
│                                                   │
│  ┌──────────────────────────────────────┐ 🔮 规划中│
│  │         Multi-Agent 协作系统           │         │
│  │  RAG (ChromaDB)   自进化引擎           │         │
│  └──────────────────────────────────────┘        │
│                                                   │
│  SQLite ✅                     PostgreSQL 🔮       │
└──────────────────────────────────────────────────┘
```

---

## 核心能力

### ✅ 网站测试

- OpenAPI/Swagger 文档导入 → 自动解析所有端点 → 生成测试用例
- 网页爬虫：死链检测 / 表单测试 / SEO 检查 / 性能审计 / JS 错误捕获
- 综合健康评分 0-100 + PDF 报告导出

### ✅ 代码测试

- 代码/项目输入 → AST 分析 → 测试用例生成 → 沙箱安全执行 → 结果报告
- 支持 Python、JavaScript、TypeScript、Java、Go、C++ 多语言
- 安全扫描：密钥泄露检测 / Prompt 注入防护

### ✅ 认证与安全

- JWT 认证 (access_token 24h + refresh_token 7d)
- RBAC 三级权限：Admin / Editor / Viewer
- 密码 PBKDF2-SHA256、登录速率限制、全局异常处理

### 🔮 多策略融合测试生成（规划中）

| 策略 | 引擎 | 状态 |
|------|------|:--:|
| AI/LLM | LiteLLM (DashScope / DeepSeek / Ollama) | 🚧 |
| 搜索进化 | EvoSuite (Java) | 🔮 |
| 属性测试 | Hypothesis / fast-check | 🔮 |
| 流量录制 | Keploy (eBPF) | 🔮 |
| 模板引擎 | 11 预置场景模板 | 🔮 |

### 🔮 AI Agent 自主测试（架构就绪，待联调）

- 5 个协作 Agent 框架：Orchestrator → Analyst → Generator → Executor → Reviewer
- 三种框架可切换：自研 ReAct / 自研多 Agent / LangGraph StateGraph
- ReAct + Function Calling 决策循环已实现，端到端闭环待调试

### 🔮 智能分析与自愈（框架存在）

- **TIA**（Test Impact Analysis）：Git diff → 调用链追踪，已实现调用图，未接入 CI
- **Flaky 检测**：贝叶斯统计后验估计，算法已实现
- **自愈引擎**：UI 选择器修复 / API Schema 适配，框架存在

### 🔮 RAG 检索增强（引擎就绪）

- BGE 中文 embedding 模型 + ChromaDB，三级降级方案
- 检索引擎已集成，测试知识库待填充

---

## 项目规模

| 模块 | 行数 | 说明 |
|------|-----:|------|
| Backend (Python) | ~24,000 | 含规划中功能的代码框架 |
| Frontend (React/TS) | ~6,500 | 含规划中页面的路由 |
| **核心已验证代码** | **~10,000** | 网站测试 + 代码测试 + Token + 设置 |

> 项目整体代码量较大，因为采用了"架构优先"的模块化设计，24 个后端模块目录 + 14 个前端页面已预先搭建。独立精简版（仅核心功能，10,000 行）见桌面文件夹 `TestForge-Core`。

---

## 前端页面

| 状态 | 页面 | 说明 |
|:--:|------|------|
| ✅ | 网站测试 | 输入 URL → 自动扫描+测试+PDF 报告 |
| ✅ | 代码测试 | 单文件/项目级代码综合测试 |
| ✅ | Token 用量 | LLM 调用量统计 |
| ✅ | 设置 | LLM / SMTP / 应用配置 |
| 🚧 | Dashboard | 仅路由留存 |
| 🚧 | 测试设计器 | 仅路由留存 |
| 🔮 | Agent Playground | 页面已有，后端待联调 |
| 🔮 | 报告 | 后端就绪，前端待完善 |

---

## 为什么这样设计

**为什么代码量大但核心功能少？**

项目采用"架构优先"策略：先用模块化设计搭建完整骨架，再逐步填充。好处是每个功能独立在对应目录下，后期不会出现大面积重构迁移。当前阶段优先验证了网站测试和代码测试两个核心闭环。

**为什么用 FastAPI 而不是 Django？**

核心任务是异步 IO 密集型（LLM 调用、代码执行、并发测试），FastAPI 的 asyncio 原生支持更适合。

**为什么用 LiteLLM 而不是直接调 OpenAI SDK？**

避免供应商锁定，可随时切换 DeepSeek / DashScope / Ollama 等 100+ 模型，同时支持三通道降级控制成本。

---

## 快速启动

```bash
# 前提: Python 3.12+, Node.js 18+

# 1. 安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. 配置环境变量（可选，不填则使用模板引擎降级）
cp .env.example .env

# 3. 启动后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 9876 --reload

# 4. 启动前端（新终端）
cd frontend && npm run dev

# 5. 打开浏览器
# 前端: http://localhost:3000
# API 文档: http://localhost:9876/api/docs
```

---

## API 概览（核心端点）

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|:--:|
| `/api/auth/login` | POST | JWT 登录 | ✅ |
| `/api/website/scan` | POST | 网站自动测试 | ✅ |
| `/api/code/comprehensive-test` | POST | 代码综合测试 | ✅ |
| `/api/code/project-test` | POST | 项目级批量测试 | ✅ |
| `/api/token-usage/` | GET | Token 用量查询 | ✅ |
| `/api/settings/` | GET/PUT | 系统设置 | ✅ |
| `/api/tests/` | CRUD | 测试用例管理 | 🚧 |
| `/api/intelligence/agent/run` | POST | Agent 自主测试 | 🔮 |
| `/api/intelligence/rag/generate` | POST | RAG 增强生成 | 🔮 |
| `/ws/events` | WebSocket | 实时事件推送 | 🔮 |

---

## 项目结构

```
testforge/
├── backend/                  # FastAPI 后端 (~24,000 行)
│   ├── main.py               # 应用入口
│   ├── config.py             # Pydantic Settings 配置
│   ├── api/                  # REST API 路由 (15 模块，6 个已激活)
│   ├── core/                 # Pipeline / TIA / Agent / RAG / Scheduler
│   ├── generator/            # 五策略生成器 + OpenAPI 解析器
│   ├── executors/            # 代码执行器 / HTTP 执行器 / 浏览器执行器
│   ├── safety/               # 认证 / 限流 / 日志 / 沙箱 / 密钥扫描
│   ├── analyzer/             # 多语言静态分析器 (tree-sitter)
│   ├── reporter/             # 多格式报告
│   ├── quality/              # 覆盖率 / 变异测试 / Flaky 检测
│   ├── models/               # 数据模型
│   └── dsl/                  # 测试场景 DSL
├── frontend/                 # React 18 + TypeScript (~6,500 行, 14 页面)
│   └── src/pages/            # 页面组件（4 个已激活）
├── cli/                      # testgen CLI
├── tests/                    # pytest 测试
└── docs/                     # 文档
```

---

## License

Apache 2.0  (c) 2026
