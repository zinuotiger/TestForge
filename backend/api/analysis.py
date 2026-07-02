"""分析 API — 静态分析 + 覆盖率 + DSL + 集成"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.analyzer import analyze_code, analyze_file
from backend.quality.coverage import collect_coverage
from backend.quality.mutation import run_mutation_tests
from backend.dsl import parse_dsl, validate_dsl
from backend.integrations import check_keploy_available
from backend.safety.auth import get_current_user

router = APIRouter()


class AnalyzeRequest(BaseModel):
    code: str = ""
    language: str = "python"
    filepath: str = ""


@router.post("/static")
async def api_static_analysis(req: AnalyzeRequest):
    """静态代码分析"""
    if req.filepath:
        return analyze_file(req.filepath)
    return analyze_code(req.code, req.language)


@router.post("/coverage")
async def api_coverage(test_path: str = "tests/", source_dir: str = "backend/", user: str = Depends(get_current_user)):
    """收集测试覆盖率"""
    return await collect_coverage(test_path, source_dir)


@router.post("/mutation")
async def api_mutation(source_file: str = "backend/", user: str = Depends(get_current_user)):
    """变异测试"""
    return await run_mutation_tests(source_file)


class DSLRequest(BaseModel):
    dsl: str


@router.post("/dsl/parse")
async def api_dsl_parse(req: DSLRequest):
    """解析 DSL 为 TestCase"""
    try:
        tc = parse_dsl(req.dsl)
        return {"valid": True, "test_case": tc.model_dump()}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.post("/dsl/validate")
async def api_dsl_validate(req: DSLRequest):
    """校验 DSL 语法"""
    return validate_dsl(req.dsl)


@router.get("/integrations/keploy")
async def api_keploy_status():
    """检查 Keploy 集成状态"""
    return await check_keploy_available()
