"""多语言适配器 — 为 TIA 引擎和静态分析器提供统一接口"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionInfo:
    name: str


@dataclass
class ImportInfo:
    module: str


@dataclass
class CallEdge:
    caller: str
    callee: str


@dataclass
class ParsedFunction:
    name: str
    line: int = 0
    end_line: int = 0
    complexity: int = 1
    params: list[str] = field(default_factory=list)


def get_adapter(language: str) -> Optional[object]:
    lang = language.lower()
    if lang == "python":
        from backend.analyzer.languages.python import PythonAdapter
        return PythonAdapter()
    if lang in ("javascript", "js", "typescript", "ts", "jsx", "tsx", "mjs"):
        from backend.analyzer.languages.javascript import JavaScriptAdapter
        return JavaScriptAdapter()
    if lang in ("java", "go", "cpp", "c", "c++", "h", "hpp", "cc", "cxx"):
        from backend.analyzer.languages.fallback import FallbackAdapter
        return FallbackAdapter()
    return None


def get_adapter_for_file(filepath: str) -> Optional[object]:
    ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
    lang_map = {
        "py": "python",
        "js": "javascript", "jsx": "javascript", "mjs": "javascript",
        "ts": "javascript", "tsx": "javascript",
        "java": "java", "go": "go",
        "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "c": "c", "h": "h", "hpp": "hpp",
    }
    lang = lang_map.get(ext)
    if lang:
        return get_adapter(lang)
    return None
