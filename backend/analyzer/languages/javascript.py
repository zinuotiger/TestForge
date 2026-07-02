"""JavaScript/TypeScript 适配器 — 正则级别函数提取、导入和调用图分析"""

import re
from backend.analyzer.languages import FunctionInfo, ImportInfo, CallEdge, ParsedFunction


class JavaScriptAdapter:
    name = "javascript"

    _FUNC_PATTERN = re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)"
        r"|(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"
        r"|(\w+)\s*:\s*(?:async\s+)?function"
        r"|class\s+(\w+)",
        re.MULTILINE,
    )
    _IMPORT_PATTERN = re.compile(
        r"""import\s+(?:{[^}]*}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]"""
        r"""|require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"""
        r"""|import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)""",
    )
    _TAG_NAMES = re.compile(r"<\w[\w-]*>", re.IGNORECASE)

    def parse(self, code: str) -> dict:
        funcs = []
        seen = set()
        lines = code.split("\n")
        cleaned = re.sub(r"//[^\n]*", "", code)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        for m in self._FUNC_PATTERN.finditer(cleaned):
            name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            if not name or name in seen:
                continue
            seen.add(name)
            pos = m.start()
            line_no = code[:pos].count("\n") + 1 if pos < len(code) else 0
            func_body_start = line_no
            end_line = min(line_no + 20, len(lines))
            complexity = 1 + len(re.findall(r"\b(if|else|for|while|switch|case|catch|try)\b", code[pos:]))
            params_match = re.search(r"\(([^)]*)\)", code[pos:pos + 200])
            params = []
            if params_match:
                params_str = params_match.group(1)
                if params_str.strip():
                    params = [p.strip().split("=")[0].strip().split(":")[0].strip()
                              for p in params_str.split(",")]
            funcs.append(ParsedFunction(
                name=name, line=line_no,
                end_line=end_line, complexity=min(complexity, 20),
                params=params,
            ))
        return {"functions": funcs}

    def extract_functions(self, code: str) -> list[FunctionInfo]:
        cleaned = re.sub(r"//[^\n]*", "", code)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        seen = set()
        funcs = []
        for m in self._FUNC_PATTERN.finditer(cleaned):
            name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            if name and name not in seen:
                seen.add(name)
                funcs.append(FunctionInfo(name=name))
        return funcs

    def extract_imports(self, code: str) -> list[ImportInfo]:
        cleaned = re.sub(r"//[^\n]*", "", code)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        imports = []
        seen = set()
        for m in self._IMPORT_PATTERN.finditer(cleaned):
            module = m.group(1) or m.group(2) or m.group(3)
            if module and module not in seen:
                seen.add(module)
                imports.append(ImportInfo(module=module))
        return imports

    def extract_call_graph(self, code: str) -> list[CallEdge]:
        cleaned = re.sub(r"//[^\n]*", "", code)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        func_names = set()
        for m in self._FUNC_PATTERN.finditer(cleaned):
            name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            if name:
                func_names.add(name)
        edges = []
        safe_names = [re.escape(fn) for fn in func_names]
        if safe_names:
            call_pattern = re.compile(r"\b(" + "|".join(safe_names) + r")\s*\(")
            edges_found = set()
            for m in call_pattern.finditer(cleaned):
                callee = m.group(1)
                for func_name in func_names:
                    if func_name != callee:
                        key = (func_name, callee)
                        if key not in edges_found:
                            edges_found.add(key)
                            edges.append(CallEdge(caller=func_name, callee=callee))
        return edges
