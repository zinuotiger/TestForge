"""Fallback 适配器 — 为 Java/Go/C++ 等语言提供占位实现"""

from backend.analyzer.languages import FunctionInfo, ImportInfo, CallEdge


class FallbackAdapter:
    name = "fallback"

    def parse(self, code: str) -> dict:
        return {"functions": []}

    def extract_functions(self, code: str) -> list[FunctionInfo]:
        return []

    def extract_imports(self, code: str) -> list[ImportInfo]:
        return []

    def extract_call_graph(self, code: str) -> list[CallEdge]:
        return []
