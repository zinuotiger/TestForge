"""Python 语言适配器 — AST 级别函数提取、导入和调用图分析"""

import ast
from backend.analyzer.languages import FunctionInfo, ImportInfo, CallEdge, ParsedFunction


class PythonAdapter:
    name = "python"

    def parse(self, code: str) -> dict:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"functions": [], "error": str(e)}
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in node.args.args]
                complexity = self._calc_complexity(node)
                funcs.append(ParsedFunction(
                    name=node.name, line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    complexity=complexity, params=params,
                ))
        return {"functions": funcs}

    def extract_functions(self, code: str) -> list[FunctionInfo]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                funcs.append(FunctionInfo(name=node.name))
        return funcs

    def extract_imports(self, code: str) -> list[ImportInfo]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(module=alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(ImportInfo(module=node.module))
        return imports

    def extract_call_graph(self, code: str) -> list[CallEdge]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        edges = []

        class CallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_func = None
            def visit_FunctionDef(self, node):
                prev = self.current_func
                self.current_func = node.name
                self.generic_visit(node)
                self.current_func = prev
            def visit_AsyncFunctionDef(self, node):
                prev = self.current_func
                self.current_func = node.name
                self.generic_visit(node)
                self.current_func = prev
            def visit_Call(self, node):
                if self.current_func:
                    if isinstance(node.func, ast.Name):
                        edges.append(CallEdge(caller=self.current_func, callee=node.func.id))
                    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                        edges.append(CallEdge(caller=self.current_func, callee=f"{node.func.value.id}.{node.func.attr}"))
                self.generic_visit(node)

        CallVisitor().visit(tree)
        return edges

    @staticmethod
    def _calc_complexity(node) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor,
                                  ast.ExceptHandler, ast.With, ast.AsyncWith,
                                  ast.And, ast.Or, ast.Try, ast.Assert)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity
