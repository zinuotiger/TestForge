"""报告生成模块"""

from backend.reporter.generator import (
    generate_junit_xml,
    generate_json_report,
    generate_html_report,
)
from backend.reporter.badge import (
    generate_coverage_badge,
    generate_score_badge,
    generate_pass_rate_badge,
)
from backend.reporter.allure_writer import generate_allure_results

__all__ = [
    "generate_junit_xml",
    "generate_json_report",
    "generate_html_report",
    "generate_coverage_badge",
    "generate_score_badge",
    "generate_pass_rate_badge",
    "generate_allure_results",
]
