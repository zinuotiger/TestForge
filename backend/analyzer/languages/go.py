"""Go 语言适配器 — tree-sitter 优先 + 正则降级"""

import re
from typing import Optional

from backend.analyzer.languages.base import (
    LanguageAdapter, FunctionInfo, ImportInfo, ClassInfo, CallEdge,
)


class GoAdapter(LanguageAdapter):
    name = "go"
    extensions = [".go"]
    tree_sitter_grammar = "go"

    # ---- tree-sitter ----

    def _init_treesitter(self):
        try:
            import tree_sitter_go as tsgo
            from tree_sitter import Language, Parser
            lang = Language(tsgo.language())
            return Parser(lang)
        except ImportError:
            return None

    def _ts_extract_functions(self, code: str) -> Optional[list[FunctionInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            funcs = []
            self._ts_walk(tree.root_node, code, funcs, "function_declaration", "method_declaration")
            return funcs if funcs else None
        except Exception:
            return None

    def _ts_walk(self, node, code: str, funcs: list, *types: str):
        if node.type in types:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = code[name_node.start_byte:name_node.end_byte]
                funcs.append(FunctionInfo(
                    name=name, line=name_node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    complexity=self._estimate_complexity(
                        code[node.start_byte:node.end_byte]
                    ),
                ))
        for child in node.children:
            self._ts_walk(child, code, funcs, *types)

    def _ts_extract_classes(self, code: str) -> Optional[list[ClassInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            classes = []
            self._ts_walk_types(tree.root_node, code, classes)
            return classes if classes else None
        except Exception:
            return None

    def _ts_walk_types(self, node, code: str, classes: list):
        if node.type in ("type_declaration",):
            for child in node.children:
                if child.type in ("type_spec",):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        classes.append(ClassInfo(
                            name=code[name_node.start_byte:name_node.end_byte],
                            line=name_node.start_point[0] + 1,
                        ))
        for child in node.children:
            self._ts_walk_types(child, code, classes)

    def _ts_extract_imports(self, code: str) -> Optional[list[ImportInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            imports = []
            self._ts_walk_imports(tree.root_node, code, imports)
            return imports if imports else None
        except Exception:
            return None

    def _ts_walk_imports(self, node, code: str, imports: list):
        if node.type == "import_declaration":
            text = code[node.start_byte:node.end_byte]
            for m in re.finditer(r'"([^"]+)"', text):
                imports.append(ImportInfo(module=m.group(1), line=node.start_point[0] + 1))
        for child in node.children:
            self._ts_walk_imports(child, code, imports)

    def _ts_extract_call_graph(self, code: str) -> Optional[list[CallEdge]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            edges = []
            self._ts_walk_calls(tree.root_node, code, edges)
            return edges if edges else None
        except Exception:
            return None

    def _ts_walk_calls(self, node, code: str, edges: list, current_func: str = ""):
        if node.type in ("function_declaration", "method_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node:
                current_func = code[name_node.start_byte:name_node.end_byte]
        if node.type == "call_expression" and current_func:
            func_node = node.child_by_field_name("function")
            if func_node:
                callee = code[func_node.start_byte:func_node.end_byte]
                edges.append(CallEdge(caller=current_func, callee=callee, line=node.start_point[0] + 1))
        for child in node.children:
            self._ts_walk_calls(child, code, edges, current_func)

    def _ts_check_syntax(self, code: str) -> Optional[list[dict]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            errors = []
            self._ts_walk_errors(tree.root_node, errors)
            return errors
        except Exception:
            return None

    def _ts_walk_errors(self, node, errors: list):
        if node.type == "ERROR" or node.is_missing:
            errors.append({"line": node.start_point[0] + 1, "message": "语法错误"})
        for child in node.children:
            self._ts_walk_errors(child, errors)

    # ---- 正则降级 ----

    def _regex_extract_functions(self, code: str) -> list[FunctionInfo]:
        funcs = []
        # func name(params) ReturnType {
        # func (r Receiver) name(params) ReturnType {
        for m in re.finditer(r"func\s+(?:\([^)]*\)\s+)?(\w+)\s*\(([^)]*)\)", code, re.MULTILINE):
            params = [p.strip().split(" ")[0] for p in m.group(2).split(",") if p.strip()]
            line = code[:m.start()].count("\n") + 1
            funcs.append(FunctionInfo(name=m.group(1), line=line, params=params))
        return funcs

    def _regex_extract_classes(self, code: str) -> list[ClassInfo]:
        """Go 没有 class，但有 struct/interface type"""
        classes = []
        for m in re.finditer(r"type\s+(\w+)\s+(struct|interface)", code, re.MULTILINE):
            classes.append(ClassInfo(name=m.group(1), line=code[:m.start()].count("\n") + 1))
        return classes

    def _regex_extract_imports(self, code: str) -> list[ImportInfo]:
        imports = []
        # 单行: import "fmt"
        for m in re.finditer(r'^\s*import\s+"([^"]+)"', code, re.MULTILINE):
            imports.append(ImportInfo(module=m.group(1), line=code[:m.start()].count("\n") + 1))
        # 多行: import (\n "fmt"\n "os"\n )
        for m in re.finditer(r'import\s*\(\s*([^)]+)\s*\)', code, re.DOTALL):
            block = m.group(1)
            for line in block.split("\n"):
                lm = re.search(r'"([^"]+)"', line)
                if lm:
                    imports.append(ImportInfo(module=lm.group(1)))
        return imports

    def _regex_extract_call_graph(self, code: str) -> list[CallEdge]:
        edges = []
        func_starts = []
        for m in re.finditer(r"func\s+(?:\([^)]*\)\s+)?(\w+)\s*\([^)]*\)\s*(?:\([^)]*\)\s*)?\{", code, re.MULTILINE):
            func_starts.append((m.group(1), m.end()))
        for i, (caller, start) in enumerate(func_starts):
            end = func_starts[i + 1][1] if i + 1 < len(func_starts) else len(code)
            body = code[start:end]
            for cm in re.finditer(r"\b(\w+)\s*\(", body):
                callee = cm.group(1)
                if callee not in ("if", "for", "range", "switch", "select", "func", "return", "make", "append", "len", "cap", "new", "type"):
                    edges.append(CallEdge(caller=caller, callee=callee))
        return edges
