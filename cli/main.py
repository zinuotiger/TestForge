"""TestForge CLI (testgen 命令) — 完整命令集

文档第六节核心命令：
  design / create / record browser|api / run / analyze / heal / quarantine / report / init
"""

import asyncio
import argparse
import webbrowser


def main():
    parser = argparse.ArgumentParser(
        prog="testgen",
        description="TestForge — 全类型智能测试平台",
    )
    sub = parser.add_subparsers(dest="command")

    # ===== 测试设计 =====
    sub.add_parser("design", help="打开可视化设计器 (Web UI)")

    create_parser = sub.add_parser("create", help="自然语言创建测试用例")
    create_parser.add_argument("description", help='自然语言描述，如 "用户登录的各种异常情况"')
    create_parser.add_argument("--base-url", default="", help="基础 URL")

    record_parser = sub.add_parser("record", help="录制测试")
    record_sub = record_parser.add_subparsers(dest="record_type")
    rb = record_sub.add_parser("browser", help="浏览器录制 (Playwright)")
    rb.add_argument("--url", default="about:blank", help="起始 URL")
    ra = record_sub.add_parser("api", help="API 流量录制 (Keploy)")
    ra.add_argument("-c", "--command", default="python app.py", help="启动应用命令")
    ra.add_argument("--port", type=int, default=8080, help="应用端口")

    # ===== 执行 =====
    run_parser = sub.add_parser("run", help="触发测试执行")
    run_parser.add_argument("path", nargs="?", default=".", help="源码路径")
    run_parser.add_argument("--smart", action="store_true", help="TIA智能选择")
    run_parser.add_argument("--smoke", action="store_true", help="冒烟测试(5min)")
    run_parser.add_argument("--full", action="store_true", help="全量回归")
    run_parser.add_argument("--target-cov", type=float, default=80, help="目标覆盖率")
    run_parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际运行")
    run_parser.add_argument("--llm", choices=["api", "local"], default="api")

    # ===== 智能分析 =====
    analyze = sub.add_parser("analyze", help="智能分析")
    analyze.add_argument("--impact", help="变更影响分析 (git ref)")
    analyze.add_argument("--flaky", action="store_true", help="Flaky检测")
    analyze.add_argument("--health", action="store_true", help="测试债务报告")

    # ===== 维护 =====
    sub.add_parser("heal", help="自愈失败的测试")
    quarantine_parser = sub.add_parser("quarantine", help="隔离 Flaky 测试")
    quarantine_parser.add_argument("test_id", help="测试用例 ID")
    sub.add_parser("review", help="交互式审查生成结果")
    # ===== 自进化闭环 =====
    evolution_parser = sub.add_parser("evolution", help="自进化闭环 (知识库、策略、报告)")
    evolution_sub = evolution_parser.add_subparsers(dest="evol_cmd")

    ev_report = evolution_sub.add_parser("report", help="进化报告 (策略权重、知识库统计)")

    ev_knowledge = evolution_sub.add_parser("knowledge", help="搜索进化知识库")
    ev_knowledge.add_argument("--query", "-q", default="", help="搜索关键词")
    ev_knowledge.add_argument("--category", "-c", default="", help="知识类别")
    ev_knowledge.add_argument("--limit", "-n", type=int, default=20, help="返回条数")

    evolution_sub.add_parser("strategies", help="推荐策略排序 (按进化权重)")

    ev_events = evolution_sub.add_parser("events", help="进化事件历史")
    ev_events.add_argument("--type", "-t", dest="event_type", default="", help="事件类型")
    ev_events.add_argument("--limit", "-n", type=int, default=50, help="返回条数")

    evolution_sub.add_parser("stats", help="进化引擎统计概览")

    ev_cross = evolution_sub.add_parser("cross-project", help="跨项目知识迁移")
    ev_cross.add_argument("source_project", help="源项目 ID")

    # ===== 报告 =====
    report = sub.add_parser("report", help="生成报告")
    report.add_argument("--format", choices=["html", "json", "junit", "pdf", "allure"], default="html")
    report.add_argument("--trend", action="store_true", help="历史趋势")

    # ===== Dashboard =====
    dash_parser = sub.add_parser("dashboard", help="打开Web Dashboard")
    dash_parser.add_argument("--port", type=int, default=9876)
    dash_parser.add_argument("--no-browser", action="store_true")

    # ===== 初始化 =====
    sub.add_parser("init", help="初始化项目配置")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    asyncio.run(_handle(args))


async def _handle(args):
    import aiohttp

    base_url = "http://localhost:9876"

    if args.command == "design":
        url = f"{base_url}/#/design"
        print(f"🎨 打开可视化设计器: {url}")
        webbrowser.open(url)

    elif args.command == "create":
        # 自然语言创建
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{base_url}/api/tests/nl",
                json={"description": args.description, "base_url": args.base_url},
            ) as resp:
                if resp.status != 200:
                    data = await resp.text()
                    print(f"❌ 创建失败: {data}")
                    return
                data = await resp.json()
                print(f"✅ 自然语言创建完成")
                print(f"   描述: {data.get('description', '')}")
                print(f"   生成 {data.get('generated_count', 0)} 个测试用例:")
                for tid in data.get("test_ids", []):
                    print(f"     - {tid}")

    elif args.command == "record":
        if not hasattr(args, "record_type") or not args.record_type:
            print("❌ 请指定录制类型: browser 或 api")
            return
        if args.record_type == "browser":
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{base_url}/api/record/browser/start",
                    json={"url": args.url, "browser": "chromium"},
                ) as resp:
                    data = await resp.json()
                    if data.get("status") == "error":
                        print(f"❌ {data['error']}")
                        return
                    print(f"🎥 浏览器录制已启动: {data.get('session_id')}")
                    print(f"   URL: {data.get('url')}")
                    print(f"   提示: {data.get('hint', '')}")
                    print(f"   完成后运行: testgen record browser --stop {data.get('session_id')}")
        elif args.record_type == "api":
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{base_url}/api/record/api/start",
                    json={"app_command": args.command, "port": args.port},
                ) as resp:
                    data = await resp.json()
                    if data.get("status") == "error":
                        print(f"❌ {data['error']}")
                        return
                    print(f"📡 API 流量录制已启动: {data.get('session_id')}")
                    print(f"   应用命令: {data.get('app_command')}")

    elif args.command == "run":
        if args.dry_run:
            print("🔍 Dry-run 模式：仅预览，不实际运行")
            return
        strategy = "smart" if args.smart else "smoke" if args.smoke else "full" if args.full else "smart"
        payload = {"path": args.path, "strategy": strategy, "llm_mode": args.llm}

        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base_url}/api/executions/run", json=payload) as resp:
                data = await resp.json()
                run_id = data["run_id"]
                print(f"🚀 执行已启动: {run_id}")
                print(f"   Dashboard: http://localhost:9876")
                print(f"   轮询状态中...")

                while True:
                    await asyncio.sleep(1)
                    async with s.get(f"{base_url}/api/executions/{run_id}") as r:
                        d = await r.json()
                        status = d.get("status", "running")
                        logs = d.get("logs", [])
                        if logs:
                            print(f"  {logs[-1]}")
                        if status in ("passed", "failed"):
                            print(f"\n{'✅ 通过' if status == 'passed' else '❌ 失败'} — {d.get('duration_ms', 0)}ms")
                            break

    elif args.command == "analyze":
        async with aiohttp.ClientSession() as s:
            if args.impact:
                async with s.post(f"{base_url}/api/executions/analyze/impact?ref={args.impact}") as resp:
                    data = await resp.json()
                    print(f"📊 影响分析: 变更文件 {len(data.get('changed_files', []))}, 选择测试 {data.get('selected_count', 0)}")
                    if data.get("acceleration"):
                        print(f"   加速比: {data['acceleration']}")
            if args.flaky:
                async with s.get(f"{base_url}/api/executions/analyze/flaky") as resp:
                    data = await resp.json()
                    flaky_tests = data.get("flaky_tests", [])
                    print(f"🔍 Flaky检测: 发现 {len(flaky_tests)} 个 Flaky 测试")
                    for ft in flaky_tests:
                        print(f"   - {ft.get('test', 'unknown')}: 评分={ft.get('flaky_score', 0)}")
            if args.health:
                async with s.get(f"{base_url}/api/executions/analyze/health") as resp:
                    data = await resp.json()
                    print(f"💊 健康度: {data.get('health_score', 'N/A')}/100 ({data.get('grade', '?')})")
                    for s_item in data.get("suggestions", []):
                        print(f"   [{s_item['priority']}] {s_item['action']}: {s_item['detail']}")

    elif args.command == "heal":
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base_url}/api/executions/heal", json={"test_ids": [], "layer": "assertion"}) as resp:
                data = await resp.json()
                print(f"🔧 自愈完成")
                print(f"   尝试: {data.get('total', 0)} 个")
                stats = data.get("stats", {})
                print(f"   成功率: {stats.get('success_rate', 0)}")
                print(f"   建议: 使用 testgen review 查看详细修复建议")

    elif args.command == "quarantine":
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base_url}/api/tests/{args.test_id}/quarantine") as resp:
                if resp.status == 200:
                    print(f"🔒 测试 {args.test_id} 已隔离")
                else:
                    print(f"❌ 隔离失败: {await resp.text()}")

    elif args.command == "review":
        print("📋 交互式审查模式")
        print("   打开 Web UI 查看生成结果: http://localhost:9876/#/design")
        webbrowser.open(f"{base_url}/#/design")

    elif args.command == "evolution":
            await _handle_evolution(args, base_url)
    elif args.command == "report":
        fmt = args.format
        async with aiohttp.ClientSession() as s:
            if args.trend:
                async with s.get(f"{base_url}/api/reports/trend") as resp:
                    data = await resp.json()
                    print(f"📈 历史趋势 ({data.get('days', 0)} 天):")
                    for day in data.get("trend", [])[:10]:
                        rate = round(day["passed"] / max(day["total"], 1) * 100, 1)
                        print(f"   {day['date']}: {day['total']} 测试, 通过率 {rate}%")
            elif fmt == "allure":
                async with s.post(f"{base_url}/api/reports/allure") as resp:
                    data = await resp.json()
                    print(f"📊 Allure 结果已生成: {data.get('files', 0)} 个文件")
                    print(f"   输出目录: {data.get('output_dir')}")
                    print(f"   使用 allure serve {data.get('output_dir')} 渲染")
            else:
                print(f"📋 报告地址: {base_url}/api/reports/{fmt}")

    elif args.command == "dashboard":
        port = args.port
        url = f"http://localhost:{port}"
        if not args.no_browser:
            webbrowser.open(url)
        print(f"🌐 Dashboard: {url}")

        import uvicorn
        uvicorn.run("backend.main:app", host="0.0.0.0", port=port, log_level="info")

    elif args.command == "init":
        await _init_project()


async def _handle_evolution(args, base_url):
    """Handle evolution-related CLI commands."""
    import aiohttp

    async with aiohttp.ClientSession() as s:
        if not args.evol_cmd or args.evol_cmd == "report":
            async with s.get(f"{base_url}/api/v1/evolution/report") as resp:
                data = await resp.json()
                print("========================================")
                print("  TestForge 自进化闭环报告")
                print("========================================")
                summary = data.get("summary", {})
                print(f"  总事件数:   {summary.get('total_events', 0)}")
                print(f"  知识条目:   {summary.get('total_knowledge', 0)}")
                print(f"  策略数量:   {summary.get('total_strategies', 0)}")
                print(f"  主推策略:   {summary.get('primary_strategy', 'template')}")
                print("----------------------------------------")
                print("  策略权重 (Thompson采样):")
                for s in data.get("strategies", []):
                    bar = "▓" * int(s["recommended_weight"] * 20)
                    print(f"    {s['name']:>10}  w={s['recommended_weight']:.3f}  "
                          f"calls={s['calls']}  sr={s['success_rate']}  {bar}")
                print("----------------------------------------")
                print("  近期事件分布:")
                for event_type, count in data.get("recent_event_distribution", {}).items():
                    print(f"    {event_type}: {count}")
                if data.get("recent_knowledge"):
                    print("----------------------------------------")
                    print("  最新知识条目:")
                    for k in data["recent_knowledge"][:5]:
                        print(f"    [{k.get('category', '')}] {k.get('title', '')} "
                              f"(score={k.get('score', 0)})")

        elif args.evol_cmd == "knowledge":
            params = {}
            if args.query:
                params["query"] = args.query
            if args.category:
                params["category"] = args.category
            params["limit"] = args.limit
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            async with s.get(f"{base_url}/api/v1/evolution/knowledge?{query_str}") as resp:
                data = await resp.json()
                print(f"知识库 (共 {data.get('total', 0)} 条):")
                for k in data.get("results", []):
                    print(f"  [{k.get('category', '')}] {k.get('title', '')} "
                          f"(score={k.get('score', 0)}, used={k.get('use_count', 0)}x)")

        elif args.evol_cmd == "strategies":
            async with s.get(f"{base_url}/api/v1/evolution/strategies/recommended") as resp:
                data = await resp.json()
                print(f"主推策略: {data.get('primary_strategy', 'template')}")
                print("策略排序 (按进化权重):")
                for i, s in enumerate(data.get("strategies", [])):
                    print(f"  {i+1}. {s['name']:>10}  w={s['weight']:.3f}  "
                          f"calls={s['calls']}  sr={s['success_rate']}")

        elif args.evol_cmd == "events":
            params = {}
            evt = getattr(args, 'event_type', '')
            if evt:
                params["event_type"] = evt
            params["limit"] = args.limit
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            async with s.get(f"{base_url}/api/v1/evolution/events?{query_str}") as resp:
                data = await resp.json()
                print(f"进化事件 (共 {data.get('total', 0)} 条):")
                for e in data.get("events", [])[:20]:
                    event_type = e.get("event_type", "unknown")
                    created = e.get("created_at", "")
                    print(f"  [{created}] {event_type}")
                    event_data = e.get("data", {})
                    if isinstance(event_data, str):
                        try:
                            import json
                            event_data = json.loads(event_data)
                        except Exception:
                            pass
                    if isinstance(event_data, dict):
                        for dk, dv in event_data.items():
                            if dk not in ("project_id",):
                                print(f"      {dk}: {str(dv)[:80]}")

        elif args.evol_cmd == "stats":
            async with s.get(f"{base_url}/api/v1/evolution/stats") as resp:
                data = await resp.json()
                print("========================================")
                print("  TestForge 进化引擎统计")
                print("========================================")
                print(f"  知识条目总数: {data.get('total_knowledge', 0)}")
                print(f"  近期事件(100): {data.get('total_events_100', 0)}")
                print("----------------------------------------")
                print("  策略状态:")
                for s in data.get("strategies", []):
                    print(f"    {s['name']:>10}  w={s['weight']:.3f}  "
                          f"calls={s['calls']}  sr={s['success_rate']}")
                print("----------------------------------------")
                print("  近期事件分布:")
                for event_type, count in data.get("recent_events", {}).items():
                    print(f"    {event_type}: {count}")

        elif args.evol_cmd == "cross-project":
            async with s.get(
                f"{base_url}/api/v1/evolution/cross-project/recommendations",
                json={"source_project": args.source_project, "all_projects": [args.source_project]},
            ) as resp:
                data = await resp.json()
                print(f"跨项目迁移推荐 (源: {args.source_project}):")
                if isinstance(data, list):
                    for item in data:
                        print(f"  知识: {item.get('title', '')} "
                              f"(来源: {item.get('source_project', '')}, "
                              f"相似度: {item.get('transfer_similarity', 0)})")
                else:
                    print(f"  {data}")


async def _init_project():
    """初始化项目配置"""
    from pathlib import Path

    config_content = """project:
  name: "my-project"
  languages: [python]
  test_directory: "tests"
  source_directory: "src"

generation:
  strategy: "auto"
  ai:
    provider: "dashscope"
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
    enabled: false
    threshold: 80
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

notifications:
  slack: ""
  dingtalk: ""
"""
    config_path = Path(".testgen.yaml")
    if config_path.exists():
        print(f"⚠️  {config_path} 已存在，跳过创建")
        return

    config_path.write_text(config_content, encoding="utf-8")
    print(f"📝 已创建 {config_path}")
    print(f"   编辑该文件配置你的项目，然后运行: testgen run")


if __name__ == "__main__":
    main()



