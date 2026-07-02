"""TIA 测试影响分析引擎 — Git diff → 函数级依赖图 → 只跑受影响测试

增强点（对比旧版）：
  1. 函数级调用图分析（旧版只做文件级 import 依赖）
  2. 多语言支持（Python/JS/TS/Java/Go/C++），通过语言适配器
  3. 反向调用链追踪：变更函数 → 谁调用了它 → 递归向上
  4. 测试-源码精确映射（通过函数名匹配，不仅靠文件名）
  5. 增量索引缓存（避免每次全量扫描）
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional

from backend.analyzer.languages import get_adapter_for_file

logger = logging.getLogger("testforge")


class TIAEngine:
    """Test Impact Analysis: 代码变更 → 影响范围 → 选择性执行

    数据结构:
      _file_deps:    file → set(depended_files)         文件级依赖（import）
      _call_graph:   function → set(called_functions)   正向调用图
      _reverse_call: function → set(callers)            反向调用图（谁调用了我）
      _func_to_file: function → file                    函数所在文件
      _test_map:     source_file → set(test_files)      源文件→测试文件映射
      _test_funcs:   test_file → set(test_function)     测试函数集合
    """

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root)
        self._file_deps: dict[str, set[str]] = {}
        self._call_graph: dict[str, set[str]] = {}
        self._reverse_call: dict[str, set[str]] = {}
        self._func_to_file: dict[str, set[str]] = {}
        self._test_map: dict[str, set[str]] = {}
        self._test_funcs: dict[str, set[str]] = {}
        self._built = False
        self._indexed_files: set[str] = set()

    def build_index(self):
        """构建依赖图、调用图和测试映射（多语言）"""
        self._file_deps.clear()
        self._call_graph.clear()
        self._reverse_call.clear()
        self._func_to_file.clear()
        self._test_map.clear()
        self._test_funcs.clear()
        self._indexed_files.clear()

        supported_exts = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp"}

        for src_file in self.root.rglob("*"):
            if not src_file.is_file():
                continue
            ext = src_file.suffix.lower()
            if ext not in supported_exts:
                continue
            # 跳过常见无关目录
            rel = str(src_file.relative_to(self.root)).replace("\\", "/")
            if any(part in ("node_modules", ".git", "venv", "__pycache__", "dist", "build", ".next", "target") for part in rel.split("/")):
                continue
            self._index_file(rel, src_file)

        self._built = True
        logger.info(
            "TIA 索引构建完成: %d 文件, %d 函数, %d 调用边, %d 测试文件",
            len(self._indexed_files), len(self._func_to_file),
            sum(len(v) for v in self._call_graph.values()), len(self._test_funcs),
        )

    def _index_file(self, rel_path: str, abs_path: Path):
        """索引单个文件"""
        adapter = get_adapter_for_file(rel_path)
        if not adapter:
            return

        try:
            code = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return

        self._indexed_files.add(rel_path)

        # 1. 提取函数和所在文件
        funcs = adapter.extract_functions(code)
        func_names = set()
        for f in funcs:
            func_names.add(f.name)
            self._func_to_file.setdefault(f.name, set()).add(rel_path)

        # 2. 提取导入 → 文件级依赖
        imports = adapter.extract_imports(code)
        deps: set[str] = set()
        for imp in imports:
            dep_file = self._resolve_import(imp.module, rel_path)
            if dep_file:
                deps.add(dep_file)
        self._file_deps[rel_path] = deps

        # 3. 提取调用图 → 正向 + 反向
        call_edges = adapter.extract_call_graph(code)
        for edge in call_edges:
            self._call_graph.setdefault(edge.caller, set()).add(edge.callee)
            self._reverse_call.setdefault(edge.callee, set()).add(edge.caller)

        # 4. 测试文件映射
        if self._is_test_file(rel_path):
            self._test_funcs[rel_path] = func_names
            # 测试 → 源码映射
            src = self._infer_source(rel_path)
            if src:
                self._test_map.setdefault(src, set()).add(rel_path)
            # 同时通过函数名匹配（test_add → add）
            for fn in func_names:
                src_func = self._strip_test_prefix(fn)
                if src_func and src_func in self._func_to_file:
                    for sf in self._func_to_file[src_func]:
                        self._test_map.setdefault(sf, set()).add(rel_path)

    def analyze(self, changed_files: list[str]) -> dict:
        """分析变更影响，返回需要执行的测试

        策略:
          1. 文件级：变更文件 → 直接关联的测试
          2. 依赖级：依赖该文件的模块 → 它们的测试
          3. 函数级：变更文件中的函数 → 反向调用链 → 受影响函数 → 它们的测试
        """
        if not self._built:
            self.build_index()

        affected_tests: set[str] = set()
        affected_functions: set[str] = set()
        affected_files: set[str] = set()

        for changed in changed_files:
            changed = changed.replace("\\", "/")
            affected_files.add(changed)

            # 1. 直接关联的测试
            if changed in self._test_map:
                affected_tests |= self._test_map[changed]

            # 2. 依赖该文件的模块（反向文件依赖）
            for dep_file, deps in self._file_deps.items():
                if changed in deps:
                    affected_files.add(dep_file)
                    if dep_file in self._test_map:
                        affected_tests |= self._test_map[dep_file]

            # 3. 函数级：找出变更文件中的函数，反向追踪调用链
            changed_funcs = {
                fn for fn, files in self._func_to_file.items() if changed in files
            }
            for func in changed_funcs:
                # 反向调用链（BFS，最多 3 层）
                callers = self._reverse_call_chain(func, max_depth=3)
                affected_functions |= callers
                affected_functions.add(func)

            # 4. 受影响函数所在文件的测试
            for func in affected_functions:
                for f in self._func_to_file.get(func, set()):
                    affected_files.add(f)
                    if f in self._test_map:
                        affected_tests |= self._test_map[f]

        # 5. 优先级排序
        priority = self._prioritize(list(affected_tests), list(affected_files))

        return {
            "changed_files": changed_files,
            "affected_files": sorted(affected_files),
            "affected_tests": sorted(affected_tests),
            "affected_functions": sorted(affected_functions),
            "total_tests": sum(len(v) for v in self._test_map.values()),
            "selected_count": len(affected_tests),
            "acceleration": self._calc_acceleration(len(affected_tests)),
            "priority": priority,
        }

    def get_diff(self, base_ref: str = "HEAD~1") -> list[str]:
        """获取 Git diff 变更文件列表"""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base_ref, "HEAD"],
                capture_output=True, text=True, cwd=str(self.root),
            )
            files = [f.strip() for f in result.stdout.split("\n") if f.strip()]
            return [f for f in files if not f.startswith(".")]
        except Exception:
            return []

    # ---- 内部方法 ----

    def _reverse_call_chain(self, func: str, max_depth: int = 3) -> set[str]:
        """BFS 反向调用链：找出所有直接/间接调用 func 的函数"""
        visited: set[str] = {func}
        queue = [(func, 0)]
        result: set[str] = set()

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for caller in self._reverse_call.get(current, set()):
                if caller not in visited:
                    visited.add(caller)
                    result.add(caller)
                    queue.append((caller, depth + 1))

        return result

    def _resolve_import(self, module: str, current_file: str) -> Optional[str]:
        """将 import 模块名解析为项目内文件路径"""
        if not module:
            return None
        # 相对路径导入（./foo, ../foo）
        if module.startswith("."):
            base_dir = os.path.dirname(current_file)
            rel = os.path.normpath(os.path.join(base_dir, module))
            for ext in (".py", ".js", ".ts", ".jsx", ".tsx"):
                candidate = rel + ext
                if candidate in self._indexed_files:
                    return candidate
                candidate = rel + "/index" + ext
                if candidate in self._indexed_files:
                    return candidate
            return None

        # 绝对模块名：尝试匹配文件路径
        # from backend.core.tia_engine → backend/core/tia_engine.py
        parts = module.replace(".", "/")
        for ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go"):
            candidate = parts + ext
            if candidate in self._indexed_files:
                return candidate
            candidate = parts + "/index" + ext
            if candidate in self._indexed_files:
                return candidate

        return None

    @staticmethod
    def _is_test_file(path: str) -> bool:
        """判断是否为测试文件"""
        basename = os.path.basename(path)
        return (
            basename.startswith("test_")
            or basename.endswith("_test.py")
            or basename.endswith(".test.js")
            or basename.endswith(".test.ts")
            or basename.endswith(".spec.js")
            or basename.endswith(".spec.ts")
            or basename.endswith("Test.java")
            or path.startswith("tests/")
            or "/test/" in path
            or "/tests/" in path
        )

    def _infer_source(self, test_path: str) -> Optional[str]:
        """从测试文件推断源文件路径"""
        basename = os.path.basename(test_path)
        # test_user.py → user.py, user_test.py → user.py
        if basename.startswith("test_"):
            src_name = basename[5:]
        elif basename.endswith("_test.py"):
            src_name = basename[:-8] + ".py"
        elif basename.endswith(".test.js"):
            src_name = basename[:-8] + ".js"
        elif basename.endswith(".test.ts"):
            src_name = basename[:-8] + ".ts"
        elif basename.endswith("Test.java"):
            src_name = basename[:-9] + ".java"
        else:
            src_name = basename

        # 在索引中搜索匹配
        for f in self._indexed_files:
            if os.path.basename(f) == src_name:
                return f
        return None

    @staticmethod
    def _strip_test_prefix(func_name: str) -> Optional[str]:
        """test_add → add, test_create_user → create_user"""
        if func_name.startswith("test_"):
            return func_name[5:]
        if func_name.startswith("test"):
            return func_name[4].lower() + func_name[5:]
        return None

    def _prioritize(self, tests: list[str], changed: list[str]) -> list[dict]:
        """测试优先级排序 P0/P1/P2"""
        result = []
        changed_basenames = {os.path.basename(c) for c in changed}
        changed_dirs = {os.path.dirname(c) for c in changed}

        for t in tests:
            score = 0
            for cb in changed_basenames:
                if cb in t:
                    score += 2
            for cd in changed_dirs:
                if cd and cd in t:
                    score += 1
            # 测试函数名匹配变更函数 → 加分
            test_funcs = self._test_funcs.get(t, set())
            for tf in test_funcs:
                src_func = self._strip_test_prefix(tf)
                if src_func and any(src_func in cf for cf in changed):
                    score += 3

            level = "P0" if score >= 3 else "P1" if score >= 1 else "P2"
            result.append({"test": t, "priority": level, "score": score})

        return sorted(result, key=lambda x: -x["score"])

    def _calc_acceleration(self, selected: int) -> str:
        total = sum(len(v) for v in self._test_map.values())
        if total == 0 or selected == 0:
            return "N/A"
        ratio = total / max(selected, 1)
        return f"{ratio:.1f}x"


# 全局单例
tia_engine = TIAEngine()
