"""多语言静态分析模块"""

from backend.analyzer.static_analyzer import (
    analyze_python,
    analyze_javascript,
    analyze_file,
    analyze_code,
)

__all__ = ["analyze_python", "analyze_javascript", "analyze_file", "analyze_code"]
