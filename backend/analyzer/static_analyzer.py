"""多语言静态分析器 — 统一走语言适配器架构

设计文档第三节：tree-sitter（60+语言，C级性能）。
本模块委托给 backend.analyzer.languages 的适配器：
  - tree-sitter 可用时：精确 AST 解析
  - tree-sitter 不可用时：各语言正则降级
  - Python 额外支持内置 ast 模块（零依赖且精确）
"""

import re
from pathlib import Path

from backend.analyzer.languages import get_adapter, get_adapter_for_file


def analyze_file(filepath: str) -> dict:
    """根据文件扩展名选择分析器"""
    path = Path(filepath)
    if not path.exists():
        return {"error": f"文件不存在: {filepath}"}

    try:
        code = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return {"error": f"读取失败: {e}"}

    adapter = get_adapter_for_file(filepath)
    if not adapter:
        return {"error": f"不支持的语言: {path.suffix}"}

    return analyze_code(code, adapter.name)


def analyze_code(code: str, language: str = "python") -> dict:
    """直接分析代码字符串

    Args:
        code: 源代码
        language: python | javascript | typescript | java | go | cpp
    """
    adapter = get_adapter(language)
    if not adapter:
        return {"error": f"不支持的语言: {language}"}

    result = adapter.parse(code)

    # 补充代码异味检测
    smells = _detect_smells(code, result)
    result["smells"] = smells
    return result


# ============ 向后兼容：保留旧 API ============

def analyze_python(code: str) -> dict:
    """Python 静态分析（向后兼容旧接口）"""
    return analyze_code(code, "python")


def analyze_javascript(code: str) -> dict:
    """JavaScript/TypeScript 启发式分析（向后兼容旧接口）"""
    return analyze_code(code, "javascript")


# ============ 代码异味检测 ============

def _detect_smells(code: str, analysis: dict) -> list[dict]:
    """基于分析结果检测代码异味"""
    smells = []

    # 高复杂度函数
    for func in analysis.get("functions", []):
        complexity = func.complexity if hasattr(func, "complexity") else func.get("complexity", 1)
        name = func.name if hasattr(func, "name") else func.get("name", "")
        line = func.line if hasattr(func, "line") else func.get("line", 0)
        end_line = func.end_line if hasattr(func, "end_line") else func.get("end_line", line)
        params = func.params if hasattr(func, "params") else func.get("params", [])

        if complexity > 10:
            smells.append({
                "type": "high_complexity",
                "function": name,
                "line": line,
                "detail": f"圈复杂度 {complexity} > 10",
            })

        # 长函数
        line_count = end_line - line
        if line_count > 50:
            smells.append({
                "type": "long_function",
                "function": name,
                "line": line,
                "detail": f"函数长度 {line_count} 行 > 50",
            })

        # 过多参数
        if len(params) > 5:
            smells.append({
                "type": "too_many_params",
                "function": name,
                "line": line,
                "detail": f"参数数量 {len(params)} > 5",
            })

    # 硬编码密码/密钥
    secret_patterns = [
        (r'password\s*=\s*["\'][^"\']+["\']', "hardcoded_password"),
        (r'api_key\s*=\s*["\'][^"\']+["\']', "hardcoded_api_key"),
        (r'secret\s*=\s*["\'][^"\']+["\']', "hardcoded_secret"),
    ]
    for pattern, smell_type in secret_patterns:
        for m in re.finditer(pattern, code, re.IGNORECASE):
            line = code[:m.start()].count("\n") + 1
            smells.append({
                "type": smell_type,
                "line": line,
                "detail": "检测到硬编码敏感信息",
            })

    # TODO/FIXME 注释
    for m in re.finditer(r"\b(TODO|FIXME|HACK|XXX)\b", code):
        line = code[:m.start()].count("\n") + 1
        smells.append({
            "type": "todo_comment",
            "line": line,
            "detail": f"{m.group(1)} 注释待处理",
        })

    return smells
