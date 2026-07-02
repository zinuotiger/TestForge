"""变异测试 — 多语言支持 + 降级方案

支持语言/工具:
  - Python:  mutmut (优先) → 内置轻量变异器（降级）
  - Java:    PITest (pitest-maven)
  - JS/TS:   Stryker (npx stryker run)
  - 其他:    内置轻量变异器（降级）

降级策略：
  当外部工具不可用时，使用内置变异器对源码做简单变异
  （算术运算符替换、条件取反、常量修改），用已有测试验证。
  虽不如专业工具精确，但零依赖可用。
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("testforge")


# ============ 公共入口 ============

async def run_mutation_tests(
    source_file: str,
    test_file: str = "",
    language: str = "python",
    timeout: int = 120,
) -> dict:
    """运行变异测试

    Args:
        source_file: 源文件路径
        test_file: 测试文件路径（可选）
        language: python | java | javascript | typescript
        timeout: 超时秒数

    Returns:
        {killed, survived, total, mutation_score, threshold_met, status, tool}
    """
    if not Path(source_file).exists():
        return _error_result(f"源文件不存在: {source_file}")

    language = language.lower()

    # 按语言选择工具
    if language == "python":
        return await _run_python_mutation(source_file, test_file, timeout)
    elif language == "java":
        return await _run_java_mutation(source_file, timeout)
    elif language in ("javascript", "typescript"):
        return await _run_js_mutation(source_file, timeout)
    else:
        return await _run_builtin_mutation(source_file, test_file, language, timeout)


# ============ Python: mutmut 优先 → 内置降级 ============

async def _run_python_mutation(source_file: str, test_file: str, timeout: int) -> dict:
    """Python 变异测试：mutmut 优先，不可用时用内置变异器"""
    if _mutmut_available():
        return await _run_mutmut(source_file, test_file, timeout)
    logger.info("mutmut 不可用，降级为内置轻量变异器")
    return await _run_builtin_mutation(source_file, test_file, "python", timeout)


def _mutmut_available() -> bool:
    try:
        subprocess.run(["python", "-m", "mutmut", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


async def _run_mutmut(source_file: str, test_file: str, timeout: int) -> dict:
    """运行 mutmut"""
    try:
        runner = f"python -m pytest -x {test_file}" if test_file else "python -m pytest -x"
        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "mutmut", "run", "--paths-to-mutate", source_file,
            "--runner", runner,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=timeout)

        # 解析结果
        proc2 = await asyncio.create_subprocess_exec(
            "python", "-m", "mutmut", "results",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc2.communicate()
        output = stdout.decode("utf-8", errors="replace")

        killed_m = re.search(r"Killed mutants:\s*(\d+)", output)
        survived_m = re.search(r"Survived mutants:\s*(\d+)", output)
        killed = int(killed_m.group(1)) if killed_m else 0
        survived = int(survived_m.group(1)) if survived_m else 0
        total = killed + survived
        score = round(killed / max(total, 1) * 100, 1)

        return {
            "killed": killed, "survived": survived, "total": total,
            "mutation_score": score,
            "threshold_met": score >= settings.mutation_threshold,
            "status": "completed",
            "tool": "mutmut",
        }
    except asyncio.TimeoutError:
        return {"status": "timeout", "mutation_score": 0, "tool": "mutmut", "note": "变异测试超时"}
    except Exception as e:
        logger.warning("mutmut 执行失败，降级: %s", e)
        return await _run_builtin_mutation(source_file, test_file, "python", timeout)


# ============ Java: PITest ============

async def _run_java_mutation(source_file: str, timeout: int) -> dict:
    """Java 变异测试：PITest (pitest-maven)"""
    # 检查是否在 Maven 项目中
    project_dir = Path(source_file).parent
    while project_dir != project_dir.parent:
        if (project_dir / "pom.xml").exists():
            break
        project_dir = project_dir.parent
    else:
        return _error_result("未找到 pom.xml，PITest 需要 Maven 项目")

    if not _mvn_available():
        logger.info("Maven 不可用，降级为内置轻量变异器")
        return await _run_builtin_mutation(source_file, "", "java", timeout)

    try:
        proc = await asyncio.create_subprocess_exec(
            "mvn", "org.pitest:pitest-maven:mutationCoverage",
            "-DtargetClasses=" + _java_class_name(source_file),
            "-DtargetTests=*Test",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(project_dir),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = (stdout + stderr).decode("utf-8", errors="replace")

        # 解析 PITest 输出
        killed_m = re.search(r">>\s*KILLED\s*(\d+)", output)
        survived_m = re.search(r">>\s*SURVIVED\s*(\d+)", output)
        killed = int(killed_m.group(1)) if killed_m else 0
        survived = int(survived_m.group(1)) if survived_m else 0
        total = killed + survived
        score = round(killed / max(total, 1) * 100, 1)

        return {
            "killed": killed, "survived": survived, "total": total,
            "mutation_score": score,
            "threshold_met": score >= settings.mutation_threshold,
            "status": "completed" if total > 0 else "no_mutants",
            "tool": "pitest",
        }
    except asyncio.TimeoutError:
        return {"status": "timeout", "mutation_score": 0, "tool": "pitest"}
    except Exception as e:
        logger.warning("PITest 执行失败，降级: %s", e)
        return await _run_builtin_mutation(source_file, "", "java", timeout)


def _java_class_name(source_file: str) -> str:
    """从文件路径推断 Java 类名"""
    return Path(source_file).stem


def _mvn_available() -> bool:
    try:
        subprocess.run(["mvn", "--version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


# ============ JS/TS: Stryker ============

async def _run_js_mutation(source_file: str, timeout: int) -> dict:
    """JS/TS 变异测试：Stryker"""
    if not _npx_available():
        logger.info("npx 不可用，降级为内置轻量变异器")
        return await _run_builtin_mutation(source_file, "", "javascript", timeout)

    project_dir = Path(source_file).parent
    try:
        proc = await asyncio.create_subprocess_exec(
            "npx", "stryker", "run", "--mutate", source_file,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(project_dir),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = (stdout + stderr).decode("utf-8", errors="replace")

        # 解析 Stryker 输出
        killed_m = re.search(r"killed[:\s]+(\d+)", output, re.IGNORECASE)
        survived_m = re.search(r"survived[:\s]+(\d+)", output, re.IGNORECASE)
        score_m = re.search(r"mutation score[:\s]+([\d.]+)%?", output, re.IGNORECASE)

        killed = int(killed_m.group(1)) if killed_m else 0
        survived = int(survived_m.group(1)) if survived_m else 0
        total = killed + survived
        score = float(score_m.group(1)) if score_m else round(killed / max(total, 1) * 100, 1)

        return {
            "killed": killed, "survived": survived, "total": total,
            "mutation_score": score,
            "threshold_met": score >= settings.mutation_threshold,
            "status": "completed" if total > 0 else "no_mutants",
            "tool": "stryker",
        }
    except asyncio.TimeoutError:
        return {"status": "timeout", "mutation_score": 0, "tool": "stryker"}
    except Exception as e:
        logger.warning("Stryker 执行失败，降级: %s", e)
        return await _run_builtin_mutation(source_file, "", "javascript", timeout)


def _npx_available() -> bool:
    return shutil.which("npx") is not None


# ============ 内置轻量变异器（降级方案） ============

# 变异操作规则: (正则匹配, 替换函数)
# 每条规则对源码做一处变异，生成一个 mutant
_MUTATION_RULES = [
    # 算术运算符替换
    (re.compile(r"\+"), lambda m: "-", "arith_plus_to_minus"),
    (re.compile(r"(?<!<)-(?!>)"), lambda m: "+", "arith_minus_to_plus"),
    (re.compile(r"\*"), lambda m: "/", "arith_mul_to_div"),
    (re.compile(r"(?<!/)/(?!/)"), lambda m: "*", "arith_div_to_mul"),
    # 比较运算符
    (re.compile(r"=="), lambda m: "!=", "cmp_eq_to_neq"),
    (re.compile(r"!="), lambda m: "==", "cmp_neq_to_eq"),
    (re.compile(r"<="), lambda m: "<", "cmp_le_to_lt"),
    (re.compile(r">="), lambda m: ">", "cmp_ge_to_gt"),
    (re.compile(r"(?<![<>=!])<(?![=])"), lambda m: "<=", "cmp_lt_to_le"),
    (re.compile(r"(?<![<>=!])>(?![=])"), lambda m: ">=", "cmp_gt_to_ge"),
    # 布尔取反
    (re.compile(r"\bTrue\b"), lambda m: "False", "bool_true_to_false"),
    (re.compile(r"\bFalse\b"), lambda m: "True", "bool_false_to_true"),
    (re.compile(r"\btrue\b"), lambda m: "false", "bool_true_to_false_js"),
    (re.compile(r"\bfalse\b"), lambda m: "true", "bool_false_to_true_js"),
    # 常量修改
    (re.compile(r"\b0\b"), lambda m: "1", "const_0_to_1"),
    (re.compile(r"\b1\b"), lambda m: "0", "const_1_to_0"),
    # 逻辑运算符
    (re.compile(r"&&"), lambda m: "||", "logic_and_to_or"),
    (re.compile(r"\|\|"), lambda m: "&&", "logic_or_to_and"),
    (re.compile(r"\band\b"), lambda m: "or", "logic_and_to_or_py"),
    (re.compile(r"\bor\b"), lambda m: "and", "logic_or_to_and_py"),
]


async def _run_builtin_mutation(
    source_file: str,
    test_file: str,
    language: str,
    timeout: int,
) -> dict:
    """内置轻量变异器：对源码做简单变异，用测试验证

    流程:
      1. 读取源码
      2. 对每个可变异点生成一个 mutant
      3. 对每个 mutant 运行测试
      4. 测试失败 → killed；测试通过 → survived
    """
    try:
        source_code = Path(source_file).read_text(encoding="utf-8")
    except Exception as e:
        return _error_result(f"读取源文件失败: {e}")

    # 生成所有 mutant
    mutants = _generate_mutants(source_code)
    if not mutants:
        return {
            "killed": 0, "survived": 0, "total": 0,
            "mutation_score": 0, "threshold_met": False,
            "status": "no_mutants",
            "tool": "builtin",
            "note": "源码中未找到可变异的点",
        }

    # 如果没有测试文件，无法验证，返回生成数量
    if not test_file or not Path(test_file).exists():
        return {
            "killed": 0, "survived": 0,
            "total": len(mutants),
            "mutation_score": 0,
            "threshold_met": False,
            "status": "no_tests",
            "tool": "builtin",
            "note": f"生成了 {len(mutants)} 个变异体，但未提供测试文件，无法验证",
            "mutant_samples": mutants[:5],
        }

    # 逐个验证 mutant
    killed = 0
    survived = 0
    total = min(len(mutants), 20)  # 限制数量避免超时

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(total):
            mutant = mutants[i]
            mutant_path = os.path.join(tmpdir, Path(source_file).name)
            with open(mutant_path, "w", encoding="utf-8") as f:
                f.write(mutant["code"])

            # 运行测试
            test_passed = await _run_test_against_mutant(
                test_file, source_file, mutant_path, language, timeout // max(total, 1)
            )
            if test_passed:
                survived += 1
            else:
                killed += 1

    total_verified = killed + survived
    score = round(killed / max(total_verified, 1) * 100, 1)

    return {
        "killed": killed,
        "survived": survived,
        "total": total_verified,
        "generated": len(mutants),
        "mutation_score": score,
        "threshold_met": score >= settings.mutation_threshold,
        "status": "completed",
        "tool": "builtin",
        "note": "使用内置轻量变异器（mutmut/PITest/Stryker 不可用时的降级方案）",
    }


def _generate_mutants(source_code: str) -> list[dict]:
    """生成所有变异体"""
    mutants = []
    for pattern, replace_fn, mutation_type in _MUTATION_RULES:
        for m in pattern.finditer(source_code):
            # 只对第一个匹配做变异（避免一个规则产生过多 mutant）
            mutated = source_code[:m.start()] + replace_fn(m.group()) + source_code[m.end():]
            if mutated != source_code:
                mutants.append({
                    "type": mutation_type,
                    "line": source_code[:m.start()].count("\n") + 1,
                    "original": m.group(),
                    "mutated": replace_fn(m.group()),
                    "code": mutated,
                })
            break  # 每种规则只取第一个
    return mutants


async def _run_test_against_mutant(
    test_file: str,
    original_source: str,
    mutant_path: str,
    language: str,
    timeout: int,
) -> bool:
    """用变异后的源码运行测试，返回测试是否通过"""
    # 备份原始源码，替换为变异体
    import shutil as _shutil
    backup_path = original_source + ".bak"
    try:
        _shutil.copy2(original_source, backup_path)
        _shutil.copy2(mutant_path, original_source)

        if language == "python":
            cmd = ["python", "-m", "pytest", test_file, "-x", "-q", "--tb=no", "--no-header"]
        elif language in ("javascript", "typescript"):
            cmd = ["npx", "jest", test_file, "--silent"]
        elif language == "java":
            cmd = ["mvn", "test", "-q"]
        else:
            return True  # 无法验证，视为 survived

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=max(timeout, 5))
            # 测试通过（exit 0）= survived；测试失败（非 0）= killed
            return proc.returncode == 0
        except asyncio.TimeoutError:
            return True  # 超时视为 survived
        except FileNotFoundError:
            return True  # 测试工具不可用

    finally:
        # 恢复原始源码
        try:
            _shutil.copy2(backup_path, original_source)
            os.unlink(backup_path)
        except Exception:
            pass


def _error_result(msg: str) -> dict:
    return {
        "killed": 0, "survived": 0, "total": 0,
        "mutation_score": 0, "threshold_met": False,
        "status": "error", "error": msg, "tool": "none",
    }
