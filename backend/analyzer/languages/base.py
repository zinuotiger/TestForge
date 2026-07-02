"""语言适配器基类 — 统一 AST 解析接口"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("testforge")


@dataclass
class ASTNode:
    """统一的 AST 节点表示"""
    node_type: str                       # function | class | method | import | call
    name: str
    line: int = 0
    end_line: int = 0
    params: list[str] = field(default_factory=list)
    body: str = ""                       # 源码片段
    children: list[ASTNode] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)   # public/private/static 等


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    line: int
    end_line: int = 0
    params: list[str] = field(default_factory=list)
    complexity: int = 1
    return_type: str = ""
    modifiers: list[str] = field(default_factory=list)
    docstring: str = ""


@dataclass
class ImportInfo:
    """导入信息"""
    module: str                          # 导入的模块/包
    names: list[str] = field(default_factory=list)   # from X import a, b
    line: int = 0
    is_local: bool = False               # 是否为本地/相对导入


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    line: int
    end_line: int = 0
    bases: list[str] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)


@dataclass
class CallEdge:
    """函数调用边（用于调用图）"""
    caller: str                          # 调用方函数名
    callee: str                          # 被调用函数名
    line: int = 0


class LanguageAdapter(ABC):
    """语言适配器抽象基类

    每种语言实现此类。优先使用 tree-sitter 精确解析，
    不可用时降级为正则启发式。
    """

    name: str = ""
    extensions: list[str] = []
    tree_sitter_grammar: str = ""        # tree-sitter 语法名

    def __init__(self):
        self._ts_parser = None
        self._ts_checked = False

    # ============ 公共 API ============

    def parse(self, code: str) -> dict:
        """完整解析代码，返回结构化结果"""
        return {
            "language": self.name,
            "functions": self.extract_functions(code),
            "classes": self.extract_classes(code),
            "imports": self.extract_imports(code),
            "call_graph": self.extract_call_graph(code),
            "complexity": self._total_complexity(code),
            "syntax_errors": self.check_syntax(code),
        }

    def extract_functions(self, code: str) -> list[FunctionInfo]:
        """提取所有函数定义"""
        if self._try_treesitter():
            result = self._ts_extract_functions(code)
            if result is not None:
                return result
        return self._regex_extract_functions(code)

    def extract_classes(self, code: str) -> list[ClassInfo]:
        """提取所有类定义"""
        if self._try_treesitter():
            result = self._ts_extract_classes(code)
            if result is not None:
                return result
        return self._regex_extract_classes(code)

    def extract_imports(self, code: str) -> list[ImportInfo]:
        """提取所有导入语句"""
        if self._try_treesitter():
            result = self._ts_extract_imports(code)
            if result is not None:
                return result
        return self._regex_extract_imports(code)

    def extract_call_graph(self, code: str) -> list[CallEdge]:
        """提取函数级调用图

        返回 caller → callee 的边列表，用于 TIA 影响分析。
        """
        if self._try_treesitter():
            result = self._ts_extract_call_graph(code)
            if result is not None:
                return result
        return self._regex_extract_call_graph(code)

    def check_syntax(self, code: str) -> list[dict]:
        """检查语法错误"""
        if self._try_treesitter():
            result = self._ts_check_syntax(code)
            if result is not None:
                return result
        return []  # 正则模式无法检查语法

    def _total_complexity(self, code: str) -> int:
        """计算总圈复杂度"""
        return sum(f.complexity for f in self.extract_functions(code))

    # ============ tree-sitter 子类实现（可选）============

    def _try_treesitter(self) -> bool:
        """检查 tree-sitter 是否可用（惰性初始化）"""
        if not self._ts_checked:
            self._ts_checked = True
            self._ts_parser = self._init_treesitter()
            if self._ts_parser:
                logger.debug("tree-sitter 可用: %s", self.name)
        return self._ts_parser is not None

    def _init_treesitter(self):
        """子类重写：初始化 tree-sitter parser，返回 parser 或 None"""
        return None

    def _ts_extract_functions(self, code: str) -> list[FunctionInfo] | None:
        return None

    def _ts_extract_classes(self, code: str) -> list[ClassInfo] | None:
        return None

    def _ts_extract_imports(self, code: str) -> list[ImportInfo] | None:
        return None

    def _ts_extract_call_graph(self, code: str) -> list[CallEdge] | None:
        return None

    def _ts_check_syntax(self, code: str) -> list[dict] | None:
        return None

    # ============ 正则降级子类实现（必须）============

    @abstractmethod
    def _regex_extract_functions(self, code: str) -> list[FunctionInfo]: ...

    @abstractmethod
    def _regex_extract_classes(self, code: str) -> list[ClassInfo]: ...

    @abstractmethod
    def _regex_extract_imports(self, code: str) -> list[ImportInfo]: ...

    @abstractmethod
    def _regex_extract_call_graph(self, code: str) -> list[CallEdge]: ...

    # ============ 辅助方法 ============

    @staticmethod
    def _line_of(code: str, pos: int) -> int:
        """字符偏移转行号"""
        return code.count("\n", 0, pos) + 1

    @staticmethod
    def _estimate_complexity(code: str) -> int:
        """通过控制流关键字估算圈复杂度"""
        import re
        keywords = len(re.findall(
            r"\b(if|elif|else|for|while|catch|except|case|switch|&&|\|\|)\b",
            code,
        ))
        return 1 + keywords


# ============ 工厂函数 + 注册表 ============

# 语言适配器注册表（扩展名 → 适配器）
_ADAPTERS: dict[str, "LanguageAdapter"] = {}


def register_adapter(adapter: "LanguageAdapter"):
    """注册语言适配器"""
    for ext in adapter.extensions:
        _ADAPTERS[ext] = adapter


def get_adapter(language: str) -> Optional["LanguageAdapter"]:
    """按语言名获取适配器"""
    lang_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "tsx": ".tsx", "jsx": ".jsx",
        "java": ".java",
        "go": ".go", "golang": ".go",
        "cpp": ".cpp", "c": ".c", "c++": ".cpp",
        "cc": ".cc", "cxx": ".cxx", "h": ".h", "hpp": ".hpp",
    }
    ext = lang_map.get(language.lower())
    if ext:
        return _ADAPTERS.get(ext)
    return None


def get_adapter_for_file(filepath: str) -> Optional["LanguageAdapter"]:
    """按文件扩展名获取适配器"""
    ext = Path(filepath).suffix.lower()
    return _ADAPTERS.get(ext)


def list_supported_languages() -> list[str]:
    """列出所有支持的语言"""
    seen: set[str] = set()
    for adapter in _ADAPTERS.values():
        seen.add(adapter.name)
    return sorted(seen)
