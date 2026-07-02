"""属性测试生成器 — Hypothesis / fast-check"""

from backend.models import TestCase, TestStep, Assertion, AssertionType, StepType, TestType


async def generate_property_tests(source_code: str, language: str = "python") -> list[TestCase]:
    """为数据处理函数生成属性测试"""

    # 识别适合属性测试的函数模式
    patterns = _detect_patterns(source_code, language)

    cases = []
    for p in patterns:
        if p["type"] == "roundtrip":
            cases.append(_roundtrip_test(p))
        elif p["type"] == "idempotent":
            cases.append(_idempotent_test(p))
        elif p["type"] == "commutative":
            cases.append(_commutative_test(p))
        elif p["type"] == "invariant":
            cases.append(_invariant_test(p))

    return cases


def _detect_patterns(source: str, language: str) -> list[dict]:
    """检测适合属性测试的代码模式"""
    patterns = []

    # 编解码对: encode/decode, serialize/deserialize, marshal/unmarshal
    pairs = [
        ("encode", "decode"), ("serialize", "deserialize"),
        ("marshal", "unmarshal"), ("dump", "load"),
        ("to_json", "from_json"), ("to_dict", "from_dict"),
    ]
    for a, b in pairs:
        if a in source.lower() and b in source.lower():
            patterns.append({"type": "roundtrip", "func": a, "inverse": b})

    # 幂等操作: PUT相同数据, set重复值
    if any(w in source.lower() for w in ["put", "set", "update", "upsert"]):
        patterns.append({"type": "idempotent", "func": "update"})

    # 交换律: add, multiply, merge
    if any(w in source.lower() for w in ["add", "sum", "merge", "concat"]):
        patterns.append({"type": "commutative", "func": "merge"})

    return patterns


def _roundtrip_test(p: dict) -> TestCase:
    return TestCase(
        name=f"属性测试: {p['func']}/{p['inverse']} 往返不变式",
        type=TestType.UNIT,
        created_by="ai",
        tags=["property", "roundtrip"],
        steps=[TestStep(
            id="step_prop_1",
            type=StepType.CODE_EXEC,
            description=f"验证 {p['func']}({p['inverse']}(x)) == x 对于任意输入x",
            assertions=[
                Assertion(type=AssertionType.EQUALS, expected="原值 == 往返后值"),
            ],
        )],
    )


def _idempotent_test(p: dict) -> TestCase:
    return TestCase(
        name=f"属性测试: {p['func']} 幂等性",
        type=TestType.UNIT,
        created_by="ai",
        tags=["property", "idempotent"],
        steps=[TestStep(
            id="step_prop_2",
            type=StepType.CODE_EXEC,
            description=f"验证 f(f(x)) == f(x)",
            assertions=[
                Assertion(type=AssertionType.EQUALS, expected="f(f(x)) == f(x)"),
            ],
        )],
    )


def _commutative_test(p: dict) -> TestCase:
    return TestCase(
        name=f"属性测试: {p['func']} 交换律",
        type=TestType.UNIT,
        created_by="ai",
        tags=["property", "commutative"],
        steps=[TestStep(
            id="step_prop_3",
            type=StepType.CODE_EXEC,
            description="验证 f(a, b) == f(b, a)",
            assertions=[
                Assertion(type=AssertionType.EQUALS, expected="f(a,b) == f(b,a)"),
            ],
        )],
    )


def _invariant_test(p: dict) -> TestCase:
    return TestCase(
        name=f"属性测试: {p.get('func', 'data')} 不变量",
        type=TestType.UNIT,
        created_by="ai",
        tags=["property", "invariant"],
        steps=[TestStep(
            id="step_prop_4",
            type=StepType.CODE_EXEC,
            description="验证输出长度/类型/结构不随输入变化",
            assertions=[
                Assertion(type=AssertionType.EQUALS, expected="不变量保持不变"),
            ],
        )],
    )
