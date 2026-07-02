# 测试生成流水线 - 工具能力矩阵

## 一、AI/LLM 自动测试生成

| 工具 | ⭐ | 语言支持 | 测试类型 | 输入 | 输出 | 集成方式 | 核心优势 | 关键限制 |
|------|-----|---------|---------|------|------|---------|---------|---------|
| **qodo-cover** | 5454 | Python/Go/Java/JS | 单元测试 | 源码+覆盖率报告(cobertura/jacoco) | pytest/go test/JUnit/Groovy | CLI+Docker, LiteLLM 100+模型 | 覆盖率驱动迭代生成, flakiness检测, record/replay | 已停止维护(2025.6),需覆盖率报告 |
| **Pythagora** | 1823 | JavaScript/TypeScript | 单元+集成 | 源码(AST解析依赖) | Jest测试文件 | CLI+VS Code插件 | 零手写,自动发现函数调用链,找bug能力强 | 仅JS/TS,仅Jest,依赖GPT-4,已迁移到GPT Pilot |
| **LSPRAG** | 41 | 多语言(LSP) | 单元测试 | 源码+实时LSP上下文 | 框架原生测试 | IDE集成 | 清华出品,RAG+LSP实时感知代码结构 | Stars少,成熟度低 |
| **symflower** | 24 | 多语言 | 单元测试 | 源码 | 单元测试 | 符号执行+LLM混合 | 确定性分析+AI创造力互补 | 较新,生态待完善 |
| **codura** | 42 | Java | 单元测试+补全 | IDE上下文 | JUnit | IntelliJ插件 | LLM驱动的IDE内测试生成+代码补全 | 仅Java |
| **open-testgen-llm** | 6 | Python | 单元测试 | 源码 | pytest | CLI | Meta TestGen-LLM论文复现 | 实验性质 |

## 二、传统自动测试生成

| 工具 | ⭐ | 语言支持 | 技术原理 | 目标 | 输出 | 集成方式 |
|------|-----|---------|---------|------|------|---------|
| **EvoSuite** | 914 | Java | 遗传算法(进化搜索) | 分支/语句覆盖率最大化 | JUnit 4/5 | CLI jar + Maven插件 + IntelliJ插件 + Eclipse + Docker |
| **UTBotCpp** | 185 | C/C++ | 符号执行+动态分析 | 分支覆盖 | 原生C++测试 | CLI |
| **tcframe** | 163 | C++ | 脚本化规格 | 竞赛测试用例 | 输入输出文件 | CLI |

## 三、Property-Based Testing (自动生成测试数据)

| 工具 | ⭐ | 语言 | 核心能力 | Shrinking | 测试框架集成 |
|------|-----|------|---------|-----------|-------------|
| **Hypothesis** | 8743 | Python | 随机生成+边界用例+反例最小化 | ✅自动 | pytest/unittest |
| **fast-check** | 5037 | JS/TS | 属性测试+model-based testing | ✅完整 | Jest/Mocha/Jasmine/Ava/Tape |
| **quickcheck** | 2772 | Rust | 自动属性测试 | ✅ | Rust test |
| **scalacheck** | 1965 | Scala | 属性测试 | ✅ | ScalaTest/Specs2 |

## 四、Mutation Testing (验证测试质量)

| 工具 | ⭐ | 语言 | 变异算子数 | 集成 | 说明 |
|------|-----|------|-----------|------|------|
| **stryker-js** | 2929 | JS/TS | 30+ | 主流JS测试框架 | C#/Scala版本也活跃 |
| **infection** | 2213 | PHP | 多算子 | PHPUnit/PhpSpec/Codeception | PHP变异测试 |
| **stryker-net** | 2020 | C# | 30+ | .NET测试框架 | |
| **pitest** | 1830 | Java/JVM | 15+ | Maven/Gradle/Ant/JUnit | 业界最先进的JVM变异测试 |

## 五、Fuzz Testing (安全/鲁棒性)

| 工具 | ⭐ | 语言 | 原理 |
|------|-----|------|------|
| **oss-fuzz** | 12386 | 多语言 | Google开源持续Fuzzing平台,集成ClusterFuzz |
| **AFL++** | 6620 | C/C++ | 覆盖率引导Fuzzer,社区增强版 |

## 六、测试框架与运行器

| 工具 | ⭐ | 语言 | 测试类型 | 关键特性 |
|------|-----|------|---------|---------|
| **Playwright** | 91801 | JS/TS/Python/Java/.NET | E2E | 3浏览器,自动等待,trace viewer,认证状态复用,并行,MCP协议 |
| **Cypress** | 50421 | JS/TS | E2E/组件 | 实时重载,时间旅行调试,自动截图 |
| **googletest** | 38749 | C++ | 单元/Mock | xUnit风格,Mock框架 |
| **Selenium** | 34237 | 多语言 | E2E | 浏览器自动化鼻祖,WebDriver标准 |
| **pytest** | 14274 | Python | 单元/集成/功能 | fixture,parametrize,插件生态,assert introspection |
| **Catch2** | 20459 | C++ | 单元/BDD/TDD | Header-only,modern C++ |
| **mockito** | 15439 | Java | Mock | 最流行的Java Mock框架 |
| **JUnit** | 7035 | Java | 单元 | JVM测试标准,extension model |
| **NUnit** | 2624 | C# | 单元 | .NET测试框架 |
| **testcontainers** | 8666+2243 | Java/Python | 集成 | Docker容器即用即弃,真实环境 |

## 七、BDD/验收测试

| 工具 | ⭐ | 语言 | 特点 |
|------|-----|------|------|
| **Robot Framework** | 11713 | Python | 关键字驱动,纯文本语法,庞大生态 |
| **Cucumber** | 3356 | 多语言 | Gherkin语法,BDD标准 |
| **behave** | 3496 | Python | Python版BDD,Gherkin |

## 八、API测试生成与Mock

| 工具 | ⭐ | 语言 | 核心能力 |
|------|-----|------|---------|
| **keploy** | 17806 | 语言无关(eBPF) | 流量录制回放→自动生成API测试+数据Mock,基础设施虚拟化,AI覆盖率扩展 |
| **karate** | 8884 | Java | API测试+Mock+性能+协议测试,DSL |
| **rest-assured** | 7123 | Java | REST API测试DSL |

## 九、性能/负载测试

| 工具 | ⭐ | 语言 | 特点 |
|------|-----|------|------|
| **k6** | 30898 | Go+JS | Grafana出品,高性能,JS脚本驱动,CI友好 |
| **locust** | 27944 | Python | Python定义场景,分布式,实时Web UI,协程高并发 |
| **JMeter** | 9443 | Java | GUI+CLI,多协议,久经考验 |
| **gatling** | 6926 | Scala | 高性能,DSL,HTML报告 |

## 十、AI编程助手(含测试生成能力)

| 工具 | ⭐ | 测试能力 |
|------|-----|---------|
| **aider** | 46786 | `/test`命令生成测试,了解项目结构 |
| **continue** | 34542 | IDE内测试生成,上下文感知 |
| **tabby** | 33651 | 自托管代码补全含测试 |
| **pr-agent** | 11859 | PR中自动建议测试,代码审查含测试覆盖检查 |
