"""代码综合测试 API — 分析 → 生成 → 执行 → 报告 一键流水线"""

import logging
import time
import os
import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.safety.auth import get_current_user

logger = logging.getLogger("testforge")

router = APIRouter()


class CodeTestRequest(BaseModel):
    """代码综合测试请求"""
    code: str                           # 源代码
    language: str = "python"            # 编程语言
    function_name: str = ""             # 重点函数名（可选）
    run_security_scan: bool = True      # 是否安全扫描
    timeout: int = 60                   # 执行超时


class CodeTestResult(BaseModel):
    """代码综合测试结果"""
    status: str = ""                    # completed / error
    # 分析结果
    analysis: dict = {}
    # 生成结果
    generated_test_count: int = 0
    test_cases: list = []
    # 执行结果
    execution: dict = {}
    # 安全扫描
    security: dict = {}
    # 汇总
    summary: dict = {}
    duration_ms: int = 0
    error: str = ""


class ProjectTestRequest(BaseModel):
    """项目文件夹综合测试请求"""
    folder_path: str
    language: str = "python"
    timeout: int = 120


class FileTestItem(BaseModel):
    """单个文件的测试结果"""
    filename: str
    filepath: str
    status: str = "pending"
    analysis: dict = {}
    generated_test_count: int = 0
    execution: dict = {}
    security: dict = {}
    summary: dict = {}
    duration_ms: int = 0
    error: str = ""


class ProjectTestResult(BaseModel):
    """项目文件夹测试聚合结果"""
    status: str = ""
    total_files: int = 0
    files: list = []
    error: str = ""

@router.post("/comprehensive-test", response_model=CodeTestResult)
async def comprehensive_code_test(req: CodeTestRequest, user: str = Depends(get_current_user)):
    """代码综合测试 — 一键完成分析→生成→执行→报告

    流程:
    1. 静态分析：提取函数/类/复杂度
    2. AI 生成：三通道（DashScope/LiteLLM/Ollama）生成 pytest 测试代码
    3. 真实验证：用 pytest 真实执行生成的测试，解析通过/失败
    4. 安全扫描：检测危险代码和密钥泄露
    5. 汇总报告
    """
    start = time.time()
    result = CodeTestResult()

    try:
        # Step 1: 静态分析
        logger.info("[1/4] 静态分析...")
        from backend.analyzer import analyze_code as do_analyze
        result.analysis = do_analyze(req.code, req.language)
        logger.info("静态分析完成: %d 个函数", result.analysis.get("function_count", 0))

        # Step 2: AI 生成测试用例
        # Step 2: AI 生成测试用例
        logger.info("[2/4] AI 生成测试用例...")
        from backend.generator.router import route_generation
        from backend.core.agent import _cases_to_pytest_code
        test_cases = []
        try:
            test_cases = await route_generation(
                req.code,
                req.language,
                req.function_name,
            )
            result.generated_test_count = len(test_cases)
            result.test_cases = [
                {"name": tc.name, "type": tc.type.value, "steps": len(tc.steps)}
                for tc in test_cases
            ]
            logger.info("生成 %d 个测试用例", len(test_cases))
        except Exception as gen_err:
            logger.warning("AI 生成失败: %s", gen_err)
            result.generated_test_count = 0
            result.test_cases = []
            test_cases = []

        # Step 3: 执行测试
        if test_cases:
            logger.info("[3/4] 执行测试...")
            from backend.executors.code_executor import execute_pytest_via_code
            test_code = _cases_to_pytest_code(test_cases, req.code)
            result.execution = await execute_pytest_via_code(test_code, timeout=req.timeout)
            logger.info("测试执行完成: %d passed, %d failed",
                         result.execution.get("passed", 0),
                         result.execution.get("failed", 0))
        else:
            result.execution = {"total": 0, "passed": 0, "failed": 0, "skipped": True, "note": "未配置 AI API"}
            logger.info("[3/4] 跳过执行（未配置 AI）")

        # Step 4: 安全扫描
        if req.run_security_scan:
            logger.info("[4/4] 安全扫描...")
            from backend.safety.secret_scan import scan_all
            result.security = scan_all(req.code)

        # 汇总
        execution = result.execution
        total = execution.get("total", 0)
        passed = execution.get("passed", 0)
        failed = execution.get("failed", 0)
        pass_rate = round(passed / total * 100, 1) if total > 0 else 0

        score = 100
        if failed > 0:
            score -= failed * 10
        if result.analysis.get("smells", 0) > 3:
            score -= 10
        if result.security.get("risks_found", 0) > 0:
            score -= 15
        score = max(0, min(100, score))

        result.summary = {
            "analysis": {
                "functions": result.analysis.get("function_count", 0),
                "classes": result.analysis.get("class_count", 0),
                "complexity": result.analysis.get("complexity", "unknown"),
            },
            "tests": {
                "generated": result.generated_test_count,
                "executed": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": pass_rate,
            },
            "security": {
                "risks_found": result.security.get("risks_found", 0),
            },
            "overall_score": score,
            "language": req.language,
        }
        result.status = "completed"

    except Exception as e:
        logger.error("代码综合测试失败: %s", e)
        result.status = "error"
        result.error = str(e)

    result.duration_ms = int((time.time() - start) * 1000)
    return result


@router.post("/generate-only")
async def generate_tests_only(req: CodeTestRequest, user: str = Depends(get_current_user)):
    """仅生成测试用例（不执行）

    返回生成的 pytest 代码，适合手动审查后再执行。
    """
    from backend.generator.router import route_generation
    from backend.core.agent import _cases_to_pytest_code

    test_cases = await route_generation(req.code, req.language, req.function_name)
    test_code = _cases_to_pytest_code(test_cases, req.code)

    return {
        "count": len(test_cases),
        "test_cases": [
            {"name": tc.name, "type": tc.type.value, "steps": len(tc.steps)}
            for tc in test_cases
        ],
        "pytest_code": test_code,
        "language": req.language,
    }


@router.post("/execute-only")
async def execute_tests_only(req: CodeTestRequest, user: str = Depends(get_current_user)):
    """仅执行传入的代码（直接跑 pytest）

    与 /generate-only 配合使用：先生成 → 审查 → 执行。
    """
    from backend.executors.code_executor import execute_pytest_via_code
    result = await execute_pytest_via_code(req.code, timeout=req.timeout)
    return result


@router.post("/project-test", response_model=ProjectTestResult)
async def project_code_test(req: ProjectTestRequest, user: str = Depends(get_current_user)):
    """项目文件夹综合测试"""
    start_total = time.time()
    folder = os.path.abspath(req.folder_path)
    logger.info("[PROJECT-TEST] Received folder_path: %s", req.folder_path)
    logger.info("[PROJECT-TEST] Resolved path: %s", folder)
    logger.info("[PROJECT-TEST] Is directory: %s", os.path.isdir(folder))
    if not os.path.isdir(folder):
        return ProjectTestResult(status="error", error=f"目录不存在: {folder}")

    EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", "venv", ".venv", "dist", "build", ".tox", ".pytest_cache", ".mypy_cache"}
    py_files = []
    for root, dirs, filenames in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    if not py_files:
        return ProjectTestResult(status="completed", total_files=0, files=[])

    result = ProjectTestResult(status="running", total_files=len(py_files))

    from backend.analyzer import analyze_code as do_analyze
    from backend.generator.router import route_generation
    from backend.core.agent import _cases_to_pytest_code
    from backend.executors.code_executor import execute_pytest_via_code
    from backend.safety.secret_scan import scan_all

    for filepath in py_files:
        item = FileTestItem(filename=os.path.relpath(filepath, folder), filepath=filepath, status="running")
        if time.time() - start_total > req.timeout * 0.8:
            item.status = "error"
            item.error = "项目总超时，跳过剩余文件"
            result.files.append(item)
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            if len(code.strip()) < 10:
                item.status = "completed"
                item.summary = {"note": "文件为空或过短，已跳过"}
                result.files.append(item)
                continue

            file_start = time.time()

            # Step 1: 静态分析
            item.analysis = do_analyze(code, req.language)

            # 2. AI 生成
            test_cases = []
            try:
                test_cases = await route_generation(code, req.language, "")
                item.generated_test_count = len(test_cases)
            except Exception as gen_err:
                logger.warning("AI gen failed: %s", gen_err)
                item.generated_test_count = 0

            # 3. 执行
            if test_cases:
                test_code = _cases_to_pytest_code(test_cases, code)
                item.execution = await execute_pytest_via_code(test_code, timeout=30)
            else:
                item.execution = {"total": 0, "passed": 0, "failed": 0, "skipped": True, "note": "未配置 AI"}

            # 4. 安全扫描
            item.security = scan_all(code)

            total = item.execution.get("total", 0)
            passed = item.execution.get("passed", 0)
            failed = item.execution.get("failed", 0)
            pass_rate = round(passed / total * 100, 1) if total > 0 else 0
            item.summary = {"functions": item.analysis.get("function_count", 0), "test_count": item.generated_test_count, "passed": passed, "failed": failed, "pass_rate": pass_rate, "risks": item.security.get("risks_found", 0)}
            item.status = "completed"
            item.duration_ms = int((time.time() - file_start) * 1000)
        except Exception as e:
            item.status = "error"
            item.error = str(e)
        result.files.append(item)

    result.status = "completed"
    return result
