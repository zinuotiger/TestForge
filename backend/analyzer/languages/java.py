"""Java 语言适配器 — tree-sitter 优先 + 正则降级"""

import re
from typing import Optional

from backend.analyzer.languages.base import (
    LanguageAdapter, FunctionInfo, ImportInfo, ClassInfo, CallEdge,
)


class JavaAdapter(LanguageAdapter):
    name = "java"
    extensions = [".java"]
    tree_sitter_grammar = "java"

    # ---- tree-sitter ----

    def _init_treesitter(self):
        try:
            import tree_sitter_java as tsjava
            from tree_sitter import Language, Parser
            lang = Language(tsjava.language())
            return Parser(lang)
        except ImportError:
            return None

    def _ts_extract_functions(self, code: str) -> Optional[list[FunctionInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            funcs = []
            self._ts_walk_methods(tree.root_node, code, funcs)
            return funcs if funcs else None
        except Exception:
            return None

    def _ts_walk_methods(self, node, code: str, funcs: list):
        if node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = code[name_node.start_byte:name_node.end_byte]
                line = name_node.start_point[0] + 1
                modifiers = self._ts_get_modifiers(node, code)
                funcs.append(FunctionInfo(
                    name=name, line=line, end_line=node.end_point[0] + 1,
                    modifiers=modifiers,
                    complexity=self._estimate_complexity(
                        code[node.start_byte:node.end_byte]
                    ),
                ))
        for child in node.children:
            self._ts_walk_methods(child, code, funcs)

    @staticmethod
    def _ts_get_modifiers(node, code: str) -> list[str]:
        modifiers = []
        for child in node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if mod.type in ("public", "private", "protected", "static", "final", "abstract"):
                        modifiers.append(mod.type)
        return modifiers

    def _ts_extract_classes(self, code: str) -> Optional[list[ClassInfo]]:
        try:
            tree = self._ts_parser.parse(bytes(code, "utf-8"))
            classes = []
            self._ts_walk_classes(tree.root_node, code, classes)
            return classes if classes else None
        except Exception:
            return None

    def _ts_walk_classes(self, node, code: str, classes: list):
        if node.type in ("class_declaration", "interface_declaration", "enum_declaration"):
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
        if node.type == "import_declaration":
            text = code[node.start_byte:node.end_byte]
            m = re.search(r"import\s+(?:static\s+)?([^;]+);", text)
            if m:
                imports.append(ImportInfo(module=m.group(1).strip(), line=node.start_point[0] + 1))
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

    def _ts_walk_calls(self, node, code: str, edges: list, current_method: str = ""):
        if node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                current_method = code[name_node.start_byte:name_node.end_byte]
        if node.type == "method_invocation" and current_method:
            name_node = node.child_by_field_name("name")
            if name_node:
                callee = code[name_node.start_byte:name_node.end_byte]
                edges.append(CallEdge(caller=current_method, callee=callee, line=node.start_point[0] + 1))
        for child in node.children:
            self._ts_walk_calls(child, code, edges, current_method)

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
        # Java 方法: [modifiers] returnType methodName(params) {
        pattern = re.compile(
            r"(public|private|protected|static|final|abstract|synchronized|\s)*"
            r"(?:[\w<>\[\],\s]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{",
            re.MULTILINE,
        )
        for m in pattern.finditer(code):
            name = m.group(2)
            if name in ("if", "for", "while", "switch", "catch", "class", "interface", "enum"):
                continue
            params = [p.strip().split(" ")[-1].replace("...", "") for p in m.group(3).split(",") if p.strip()]
            line = code[:m.start()].count("\n") + 1
            funcs.append(FunctionInfo(name=name, line=line, params=params))
        return funcs

    def _regex_extract_classes(self, code: str) -> list[ClassInfo]:
        classes = []
        for m in re.finditer(
            r"(?:public\s+|private\s+|abstract\s+|final\s+)*"
            r"(class|interface|enum)\s+(\w+)(?:\s+extends\s+([\w,]+))?(?:\s+implements\s+([\w,]+))?",
            code, re.MULTILINE,
        ):
            bases = []
            if m.group(3):
                bases.extend(b.strip() for b in m.group(3).split(","))
            if m.group(4):
                bases.extend(b.strip() for b in m.group(4).split(","))
            classes.append(ClassInfo(
                name=m.group(2), line=code[:m.start()].count("\n") + 1, bases=bases,
            ))
        return classes

    def _regex_extract_imports(self, code: str) -> list[ImportInfo]:
        imports = []
        for m in re.finditer(r"^\s*import\s+(?:static\s+)?([^;]+);", code, re.MULTILINE):
            imports.append(ImportInfo(
                module=m.group(1).strip(), line=code[:m.start()].count("\n") + 1,
            ))
        return imports

    def _regex_extract_call_graph(self, code: str) -> list[CallEdge]:
        edges = []
        # 找方法定义
        method_starts = []
        pattern = re.compile(
            r"(?:public|private|protected|static|\s)*\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{",
            re.MULTILINE,
        )
        for m in pattern.finditer(code):
            name = m.group(1)
            if name not in ("if", "for", "while", "switch", "catch", "class"):
                method_starts.append((name, m.end()))
        for i, (caller, start) in enumerate(method_starts):
            end = method_starts[i + 1][1] if i + 1 < len(method_starts) else len(code)
            body = code[start:end]
            # 找方法调用: methodName(
            for cm in re.finditer(r"\b(\w+)\s*\(", body):
                callee = cm.group(1)
                if callee not in ("if", "for", "while", "switch", "catch", "return", "new", "this", "super"):
                    edges.append(CallEdge(caller=caller, callee=callee))
        return edges
