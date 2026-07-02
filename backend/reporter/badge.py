"""覆盖率徽章生成 — SVG 格式，可嵌入 README / CI 状态

文档第二节 L6 报告与集成层：badge 生成。
"""

import logging

logger = logging.getLogger("testforge")


# 徽章颜色阶梯（按覆盖率/分数）
def _color_for_score(score: float) -> str:
    if score >= 90:
        return "#4c1"        # brightgreen
    if score >= 80:
        return "#97ca00"     # green
    if score >= 70:
        return "#dfb317"     # yellowgreen
    if score >= 60:
        return "#fe7d37"     # orange
    return "#e05d44"         # red


def generate_coverage_badge(
    coverage_pct: float,
    label: str = "coverage",
    output_path: str = "",
) -> str:
    """生成覆盖率 SVG 徽章

    Args:
        coverage_pct: 覆盖率百分比
        label: 徽章左侧标签
        output_path: 写入文件路径；为空则仅返回 SVG 字符串

    Returns:
        SVG 字符串
    """
    score = round(coverage_pct, 1)
    color = _color_for_score(coverage_pct)
    return _render_badge(label, f"{score}%", color, output_path)


def generate_score_badge(
    score: float,
    label: str = "health",
    output_path: str = "",
) -> str:
    """生成健康度/评分 SVG 徽章"""
    score_int = int(round(score))
    color = _color_for_score(score)
    return _render_badge(label, f"{score_int}/100", color, output_path)


def generate_pass_rate_badge(
    passed: int,
    total: int,
    output_path: str = "",
) -> str:
    """生成通过率徽章"""
    rate = (passed / total * 100) if total else 0
    color = _color_for_score(rate)
    return _render_badge("tests", f"{passed}/{total} passed", color, output_path)


def _render_badge(label: str, value: str, color: str, output_path: str) -> str:
    """渲染标准 SVG 徽章（shields.io 风格）"""
    # 估算文本宽度（粗略）
    label_width = max(len(label) * 7 + 10, 30)
    value_width = max(len(value) * 7 + 10, 30)
    total_width = label_width + value_width

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
<linearGradient id="b" x2="0" y2="100%">
<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
<stop offset="1" stop-opacity=".1"/>
</linearGradient>
<mask id="a">
<rect width="{total_width}" height="20" rx="3" fill="#fff"/>
</mask>
<g mask="url(#a)">
<path fill="#555" d="M0 0h{label_width}v20H0z"/>
<path fill="{color}" d="M{label_width} 0h{value_width}v20H{label_width}z"/>
<path fill="url(#b)" d="M0 0h{total_width}v20H0z"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
<text x="{label_width // 2}" y="15">{label}</text>
<text x="{label_width + value_width // 2}" y="15">{value}</text>
</g>
</svg>"""

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(svg)
            logger.info("徽章已写入: %s", output_path)
        except OSError as e:
            logger.error("写入徽章失败: %s", e)

    return svg
