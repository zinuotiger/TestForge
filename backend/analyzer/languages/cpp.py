"""C/C++ 语言适配器 — tree-sitter 优先 + 正则降级"""

import re
from typing import Optional

from backend.analyzer.languages.base import (
    LanguageAdapter, FunctionInfo, ImportInfo, ClassInfo, CallEdge,
)


class CppAdapter(LanguageAdapter):
    name = "cpp"
    extensions = [".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"]
    tree_sitter_grammar = "cpp"

    # ---- tree-sitter ----

    def _init_treesitter(self):
        try:
            import tree_sitter_cpp as tscpp
            from tree_sitter import Language, Parser
            lang = Language(tscpp.language())
            return Parser(lang)
        except ImportError:
            return None

    def _ts_extract_functions(self, code: str) -> Optional[list[FunctionInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            funcs = []
            self._ts_walk(tree.root_node, code, funcs, "function_definition", "declaration")
            return funcs if funcs else None
        except Exception:
            return None

    def _ts_walk(self, node, code: str, funcs: list, *types: str):
        if node.type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            if declarator:
                name = self._ts_extract_func_name(declarator, code)
                if name:
                    funcs.append(FunctionInfo(
                        name=name, line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        complexity=self._estimate_complexity(
                            code[node.start_byte:node.end_byte]
                        ),
                    ))
        for child in node.children:
            self._ts_walk(child, code, funcs, *types)

    @staticmethod
    def _ts_extract_func_name(declarator, code: str) -> str:
        """从 C++ 函数声明中提取函数名"""
        text = code[declarator.start_byte:declarator.end_byte]
        # 处理指针: ReturnType (*name)(params)
        m = re.search(r"\(\s*\*\s*(\w+)\s*\)", text)
        if m:
            return m.group(1)
        # 普通: ReturnType name(params)
        m = re.search(r"(\w+)\s*\(", text)
        if m:
            return m.group(1)
        return ""

    def _ts_extract_classes(self, code: str) -> Optional[list[ClassInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            classes = []
            self._ts_walk_classes(tree.root_node, code, classes)
            return classes if classes else None
        except Exception:
            return None

    def _ts_walk_classes(self, node, code: str, classes: list):
        if node.type in ("class_specifier", "struct_specifier"):
            name_node = node.child_by_field_name("name")
            if name_node:
                classes.append(ClassInfo(
                    name=code[name_node.start_byte:name_node.end_byte],
                    line=name_node.start_point[0] + 1,
                ))
        for child in node.children:
            self._ts_walk_classes(child, code, classes)

    def _ts_extract_imports(self, code: str) -> Optional[list[ImportInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            imports = []
            self._ts_walk_imports(tree.root_node, code, imports)
            return imports if imports else None
        except Exception:
            return None

    def _ts_walk_imports(self, node, code: str, imports: list):
        if node.type == "preproc_include":
            text = code[node.start_byte:node.end_byte]
            m = re.search(r'[<"]([^>"]+)[>"]', text)
            if m:
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
        if node.type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            if declarator:
                name = self._ts_extract_func_name(declarator, code)
                if name:
                    current_func = name
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
        # C/C++ 函数: ReturnType name(params) {
        # 跳过控制语句
        pattern = re.compile(
            r"(?:[\w:<>*&\s]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:const\s*)?(?:noexcept\s*)?\{",
            re.MULTILINE,
        )
        keywords = {"if", "for", "while", "switch", "catch", "return", "sizeof", "class", "struct"}
        for m in pattern.finditer(code):
            name = m.group(1)
            if name in keywords:
                continue
            params = [p.strip() for p in m.group(2).split(",") if p.strip() and p.strip() != "void"]
            line = code[:m.start()].count("\n") + 1
            funcs.append(FunctionInfo(name=name, line=line, params=params))
        return funcs

    def _regex_extract_classes(self, code: str) -> list[ClassInfo]:
        classes = []
        for m in re.finditer(
            r"\b(?:class|struct)\s+(\w+)\s*(?::\s*[\w,\s<>]+)?\s*\{",
            code, re.MULTILINE,
        ):
            classes.append(ClassInfo(name=m.group(1), line=code[:m.start()].count("\n") + 1))
        return classes

    def _regex_extract_imports(self, code: str) -> list[ImportInfo]:
        imports = []
        # #include <header> 或 #include "header"
        for m in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', code):
            imports.append(ImportInfo(module=m.group(1), line=code[:m.start()].count("\n") + 1))
        return imports

    def _regex_extract_call_graph(self, code: str) -> list[CallEdge]:
        edges = []
        func_starts = []
        pattern = re.compile(
            r"(?:[\w:<>*&\s]+)\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:noexcept\s*)?\{",
            re.MULTILINE,
        )
        keywords = {"if", "for", "while", "switch", "catch", "sizeof", "class", "struct"}
        for m in pattern.finditer(code):
            if m.group(1) not in keywords:
                func_starts.append((m.group(1), m.end()))
        for i, (caller, start) in enumerate(func_starts):
            end = func_starts[i + 1][1] if i + 1 < len(func_starts) else len(code)
            body = code[start:end]
            for cm in re.finditer(r"\b(\w+)\s*\(", body):
                callee = cm.group(1)
                if callee not in keywords and callee not in ("return", "sizeof", "new", "delete"):
                    edges.append(CallEdge(caller=caller, callee=callee))
        return edges
