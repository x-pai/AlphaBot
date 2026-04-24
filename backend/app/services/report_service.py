from typing import Dict, Any, List, Optional
import io
import math
import os
from datetime import datetime

import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings


CHART_PALETTE = {
    "primary": "#0f766e",
    "accent": "#d97706",
    "danger": "#b91c1c",
    "muted": "#475569",
    "grid": "#d7e1ea",
    "up": "#15803d",
    "down": "#dc2626",
}


def _load_pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def register_fonts():
    """注册中文字体。"""
    font_path = os.path.join(settings.BASE_DIR, "fonts", "SourceHanSansSC-Regular.ttf")
    pdfmetrics.registerFont(TTFont("SourceHanSans", font_path))


def ensure_reports_dir():
    """确保 reports 目录存在。"""
    reports_dir = os.path.join(settings.BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    return reports_dir


def _to_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _format_number(value: Any, digits: int = 2, suffix: str = "") -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    return f"{number:.{digits}f}{suffix}"


def _format_percent(value: Any, digits: int = 2) -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    return f"{number:.{digits}f}%"


def _safe_text(value: Any, default: str = "暂无") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _normalize_analysis_entry(symbol: str, analysis: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    analysis = analysis if isinstance(analysis, dict) else {}
    context = context or {}
    price = context.get("price", {})

    return {
        "symbol": symbol,
        "name": context.get("name") or symbol,
        "exchange": context.get("exchange"),
        "summary": analysis.get("summary") or analysis.get("analysis", {}).get("summary") or "暂无分析摘要",
        "sentiment": analysis.get("sentiment") or "neutral",
        "risk_level": analysis.get("riskLevel") or "medium",
        "recommendation": analysis.get("recommendation") or "暂无明确建议",
        "key_points": analysis.get("keyPoints") or [],
        "gs_signal": analysis.get("gs_signal") or "中性",
        "prediction": analysis.get("prediction") or {},
        "indicators": analysis.get("indicators") or context.get("technical_indicators") or {},
        "price_series": context.get("price_series") or [],
        "latest_close": price.get("latest_close"),
        "change": price.get("change"),
        "change_percent": price.get("change_percent"),
        "latest_volume": price.get("latest_volume"),
    }


def generate_analysis_report(
    results: Dict[str, Any],
    errors: Dict[str, str],
    report_contexts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成图文报告所需的数据。"""
    report_contexts = report_contexts or {}
    normalized_analyses = [
        _normalize_analysis_entry(symbol, analysis, report_contexts.get(symbol))
        for symbol, analysis in results.items()
    ]

    sentiment_breakdown = {"positive": 0, "neutral": 0, "negative": 0}
    risk_breakdown = {"low": 0, "medium": 0, "high": 0}
    recommendation_breakdown = {"买入": 0, "卖出": 0, "持有": 0, "观察": 0}

    for item in normalized_analyses:
        sentiment = item["sentiment"] if item["sentiment"] in sentiment_breakdown else "neutral"
        risk = item["risk_level"] if item["risk_level"] in risk_breakdown else "medium"
        sentiment_breakdown[sentiment] += 1
        risk_breakdown[risk] += 1

        recommendation = _safe_text(item["recommendation"], "")
        if "买" in recommendation:
            recommendation_breakdown["买入"] += 1
        elif "卖" in recommendation:
            recommendation_breakdown["卖出"] += 1
        elif "持有" in recommendation:
            recommendation_breakdown["持有"] += 1
        else:
            recommendation_breakdown["观察"] += 1

    return {
        "summary": {
            "total_stocks": len(results) + len(errors),
            "successful_analyses": len(results),
            "failed_analyses": len(errors),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sentiment_breakdown": sentiment_breakdown,
            "risk_breakdown": risk_breakdown,
            "recommendation_breakdown": recommendation_breakdown,
        },
        "analyses": normalized_analyses,
        "errors": errors,
    }


def _build_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="SourceHanSans",
            fontSize=26,
            leading=32,
            textColor=colors.HexColor("#0f172a"),
            alignment=1,
            spaceAfter=14,
        ),
        "subtitle": ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#475569"),
            alignment=1,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading1"],
            fontName="SourceHanSans",
            fontSize=18,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=6,
            spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            name="SubSectionHeading",
            parent=styles["Heading2"],
            fontName="SourceHanSans",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=2,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            name="BodyCN",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#1f2937"),
        ),
        "small": ParagraphStyle(
            name="SmallCN",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#64748b"),
        ),
        "badge": ParagraphStyle(
            name="BadgeCN",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=9.5,
            leading=12,
            textColor=colors.white,
            alignment=1,
        ),
    }


def _sentiment_color(sentiment: str) -> colors.Color:
    return {
        "positive": colors.HexColor("#15803d"),
        "neutral": colors.HexColor("#64748b"),
        "negative": colors.HexColor("#b91c1c"),
    }.get(sentiment, colors.HexColor("#64748b"))


def _risk_color(risk_level: str) -> colors.Color:
    return {
        "low": colors.HexColor("#15803d"),
        "medium": colors.HexColor("#d97706"),
        "high": colors.HexColor("#b91c1c"),
    }.get(risk_level, colors.HexColor("#64748b"))


def _pill(text: str, background: colors.Color, style: ParagraphStyle) -> Table:
    table = Table([[Paragraph(_safe_text(text), style)]], colWidths=[1.15 * inch], rowHeights=[0.32 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0, background),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _metric_table(rows: List[List[str]], col_widths: List[float]) -> Table:
    table = Table(rows, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, -1), "SourceHanSans"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _chart_image_from_buffer(buffer: io.BytesIO, width: float, height: float) -> Image:
    buffer.seek(0)
    image = Image(buffer, width=width, height=height)
    image.hAlign = "CENTER"
    return image


def _plot_trend_chart(analysis: Dict[str, Any]) -> io.BytesIO:
    plt = _load_pyplot()
    price_series = analysis.get("price_series") or []
    if not price_series:
        fig, ax = plt.subplots(figsize=(7.2, 3.1), dpi=140)
        ax.text(0.5, 0.5, "暂无可用趋势数据", ha="center", va="center", fontsize=12, color=CHART_PALETTE["muted"])
        ax.axis("off")
        buffer = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        plt.close(fig)
        return buffer

    closes = [_to_float(item.get("close")) for item in price_series]
    labels = [item.get("date", "")[5:] for item in price_series]
    volumes = [_to_float(item.get("volume")) or 0 for item in price_series]

    valid_indices = [idx for idx, close in enumerate(closes) if close is not None]
    x = np.arange(len(price_series))

    fig, ax = plt.subplots(figsize=(7.2, 3.1), dpi=140)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fbfdff")

    if valid_indices:
        close_values = [closes[idx] for idx in valid_indices]
        ax.plot(valid_indices, close_values, color=CHART_PALETTE["primary"], linewidth=2.2, label="收盘价")
        if len(close_values) >= 20:
            ma20 = []
            for i in range(len(closes)):
                window = [c for c in closes[max(0, i - 19): i + 1] if c is not None]
                ma20.append(sum(window) / len(window) if len(window) >= 5 else None)
            ma_idx = [idx for idx, value in enumerate(ma20) if value is not None]
            ma_values = [ma20[idx] for idx in ma_idx]
            ax.plot(ma_idx, ma_values, color=CHART_PALETTE["accent"], linewidth=1.5, linestyle="--", label="MA20")

        latest_close = close_values[-1]
        ax.scatter(valid_indices[-1], latest_close, color=CHART_PALETTE["danger"], s=24, zorder=3)
        ax.annotate(f"{latest_close:.2f}", (valid_indices[-1], latest_close), textcoords="offset points", xytext=(6, 6), fontsize=8)

    ax_volume = ax.twinx()
    ax_volume.bar(x, volumes, color="#cbd5e1", alpha=0.35, width=0.72)
    ax_volume.set_yticks([])
    ax_volume.spines["right"].set_visible(False)

    tick_step = max(1, len(labels) // 6) if labels else 1
    tick_positions = x[::tick_step] if len(x) > 0 else []
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([labels[idx] for idx in tick_positions], fontsize=8, color=CHART_PALETTE["muted"])
    ax.tick_params(axis="y", labelsize=8, colors=CHART_PALETTE["muted"])
    ax.grid(axis="y", color=CHART_PALETTE["grid"], linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.set_title(f"{analysis['symbol']} 价格趋势", fontsize=11, color="#0f172a", pad=10)
    ax.legend(loc="upper left", fontsize=8, frameon=False)

    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return buffer


def _plot_indicator_chart(analysis: Dict[str, Any]) -> io.BytesIO:
    plt = _load_pyplot()
    price_series = analysis.get("price_series") or []
    if not price_series:
        fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=140)
        ax.text(0.5, 0.5, "暂无可用技术指标数据", ha="center", va="center", fontsize=12, color=CHART_PALETTE["muted"])
        ax.axis("off")
        buffer = io.BytesIO()
        plt.tight_layout()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        plt.close(fig)
        return buffer

    closes = np.array([_to_float(item.get("close")) or 0 for item in price_series], dtype=float)
    x = np.arange(len(closes))

    delta = np.diff(closes, prepend=closes[0])
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    window = 14
    rsi_values: List[float] = []
    for idx in range(len(closes)):
        start = max(0, idx - window + 1)
        avg_gain = gains[start: idx + 1].mean() if idx >= 1 else 0.0
        avg_loss = losses[start: idx + 1].mean() if idx >= 1 else 0.0
        if avg_loss == 0:
            rsi_values.append(100.0 if avg_gain > 0 else 50.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

    ema12 = []
    ema26 = []
    multiplier12 = 2 / (12 + 1)
    multiplier26 = 2 / (26 + 1)
    for idx, close in enumerate(closes):
        if idx == 0:
            ema12.append(close)
            ema26.append(close)
        else:
            ema12.append((close - ema12[-1]) * multiplier12 + ema12[-1])
            ema26.append((close - ema26[-1]) * multiplier26 + ema26[-1])

    macd_line = np.array(ema12) - np.array(ema26)
    signal_line = []
    signal_multiplier = 2 / (9 + 1)
    for idx, value in enumerate(macd_line):
        if idx == 0:
            signal_line.append(value)
        else:
            signal_line.append((value - signal_line[-1]) * signal_multiplier + signal_line[-1])
    signal_line = np.array(signal_line)
    histogram = macd_line - signal_line

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 3.6), dpi=140, sharex=True)
    fig.patch.set_facecolor("#ffffff")

    axes[0].set_facecolor("#fbfdff")
    axes[0].plot(x, rsi_values, color=CHART_PALETTE["primary"], linewidth=1.8)
    axes[0].axhline(70, color=CHART_PALETTE["danger"], linestyle="--", linewidth=1)
    axes[0].axhline(30, color=CHART_PALETTE["up"], linestyle="--", linewidth=1)
    axes[0].set_ylim(0, 100)
    axes[0].set_title("RSI", fontsize=10, color="#0f172a", loc="left")
    axes[0].grid(axis="y", color=CHART_PALETTE["grid"], linewidth=0.8)

    axes[1].set_facecolor("#fbfdff")
    axes[1].plot(x, macd_line, color=CHART_PALETTE["primary"], linewidth=1.6, label="MACD")
    axes[1].plot(x, signal_line, color=CHART_PALETTE["accent"], linewidth=1.2, label="Signal")
    bar_colors = [CHART_PALETTE["up"] if value >= 0 else CHART_PALETTE["down"] for value in histogram]
    axes[1].bar(x, histogram, color=bar_colors, alpha=0.5, width=0.7)
    axes[1].axhline(0, color="#94a3b8", linewidth=1)
    axes[1].set_title("MACD", fontsize=10, color="#0f172a", loc="left")
    axes[1].legend(loc="upper left", fontsize=8, frameon=False)
    axes[1].grid(axis="y", color=CHART_PALETTE["grid"], linewidth=0.8)

    tick_step = max(1, len(price_series) // 6) if price_series else 1
    labels = [item.get("date", "")[5:] for item in price_series]
    tick_positions = x[::tick_step] if len(x) > 0 else []
    axes[1].set_xticks(tick_positions)
    axes[1].set_xticklabels([labels[idx] for idx in tick_positions], fontsize=8, color=CHART_PALETTE["muted"])

    for ax in axes:
        ax.tick_params(axis="y", labelsize=8, colors=CHART_PALETTE["muted"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")

    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return buffer


def _summary_overview_table(summary: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    sentiment = summary["sentiment_breakdown"]
    risk = summary["risk_breakdown"]
    recommendation = summary["recommendation_breakdown"]
    rows = [
        ["指标", "数值", "补充说明"],
        ["分析股票", str(summary["total_stocks"]), "本次批量任务覆盖的全部标的"],
        ["成功完成", str(summary["successful_analyses"]), "成功生成分析与报告卡片的股票数"],
        ["失败数", str(summary["failed_analyses"]), "获取行情、分析或出图失败的股票数"],
        ["情绪分布", f"正面 {sentiment['positive']} / 中性 {sentiment['neutral']} / 负面 {sentiment['negative']}", "来自各股票分析结论"],
        ["风险分布", f"低 {risk['low']} / 中 {risk['medium']} / 高 {risk['high']}", "综合风险等级统计"],
        ["建议分布", f"买入 {recommendation['买入']} / 卖出 {recommendation['卖出']} / 持有 {recommendation['持有']} / 观察 {recommendation['观察']}", "按建议文案关键词归类"],
    ]
    return _metric_table(rows, [1.15 * inch, 2.2 * inch, 3.35 * inch])


def _build_cover_page(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    summary = report_data["summary"]
    cover_metrics = Table(
        [
            [
                Paragraph("<b>批量股票时间序列分析报告</b>", styles["title"]),
            ],
            [
                Paragraph(f"生成时间：{summary['generated_at']}", styles["subtitle"]),
            ],
            [
                Paragraph(
                    "本报告聚合了价格趋势、技术指标和批量分析结论，帮助快速比较多只股票的风险、情绪和建议方向。",
                    styles["body"],
                ),
            ],
        ],
        colWidths=[6.7 * inch],
    )
    cover_metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
    ]))

    summary_cards = Table(
        [[
            Paragraph(f"<b>{summary['successful_analyses']}</b><br/>成功分析", styles["subtitle"]),
            Paragraph(f"<b>{summary['failed_analyses']}</b><br/>失败/异常", styles["subtitle"]),
            Paragraph(f"<b>{summary['risk_breakdown']['high']}</b><br/>高风险标的", styles["subtitle"]),
        ]],
        colWidths=[2.1 * inch, 2.1 * inch, 2.1 * inch],
        rowHeights=[0.95 * inch],
    )
    summary_cards.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "SourceHanSans"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))

    return [Spacer(1, 0.6 * inch), cover_metrics, Spacer(1, 0.35 * inch), summary_cards, PageBreak()]


def _build_summary_page(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    elements: List[Any] = [
        Paragraph("摘要页", styles["section"]),
        Paragraph("这一页用于快速判断本次批量分析的整体面貌，适合先看全局，再按个股深入。", styles["body"]),
        Spacer(1, 0.14 * inch),
        _summary_overview_table(report_data["summary"], styles),
        Spacer(1, 0.22 * inch),
    ]

    analyses = report_data["analyses"]
    rows = [["股票", "最新价", "涨跌幅", "情绪", "风险", "GS信号"]]
    for item in analyses[:10]:
        rows.append([
            f"{item['name']} ({item['symbol']})",
            _format_number(item["latest_close"]),
            _format_percent(item["change_percent"]),
            _safe_text(item["sentiment"], "neutral"),
            _safe_text(item["risk_level"], "medium"),
            _safe_text(item["gs_signal"], "中性"),
        ])
    elements.append(Paragraph("个股一览", styles["subsection"]))
    elements.append(_metric_table(rows, [2.2 * inch, 0.85 * inch, 0.95 * inch, 0.85 * inch, 0.85 * inch, 1.0 * inch]))
    elements.append(PageBreak())
    return elements


def _build_stock_section(item: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    elements: List[Any] = [
        Paragraph(f"{item['name']}  {item['symbol']}", styles["section"]),
        Paragraph(_safe_text(item["summary"]), styles["body"]),
        Spacer(1, 0.12 * inch),
    ]

    meta_table = Table(
        [[
            _pill(f"情绪：{_safe_text(item['sentiment'])}", _sentiment_color(item["sentiment"]), styles["badge"]),
            _pill(f"风险：{_safe_text(item['risk_level'])}", _risk_color(item["risk_level"]), styles["badge"]),
            _pill(f"GS信号：{_safe_text(item['gs_signal'])}", colors.HexColor("#0f172a"), styles["badge"]),
        ]],
        colWidths=[1.35 * inch, 1.35 * inch, 1.45 * inch],
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 0.12 * inch))

    metrics = _metric_table(
        [
            ["指标", "值", "指标", "值"],
            ["最新收盘", _format_number(item["latest_close"]), "涨跌幅", _format_percent(item["change_percent"])],
            ["成交量", _format_number(item["latest_volume"], 0), "RSI", _format_number(item["indicators"].get("RSI"))],
            ["MACD", _format_number(item["indicators"].get("MACD")), "波动率", _format_number(item["indicators"].get("Volatility"))],
            ["SMA20", _format_number(item["indicators"].get("SMA_20")), "SMA200", _format_number(item["indicators"].get("SMA_200"))],
        ],
        [1.05 * inch, 1.1 * inch, 1.05 * inch, 1.1 * inch],
    )

    trend_image = _chart_image_from_buffer(_plot_trend_chart(item), width=6.2 * inch, height=2.55 * inch)
    indicator_image = _chart_image_from_buffer(_plot_indicator_chart(item), width=6.2 * inch, height=3.0 * inch)

    key_points = item["key_points"] or []
    if key_points:
        bullets = "<br/>".join([f"• {_safe_text(point)}" for point in key_points[:6]])
    else:
        bullets = "• 暂无关键要点"

    prediction = item["prediction"] or {}
    supports = " / ".join([_format_number(level) for level in prediction.get("support_levels", [])[:2]]) or "N/A"
    resistances = " / ".join([_format_number(level) for level in prediction.get("resistance_levels", [])[:2]]) or "N/A"
    forecast = prediction.get("price_trend", [])[:3]
    forecast_text = "；".join([f"D{point.get('day')}: {_format_number(point.get('predicted_price'))}" for point in forecast]) or "N/A"

    insight_table = _metric_table(
        [
            ["维度", "内容"],
            ["投资建议", Paragraph(_safe_text(item["recommendation"]), styles["body"])],
            ["关键要点", Paragraph(bullets, styles["body"])],
            ["支撑位", supports],
            ["阻力位", resistances],
            ["短期预测", forecast_text],
        ],
        [1.0 * inch, 5.2 * inch],
    )

    elements.extend([
        metrics,
        Spacer(1, 0.18 * inch),
        trend_image,
        Spacer(1, 0.12 * inch),
        indicator_image,
        Spacer(1, 0.15 * inch),
        insight_table,
        PageBreak(),
    ])
    return elements


def _build_conclusion_page(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    analyses = report_data["analyses"]
    summary = report_data["summary"]

    high_risk = [item["symbol"] for item in analyses if item["risk_level"] == "high"]
    positive = [item["symbol"] for item in analyses if item["sentiment"] == "positive"]
    gs_buy = [item["symbol"] for item in analyses if item["gs_signal"] == "买入"]

    conclusion_text = (
        f"本次批量分析共覆盖 {summary['total_stocks']} 个标的，其中成功 {summary['successful_analyses']} 个、失败 {summary['failed_analyses']} 个。"
        f" 情绪偏正面的标的主要有：{('、'.join(positive[:5]) if positive else '暂无明显偏正面标的')}。"
        f" GS 信号显示偏买入的标的主要有：{('、'.join(gs_buy[:5]) if gs_buy else '暂无明确买入信号')}。"
        f" 需要重点关注风险的标的有：{('、'.join(high_risk[:5]) if high_risk else '暂无高风险标的')}。"
    )

    elements: List[Any] = [
        Paragraph("结论页", styles["section"]),
        Paragraph(conclusion_text, styles["body"]),
        Spacer(1, 0.18 * inch),
    ]

    if report_data["errors"]:
        error_rows = [["股票", "失败原因"]]
        for symbol, error in report_data["errors"].items():
            error_rows.append([symbol, _safe_text(error)])
        elements.extend([
            Paragraph("异常与失败明细", styles["subsection"]),
            _metric_table(error_rows, [1.1 * inch, 5.1 * inch]),
        ])

    return elements


def save_report_to_pdf(report_data: Dict[str, Any], output_path: str):
    """将图文报告保存为 PDF 文件。"""
    ensure_reports_dir()
    register_fonts()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = _build_styles()

    elements: List[Any] = []
    elements.extend(_build_cover_page(report_data, styles))
    elements.extend(_build_summary_page(report_data, styles))

    for item in report_data["analyses"]:
        elements.extend(_build_stock_section(item, styles))

    elements.extend(_build_conclusion_page(report_data, styles))

    doc.build(elements)


def get_report_path(task_id: str) -> str:
    """获取报告文件路径。"""
    reports_dir = ensure_reports_dir()
    return os.path.join(reports_dir, f"time_series_analysis_{task_id}.pdf")
