# TestForge ⚒️

> AI 驱动的全类型智能测试平台 — 测试设计 + 生成 + 执行 + 分析 + 自愈 + Agent

[![CI](https://github.com/user/testforge/actions/workflows/ci.yml/badge.svg)](https://github.com/user/testforge/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-60%2B-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

---

## 核心能力

### 五策略融合测试生成
| 策略 | 引擎 | 成本 | 适用 |
|------|------|:--:|------|
| 🤖 AI/LLM | LiteLLM 100+ 模型 (DashScope/DeepSeek/Ollama) | API | 复杂逻辑 |
| 🧬 搜索进化 | EvoSuite (Java) | 计算 | 分支覆盖 |
| 🔬 属性测试 | Hypothesis / fast-check | 零 | 数据处理 |
| 📡 流量录制 | Keploy (eBPF) + 内置代理降级 | 零 | API接口 |
| 📋 模板引擎 | 11 预置场景 | 零 | CRUD/认证 |

### 多语言 AST 分析（tree-sitter）
- 6 语言适配器：Python / JavaScript / TypeScript / Java / Go / C++
- tree-sitter 精确解析（C 级性能），不可用时自动降级为正则
- 函数级调用图提取，支持 TIA 影响分析
- 代码异味检测：高复杂度 / 长函数 / 过多参数 / 硬编码密钥 / TODO

### 变异测试（多语言 + 降级）
- Python: mutmut 优先 → 内置轻量变异器降级
- Java: PITest (pitest-maven)
- JS/TS: Stryker (npx stryker run)
- 内置变异器：算术/比较/布尔/常量/逻辑运算符变异，零依赖可用

### AI Agent 自主测试（ReAct + Function Calling）
- LLM 自主决策：分析代码 → 生成测试 → 执行 → 安全扫描 → 总结评估
- 5 个工具：`analyze_code` / `generate_tests` / `execute_tests` / `scan_security` / `finish`
- 最大 8 轮迭代，工具结果反馈给 LLM 决定下一步

### 多 Agent 协作系统
支持三种 Agent 框架，可在前端切换对比：

| 模式 | 框架 | 特点 |
|------|------|------|
| 🔧 单 Agent | 自研 ReAct | LLM 自主决策 + Function Calling |
| 🤝 多 Agent | 自研框架 | 5 Agent 协作 + 消息传递 + 反思自纠 + 记忆系统 |
| 🔷 LangGraph | LangGraph StateGraph | 声明式状态图 + 条件边路由 + MemorySaver checkpoint |

**LangGraph StateGraph 工作流：**
```
START → analyze → generate → execute → review → (pass → END | fail → retry → generate)
```

**5 个专业 Agent：**

| Agent | 角色 | 职责 |
|-------|------|------|
| 🎭 Orchestrator | 编排者 | 任务分解 + Agent 调度 + 结果聚合 + 反思重试 |
| 🔍 Analyst | 分析师 | 代码结构/复杂度/依赖/风险分析 |
| 🧬 Generator | 生成者 | 多策略测试生成 + 根据反馈改进 |
| ⚡ Executor | 执行者 | 测试执行 + 安全扫描 + 结果收集 |
| 🛡️ Reviewer | 审查者 | 质量评分 + 反思 + 触发重试 |

**核心能力：**
- **任务分解**：Orchestrator 用 LLM 将任务拆分为子任务，分配给专业 Agent
- **Agent 间通信**：结构化消息传递（task/result/feedback/query）
- **记忆系统**：短期记忆（工作记忆 FIFO）+ 长期记忆（跨任务知识积累）
- **反思自纠**：Reviewer 审查不通过 → 反馈给 Generator → 重新生成（最多重试 2 次）
- **状态机**：idle → thinking → acting → done/error
- **全程可观测**：前端实时展示 Agent 状态、协作时间线、消息流

### RAG 检索增强（ChromaDB + Embedding）
- **ChromaDB** 持久化向量库（语义级检索，百万级 HNSW 索引）
- **sentence-transformers** BGE 中文 embedding 模型（本地离线）
- **TF-IDF 降级**（chromadb 未安装时自动切换，零依赖可用）
- 三级 embedding 降级：BGE → LiteLLM API → TF-IDF
- 支持元数据过滤（按 type/tag/status 检索）

### RAG 检索增强
- TF-IDF 向量化 + 余弦相似度检索
- 测试用例自动入库，生成时检索相似用例参考

### 网站自动测试
- 输入 OpenAPI/Swagger 文档 URL → 自动解析所有端点
- 为每个端点生成测试用例（正常 + 边界 + 404）
- 并发执行真实 HTTP 请求并验证断言
- 支持 PDF 报告导出 + 邮件发送

### 网页爬虫
- BFS 异步爬取任意网站（同域过滤、robots.txt 尊重）
- 提取页面元数据（标题/状态码/响应时间/H1/meta description）
- 提取链接（内链/外链）、表单（含字段）、图片/脚本/样式资源
- 死链自动检测（4xx/5xx）
- 可配爬取深度、最大页面数、并发数

### 网页自动化测试
- **死链检测**：HEAD/GET 探测所有链接可达性
- **表单测试**：自动填充示例数据并探测响应码
- **可访问性**：图片 alt / 表单 label 检查
- **SEO 检查**：title / meta description / h1 完整性
- **安全检查**：Mixed Content / HTTP 表单提交
- **性能检查**：响应时间 / 资源数量
- **JS 错误捕获**：Playwright headless 浏览器（可选）
- **响应式截图**：mobile/tablet/desktop 三断点（可选）
- 综合健康评分（0-100）

### 智能分析
- **TIA**：Git diff → 函数级调用图 → 反向调用链追踪 → 只跑受影响测试（多语言支持）
- **Flaky 检测**：贝叶斯统计（Beta 分布后验估计）
- **健康度评分**：覆盖率(40%) + Flaky率(30%) + 维护成本(30%)
- **变异测试**：mutmut/PITest/Stryker + 内置降级方案

### 跨层自愈引擎
- **UI 选择器修复**：Playwright 真实验证 7 种选择器策略（data-testid/id/name/class/aria-label/xpath）
- **API Schema 修复**：字段增删检测 + 类型变更 + 必填字段缺失
- **断言修复**：数字容差/字符串包含/状态码范围语义判断

### 数据库双后端
- **SQLite**：单连接 + WAL 模式（本地/单用户，零配置）
- **PostgreSQL**：连接池 + 异步（团队/生产，高并发）
- 通过 `DATABASE_URL` 自动切换后端

### 定时巡检
- asyncio 后台调度，定时执行网站测试
- 通过率下降 >10% 自动告警 + 邮件通知

### E2E 浏览器测试
- Playwright 集成（导航/点击/输入/断言/截图）
- 失败自动截图

### 企业级认证与安全
- **登录系统**：用户名+密码 → JWT，前端登录页 + 路由守卫
- **RBAC 角色权限**：Admin / Editor / Viewer 三级权限矩阵
- **用户管理**：CRUD 用户 + 角色分配（仅 Admin）
- **Token 机制**：access_token(24h) + refresh_token(7d) 自动续期
- **API Token**：长期 Token 用于 CI/CD 自动化（可限作用域）
- **登录限流**：5 次失败/分钟 → 封 IP 15 分钟
- **全局异常处理**：统一错误响应格式 + trace_id 追踪
- **密码安全**：PBKDF2-SHA256 (200k 迭代)

### 容错与可观测
- **重试**：指数退避 + 随机抖动（可配最大次数/延迟/可重试异常）
- **熔断器**：三态切换（CLOSED/OPEN/HALF_OPEN），失败率阈值触发
- **吞吐量监控**：QPS / 延迟 P50/P95/P99 / 错误率
- **@resilient 装饰器**：一行代码组合重试+熔断+监控+超时
- **Prometheus 指标**：`/api/metrics` 端点暴露系统+业务指标

---

## 技术栈

| 层 | 技术 |
|----|------|
| **后端** | FastAPI + WebSocket + asyncio, SQLite 持久化 |
| **前端** | React 18 + TypeScript + Vite, 8 个页面 |
| **LLM** | LiteLLM (100+模型) + DashScope/DeepSeek/Ollama 三通道降级 |
| **Agent** | ReAct + Function Calling, 5 个工具 |
| **RAG** | TF-IDF 向量化 + 余弦相似度 |
| **报告** | JUnit XML / JSON / HTML / PDF 四格式 |
| **邮件** | SMTP (SSL/STARTTLS), HTML 邮件 + PDF 附件 |
| **E2E** | Playwright 浏览器自动化 |
| **部署** | Docker Compose + GitHub Actions CI (lint+test+build) |

---

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM API Key

# 3. 启动后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 9876 --reload

# 4. 启动前端
cd frontend && npm run dev

# 5. 打开浏览器
# 前端: http://localhost:3000
# API文档: http://localhost:9876/api/docs
```

---

## 前端页面

| 页面 | 功能 |
|------|------|
| 📊 Dashboard | 流水线实时进度, WebSocket 日志流 |
| 🎨 测试设计器 | 可视化编排测试步骤 |
| 🚀 执行中心 | 选择策略触发执行 |
| 🌐 网站测试 | 输入 URL → 自动生成+执行+PDF/邮件 |
| 🤖 Agent Playground | AI Agent 自主测试演示 |
| ⏰ 定时巡检 | 定时任务管理 + 告警 |
| 📋 报告 | 统计 + 多格式下载 |
| ⚙️ 设置 | LLM 提供商配置 |

---

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | JWT 登录 |
| `/api/tests/` | CRUD | 测试用例管理 |
| `/api/executions/run` | POST | 触发执行 |
| `/api/executions/analyze/*` | GET/POST | TIA/Flaky/健康度 |
| `/api/reports/html\|json\|junit` | GET | 多格式报告 |
| `/api/analysis/static\|coverage` | POST | 静态分析/覆盖率 |
| `/api/website/scan` | POST | 网站自动测试 |
| `/api/website/export\|email` | POST | PDF导出/邮件发送 |
| `/api/intelligence/agent/run` | POST | Agent 自主测试 |
| `/api/intelligence/rag/generate` | POST | RAG 增强生成 |
| `/api/intelligence/schedule/*` | CRUD | 定时巡检管理 |
| `/api/intelligence/e2e/run` | POST | E2E 浏览器测试 |
| `/ws/events` | WebSocket | 实时事件推送 |

---

## HTTPS 安全配置

TestForge 支持HTTPS以确保数据传输安全。以下是启用HTTPS的几种方式：

### 方案一：使用自签名证书（开发环境推荐）

#### 1. 生成SSL证书
```bash
# Windows
generate_ssl_cert.bat

# Linux/macOS
chmod +x generate_ssl_cert.sh
./generate_ssl_cert.sh

# 或手动生成
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj "/CN=localhost"
```

#### 2. 启动HTTPS环境
```bash
# Windows - 一键启动
start_https_all.bat

# Python脚本启动
python start_https_all.py

# 手动启动
python start_https_server.py
cd frontend && npm run dev
```

#### 3. 访问地址
- 前端应用: **https://localhost:3000**
- 后端API: **https://localhost:9876**
- API文档: **https://localhost:9876/api/docs**

> ⚠️ **注意**: 自签名证书会显示浏览器安全警告，在开发环境中可以安全忽略。

### 方案二：使用正式SSL证书（生产环境）

#### 1. 获取正式证书
从以下渠道获取正式SSL证书：
- Let's Encrypt (免费)
- 云服务商（阿里云、腾讯云、AWS等）
- 商业CA（DigiCert、GlobalSign等）

#### 2. 配置证书
将证书文件放入 `ssl/` 目录：
- `ssl/cert.pem` - 证书文件
- `ssl/key.pem` - 私钥文件
- `ssl/ca.pem` - CA证书链（可选）

#### 3. 启动HTTPS服务器
```bash
python start_https_server.py
```

### 方案三：使用反向代理（生产环境推荐）

在生产环境中，推荐使用Nginx或Apache作为反向代理：

#### Nginx配置示例：
```nginx
server {
    listen 443 ssl;
    server_name testforge.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:9876;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /api {
        proxy_pass http://localhost:9876;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 环境变量配置
可以通过环境变量配置HTTPS：
```bash
# 设置证书路径
export TESTFORGE_SSL_CERT_FILE=ssl/cert.pem
export TESTFORGE_SSL_KEY_FILE=ssl/key.pem

# 启动服务器
python start_https_server.py
```

### 安全建议
1. **开发环境**：使用自签名证书，但注意浏览器警告
2. **测试环境**：使用Let's Encrypt免费证书
3. **生产环境**：使用商业CA证书 + 反向代理
4. **定期更新**：证书过期前及时续期
5. **证书管理**：使用证书管理工具（如certbot）

---

## 项目结构

```
testforge/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置 (Pydantic Settings)
│   ├── api/                 # REST API (tests/executions/reports/website/agent/analysis)
│   ├── core/                # Pipeline/TIA/Flaky/自愈/健康度/Agent/RAG/Scheduler
│   ├── generator/           # 五策略生成 + OpenAPI解析器 + API测试生成器
│   ├── executors/           # 代码执行器 + HTTP执行器 + 浏览器执行器
│   ├── safety/              # 认证/限流/日志/沙箱/密钥扫描/邮件通知
│   ├── analyzer/            # 多语言静态分析器
│   ├── reporter/            # JUnit/JSON/HTML/PDF 报告
│   ├── integrations/        # Keploy 流量录制
│   ├── migrations/          # 数据库迁移
│   ├── dsl/                 # 测试场景 DSL
│   ├── models/              # 数据模型 + SQLite
│   └── quality/             # 覆盖率/变异测试
├── frontend/                # React 18 + TypeScript (8 页面)
├── cli/                     # testgen CLI
├── tests/                   # 60+ 测试
├── docker/                  # Dockerfile + Compose
└── docs/                    # SOP 文档
```

---

## 运行测试

```bash
python -m pytest tests/ -v --cov=backend --cov-report=html
```

---

## License

Apache 2.0 © 2026 TestForge Team
