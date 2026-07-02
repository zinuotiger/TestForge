"""TypeScript 语言适配器 — tree-sitter 优先 + 正则降级

继承 JavaScript 适配器的解析逻辑，增加 TypeScript 特有语法：
  - interface / type / enum 声明
  - 泛型参数 <T>
  - 类型注解 param: Type
  - 装饰器 @decorator
  - 访问修饰符 public/private/protected
"""

import re
from typing import Optional

from backend.analyzer.languages.javascript import JavaScriptAdapter
from backend.analyzer.languages.base import (
    FunctionInfo, ImportInfo, ClassInfo, CallEdge,
)


class TypeScriptAdapter(JavaScriptAdapter):
    name = "typescript"
    extensions = [".ts", ".tsx"]
    tree_sitter_grammar = "typescript"

    # ---- tree-sitter ----

    def _init_treesitter(self):
        try:
            import tree_sitter_typescript as tsts
            from tree_sitter import Language, Parser
            lang = Language(tsts.language_typescript())
            return Parser(lang)
        except ImportError:
            return None

    # ---- 正则降级（在 JS 基础上增加 TS 特有语法）----

    def _regex_extract_functions(self, code: str) -> list[FunctionInfo]:
        funcs = super()._regex_extract_functions(code)
        # TypeScript 方法定义: methodName(params): ReturnType {
        for m in re.finditer(
            r"(?:public|private|protected|static|\s)*\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*\S+)?\s*\{",
            code, re.MULTILINE,
        ):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "catch", "constructor"):
                if name == "constructor":
                    params = [p.strip().split(":")[0].strip() for p in m.group(2).split(",") if p.strip()]
                    funcs.append(FunctionInfo(
                        name="constructor", line=code[:m.start()].count("\n") + 1, params=params,
                    ))
                continue
            params = [p.strip().split(":")[0].strip() for p in m.group(2).split(",") if p.strip()]
            line = code[:m.start()].count("\n") + 1
            # 避免重复
            if not any(f.name == name and f.line == line for f in funcs):
                funcs.append(FunctionInfo(name=name, line=line, params=params))
        return funcs

    def _regex_extract_classes(self, code: str) -> list[ClassInfo]:
        classes = super()._regex_extract_classes(code)
        # TypeScript interface / type / enum
        for m in re.finditer(r"(?:export\s+)?interface\s+(\w+)", code, re.MULTILINE):
            classes.append(ClassInfo(name=m.group(1), line=code[:m.start()].count("\n") + 1))
        for m in re.finditer(r"(?:export\s+)?enum\s+(\w+)", code, re.MULTILINE):
            classes.append(ClassInfo(name=m.group(1), line=code[:m.start()].count("\n") + 1))
        return classes

    def _regex_extract_imports(self, code: str) -> list[ImportInfo]:
        imports = super()._regex_extract_imports(code)
        # TypeScript import type
        for m in re.finditer(r"import\s+type\s+.*?from\s+['\"]([^'\"]+)['\"]", code, re.MULTILINE):
            imports.append(ImportInfo(module=m.group(1), line=code[:m.start()].count("\n") + 1))
        return imports

    def _regex_extract_call_graph(self, code: str) -> list[CallEdge]:
        return super()._regex_extract_call_graph(code)
