from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.policy_service import COVERAGE_META, list_policies

COVERAGE_ORDER = ["life", "medical", "accident", "cancer", "critical", "ltc"]
COVERAGE_TARGETS = {
    "life": 1000,
    "medical": 20,
    "accident": 500,
    "cancer": 300,
    "critical": 200,
    "ltc": 5,
}


def build_policy_report_pdf(
    profile_id: str,
    owner_name: str = "",
    age: int | None = None,
    occupation: str = "",
    monthly_income: float | None = None,
) -> bytes:
    portfolio = list_policies(profile_id)
    profile = portfolio.get("profile") or {}
    policies = portfolio.get("policies") or []
    summary = portfolio.get("summary") or {}
    report_owner = owner_name or profile.get("owner_name") or "保單持有人"
    report = build_report_model(report_owner, age, occupation, monthly_income, policies, summary)

    buffer = BytesIO()
    register_fonts()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title=f"{report_owner} 保單健診報告",
    )
    styles = build_styles()
    story: list[Any] = []

    story.extend(build_cover(report, styles))
    story.append(PageBreak())
    story.extend(build_coverage_section(report, styles))
    story.append(Spacer(1, 8))
    story.extend(build_policy_table(report, styles))
    story.append(Spacer(1, 8))
    story.extend(build_completeness_section(report, styles))
    story.append(Spacer(1, 8))
    story.extend(build_advice_section(report, styles))

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()


def build_report_model(
    owner_name: str,
    age: int | None,
    occupation: str,
    monthly_income: float | None,
    policies: list[dict],
    summary: dict,
) -> dict:
    coverage = summary.get("coverage") or {}
    checks = []
    for key in COVERAGE_ORDER:
        current = float(coverage.get(key) or 0)
        target = COVERAGE_TARGETS[key]
        gap = max(target - current, 0)
        checks.append(
            {
                "key": key,
                "label": COVERAGE_META[key]["label"],
                "unit": COVERAGE_META[key]["unit"],
                "current": current,
                "target": target,
                "gap": gap,
                "status": "足夠" if gap <= 0 else "有缺口" if current > 0 else "未建立",
            }
        )

    incomplete = [
        policy
        for policy in policies
        if (policy.get("completeness") or {}).get("missing_count", 0) > 0
    ]
    score = calculate_report_score(checks, int(summary.get("incomplete") or 0))
    priorities = sorted([check for check in checks if check["gap"] > 0], key=lambda item: item["gap"], reverse=True)[:3]

    return {
        "owner_name": owner_name,
        "age": age,
        "occupation": occupation,
        "monthly_income": monthly_income,
        "date": datetime.now().strftime("%Y/%m/%d"),
        "policies": policies,
        "summary": summary,
        "checks": checks,
        "incomplete": incomplete,
        "score": score,
        "priorities": priorities,
    }


def calculate_report_score(checks: list[dict], incomplete_count: int) -> int:
    if not checks:
        return 0
    total = 0
    for check in checks:
        if check["gap"] <= 0:
            total += 100
        elif check["current"] > 0:
            total += max(35, round((check["current"] / check["target"]) * 100))
    return max(0, min(100, round(total / len(checks)) - incomplete_count * 4))


def register_fonts() -> None:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    except Exception:
        pass


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleZH",
            parent=base["Title"],
            fontName="STSong-Light",
            fontSize=26,
            leading=34,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f172a"),
        ),
        "h1": ParagraphStyle(
            "H1ZH",
            parent=base["Heading1"],
            fontName="STSong-Light",
            fontSize=16,
            leading=22,
            spaceAfter=8,
            textColor=colors.HexColor("#0f172a"),
        ),
        "h2": ParagraphStyle(
            "H2ZH",
            parent=base["Heading2"],
            fontName="STSong-Light",
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#334155"),
        ),
        "body": ParagraphStyle(
            "BodyZH",
            parent=base["BodyText"],
            fontName="STSong-Light",
            fontSize=9.5,
            leading=15,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#334155"),
        ),
        "small": ParagraphStyle(
            "SmallZH",
            parent=base["BodyText"],
            fontName="STSong-Light",
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#64748b"),
        ),
        "score": ParagraphStyle(
            "ScoreZH",
            parent=base["Title"],
            fontName="STSong-Light",
            fontSize=34,
            leading=40,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
    }


def build_cover(report: dict, styles: dict[str, ParagraphStyle]) -> list[Any]:
    summary = report["summary"]
    return [
        Spacer(1, 24),
        Paragraph("保單健診報告", styles["title"]),
        Spacer(1, 8),
        Paragraph("Insurance Policy Review", styles["h2"]),
        Spacer(1, 20),
        build_score_card(report, styles),
        Spacer(1, 18),
        build_key_value_table(
            [
                ["客戶姓名", report["owner_name"], "報告日期", report["date"]],
                ["年齡", f"{report['age']} 歲" if report["age"] else "待補", "職業", report["occupation"] or "待補"],
                ["保單張數", f"{summary.get('policyCount', 0)} 張", "保險公司", f"{summary.get('companyCount', 0)} 家"],
                ["年繳保費", format_money(summary.get("premium", 0)), "資料完整度", f"{summary.get('averageCompleteness', 0)}%"],
            ]
        ),
        Spacer(1, 16),
        Paragraph("本報告依已輸入之既有保單資料統整保障現況、需求缺口、待補資料與後續理賠服務前置條件。", styles["body"]),
        Spacer(1, 10),
        Paragraph("提醒：若保單號碼、保額、條款來源或生效日尚未補齊，健診結果需待資料完整後再次確認。", styles["small"]),
    ]


def build_score_card(report: dict, styles: dict[str, ParagraphStyle]) -> Table:
    score = report["score"]
    label = "資料可用" if score >= 80 else "需補強" if score >= 50 else "資料不足"
    table = Table(
        [[Paragraph(str(score), styles["score"]), Paragraph(f"健診分數<br/>{label}", styles["h1"])]],
        colWidths=[42 * mm, 92 * mm],
        rowHeights=[34 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#0f766e")),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("LEFTPADDING", (1, 0), (1, 0), 16),
            ]
        )
    )
    return table


def build_coverage_section(report: dict, styles: dict[str, ParagraphStyle]) -> list[Any]:
    rows = [["保障項目", "現有保障", "建議基準", "缺口", "狀態"]]
    for check in report["checks"]:
        rows.append(
            [
                check["label"],
                format_coverage(check),
                format_number(check["target"], check["unit"]),
                "無缺口" if check["gap"] <= 0 else format_number(check["gap"], check["unit"]),
                check["status"],
            ]
        )
    table = Table(rows, colWidths=[34 * mm, 34 * mm, 34 * mm, 34 * mm, 28 * mm], repeatRows=1)
    table.setStyle(base_table_style())
    return [Paragraph("一、六大保障缺口分析", styles["h1"]), table]


def build_policy_table(report: dict, styles: dict[str, ParagraphStyle]) -> list[Any]:
    rows = [["保險公司", "保單名稱", "角色", "狀態", "年繳保費", "完整度"]]
    for policy in report["policies"]:
        completeness = policy.get("completeness") or {}
        rows.append(
            [
                safe(policy.get("company_name")),
                safe(policy.get("policy_name")),
                safe(policy.get("role")),
                safe(policy.get("status")),
                format_money(policy.get("annual_premium", 0)),
                f"{completeness.get('score', 0)}%",
            ]
        )
    if len(rows) == 1:
        rows.append(["尚未建立保單資料", "", "", "", "", ""])
    table = Table(rows, colWidths=[28 * mm, 52 * mm, 18 * mm, 22 * mm, 28 * mm, 18 * mm], repeatRows=1)
    table.setStyle(base_table_style())
    return [Paragraph("二、保單明細", styles["h1"]), table]


def build_completeness_section(report: dict, styles: dict[str, ParagraphStyle]) -> list[Any]:
    rows = [["保單", "待補欄位"]]
    for policy in report["incomplete"][:8]:
        missing = "、".join(item["label"] for item in (policy.get("completeness") or {}).get("missing", [])[:8])
        rows.append([safe(policy.get("policy_name")), missing or "待確認"])
    if len(rows) == 1:
        rows.append(["全部保單", "目前無明顯待補欄位"])
    table = Table(rows, colWidths=[58 * mm, 108 * mm], repeatRows=1)
    table.setStyle(base_table_style())
    return [Paragraph("三、保單資料完整度", styles["h1"]), table]


def build_advice_section(report: dict, styles: dict[str, ParagraphStyle]) -> list[Any]:
    items = []
    if report["priorities"]:
        for item in report["priorities"]:
            items.append(f"{item['label']}仍有缺口 {format_number(item['gap'], item['unit'])}，建議優先確認家庭責任、預算與是否已有其他保障。")
    else:
        items.append("六大保障未見明顯缺口，下一步建議檢查條款限制、續保條件、實支實付限制與重複投保。")
    if report["incomplete"]:
        items.append(f"目前有 {len(report['incomplete'])} 張保單資料待補，正式建議前應先補齊缺漏欄位。")
    items.append("理賠服務需搭配診斷證明、收據與醫療明細，並以保險公司實際核定為準。")

    rows = [[Paragraph(advice, styles["body"])] for advice in items]
    table = Table(rows, colWidths=[166 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#fde68a")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#fde68a")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return [
        Paragraph("四、顧問建議與後續服務", styles["h1"]),
        table,
        Spacer(1, 10),
        Paragraph("本報告為依系統已輸入資料產生之初步保單健診，正式規劃仍需由合格業務員確認條款、批註、除外責任、投保規則與客戶最新財務狀況。", styles["small"]),
    ]


def build_key_value_table(rows: list[list[str]]) -> Table:
    table = Table(rows, colWidths=[24 * mm, 58 * mm, 24 * mm, 58 * mm])
    table.setStyle(base_table_style())
    return table


def base_table_style() -> TableStyle:
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def draw_footer(canvas, doc) -> None:
    canvas.saveState()
    try:
        canvas.setFont("STSong-Light", 8)
    except Exception:
        canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(16 * mm, 9 * mm, "AI 保險顧問平台 - 保單健診報告")
    canvas.drawRightString(194 * mm, 9 * mm, f"第 {doc.page} 頁")
    canvas.restoreState()


def format_coverage(check: dict) -> str:
    return format_number(check["current"], check["unit"])


def format_number(value: float, unit: str) -> str:
    if float(value).is_integer():
        display = f"{int(value):,}"
    else:
        display = f"{value:,.1f}"
    return f"{display} {unit}"


def format_money(value: float | int | str | None) -> str:
    return f"NT$ {float(value or 0):,.0f}"


def safe(value: Any) -> str:
    text = str(value or "待補")
    return text[:42]
