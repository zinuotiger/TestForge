"""PDF 报告生成器 — 将测试结果转为 PDF 文档"""

import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册中文字体（使用系统自带字体）
import os
import platform

_FONT_REGISTERED = False

def _ensure_font():
    """注册中文字体，失败则用默认字体"""
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    system = platform.system()
    font_paths = []

    if system == "Windows":
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",     # 黑体
            "C:/Windows/Fonts/simsun.ttc",     # 宋体
        ]
    elif system == "Darwin":  # macOS
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
    else:  # Linux
        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("TestForgeFont", path))
                _FONT_REGISTERED = True
                return
            except Exception:
                continue

    # 全部失败，用默认（中文可能显示为方块）
    _FONT_REGISTERED = True


def generate_test_report_pdf(
    api_title: str,
    api_version: str,
    endpoint_count: int,
    test_count: int,
    execution: dict,
    scan_url: str = "",
) -> bytes:
    """生成网站测试报告 PDF

    Returns:
        PDF 文件的字节内容
    """
    _ensure_font()
    font_name = "TestForgeFont" if _FONT_REGISTERED else "Helvetica"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )

    # 样式
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"],
        fontName=font_name, fontSize=20, textColor=colors.HexColor("#0f172a"))
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"],
        fontName=font_name, fontSize=14, textColor=colors.HexColor("#1e3a5f"),
        spaceBefore=12, spaceAfter=6)
    normal_style = ParagraphStyle("Normal", parent=styles["Normal"],
        fontName=font_name, fontSize=10, textColor=colors.HexColor("#333333"))
    small_style = ParagraphStyle("Small", parent=styles["Normal"],
        fontName=font_name, fontSize=8, textColor=colors.HexColor("#666666"))

    elements = []

    # 标题
    elements.append(Paragraph("TestForge 网站测试报告", title_style))
    elements.append(Spacer(1, 6*mm))
    elements.append(Paragraph(
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", small_style
    ))
    if scan_url:
        elements.append(Paragraph(f"扫描目标: {scan_url}", small_style))
    elements.append(Spacer(1, 8*mm))

    # API 信息
    elements.append(Paragraph("API 信息", heading_style))
    api_info = [
        ["API 名称", api_title or "Unknown"],
        ["版本", api_version or "Unknown"],
        ["端点数量", str(endpoint_count)],
        ["生成测试数", str(test_count)],
    ]
    api_table = Table(api_info, colWidths=[40*mm, 120*mm])
    api_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(api_table)
    elements.append(Spacer(1, 6*mm))

    # 执行统计
    if execution:
        elements.append(Paragraph("执行统计", heading_style))
        total = execution.get("total", 0)
        passed = execution.get("passed", 0)
        failed = execution.get("failed", 0)
        duration = execution.get("duration_ms", 0)
        pass_rate = round(passed / total * 100, 1) if total else 0

        stat_data = [
            ["指标", "值"],
            ["总测试数", str(total)],
            ["通过", str(passed)],
            ["失败", str(failed)],
            ["通过率", f"{pass_rate}%"],
            ["耗时", f"{duration} ms"],
        ]
        stat_table = Table(stat_data, colWidths=[40*mm, 120*mm])
        stat_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 6),
            # 通过行绿色，失败行红色
            ("TEXTCOLOR", (1, 2), (1, 2), colors.HexColor("#16a34a")),
            ("TEXTCOLOR", (1, 3), (1, 3), colors.HexColor("#dc2626")),
        ]))
        elements.append(stat_table)
        elements.append(Spacer(1, 6*mm))

        # 测试详情
        elements.append(Paragraph("测试详情", heading_style))
        results = execution.get("results", [])

        if results:
            detail_header = [["#", "方法", "状态码", "结果", "URL", "耗时(ms)"]]
            detail_rows = []
            for i, r in enumerate(results):
                status_icon = "PASS" if r.get("passed") else "FAIL"
                url = r.get("url", "")
                if len(url) > 60:
                    url = url[:57] + "..."
                detail_rows.append([
                    str(i + 1),
                    r.get("method", ""),
                    str(r.get("status", 0)),
                    status_icon,
                    url,
                    str(r.get("duration_ms", 0)),
                ])

            detail_data = detail_header + detail_rows
            detail_table = Table(detail_data, colWidths=[
                8*mm, 18*mm, 15*mm, 15*mm, 85*mm, 20*mm
            ])
            detail_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))

            # 给 PASS/FAIL 行上色
            for i, r in enumerate(results, 1):
                if r.get("passed"):
                    detail_table.setStyle(TableStyle([
                        ("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#16a34a")),
                    ]))
                else:
                    detail_table.setStyle(TableStyle([
                        ("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#dc2626")),
                    ]))

            elements.append(detail_table)
        else:
            elements.append(Paragraph("无测试执行记录", normal_style))

    elements.append(Spacer(1, 10*mm))

    # 页脚
    elements.append(Paragraph(
        "Generated by TestForge — 智能测试平台 | "
        f"{datetime.now().year} TestForge Team",
        small_style
    ))

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
