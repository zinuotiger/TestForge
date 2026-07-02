"""GitHub Actions 集成 — 生成 CI 工作流 / PR 评论

文档第二节 L6 报告与集成层 + 第十四节 ci 配置。
生成 .github/workflows/testforge.yml，支持 PR 评论。
"""

import logging
from pathlib import Path

logger = logging.getLogger("testforge")


# GitHub Actions 工作流模板
WORKFLOW_TEMPLATE = """name: TestForge CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  testforge:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # TIA 需要 git 历史

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install TestForge
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run smart tests (TIA)
        env:
          TESTFORGE_SECRET_KEY: ${{{{ secrets.TESTFORGE_SECRET_KEY }}
          TESTFORGE_LLM_API_KEY: ${{{{ secrets.TESTFORGE_LLM_API_KEY }}
        run: |
          python -m cli.main run --smart --target-cov {target_cov}

      - name: Generate reports
        if: always()
        run: |
          python -m cli.main report --format junit
          python -m cli.main report --format json

      - name: Upload coverage badge
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: testforge-reports
          path: testgen-reports/

      - name: Comment PR with results
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            try {{
              const report = JSON.parse(fs.readFileSync('testgen-reports/report.json', 'utf8'));
              const summary = report.summary || {{}};
              const body = [
                '## ⚒️ TestForge 测试报告',
                '',
                `| 指标 | 值 |`,
                `|------|-----|`,
                `| 总测试 | ${{summary.total || 0}} |`,
                `| 通过 | ${{summary.passed || 0}} |`,
                `| 失败 | ${{summary.failed || 0}} |`,
                `| 通过率 | ${{summary.pass_rate || 0}}% |`,
              ].join('\\n');
              github.rest.issues.createComment({{
                issue_number: context.issue.number,
                owner: context.repo.owner,
                repo: context.repo.repo,
                body,
              }});
            }} catch (e) {{
              console.log('No report found:', e.message);
            }}
"""


class GitHubActionsIntegration:
    """GitHub Actions CI 集成"""

    def generate_workflow(
        self,
        output_path: str = ".github/workflows/testforge.yml",
        target_cov: float = 80,
    ) -> dict:
        """生成 TestForge CI 工作流文件

        Args:
            output_path: 输出路径
            target_cov: 目标覆盖率

        Returns:
            {"status": "created", "path": str, "size": int}
        """
        content = WORKFLOW_TEMPLATE.format(target_cov=int(target_cov))
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        logger.info("GitHub Actions 工作流已生成: %s", output_path)
        return {
            "status": "created",
            "path": str(out),
            "size": len(content),
        }

    def generate_pr_comment(self, report: dict) -> str:
        """生成 PR 评论 Markdown

        Args:
            report: JSON 报告 {summary: {total, passed, failed, pass_rate}}

        Returns:
            Markdown 格式评论文本
        """
        summary = report.get("summary", {})
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        pass_rate = summary.get("pass_rate", 0)

        emoji = "✅" if failed == 0 else "⚠️"
        return f"""## {emoji} TestForge 测试报告

| 指标 | 值 |
|------|-----|
| 总测试 | {total} |
| 通过 | {passed} |
| 失败 | {failed} |
| 通过率 | {pass_rate}% |

<details>
<summary>📊 详细信息</summary>

- 由 TestForge 自动生成
- 触发方式: CI 自动运行
- 报告时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</details>
"""


# 全局单例
github_integration = GitHubActionsIntegration()
