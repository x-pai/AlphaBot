from typing import Any, Dict, List, Optional
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


THEME = {
    "ink": "#132033",
    "text": "#243447",
    "muted": "#66758a",
    "line": "#d8dee8",
    "panel": "#f6f8fb",
    "panel_alt": "#eef3f8",
    "accent": "#0f766e",
    "accent_soft": "#d9f1ee",
    "gold": "#d97706",
    "gold_soft": "#fdf0da",
    "danger": "#b42318",
    "danger_soft": "#fde7e4",
    "success": "#15803d",
    "success_soft": "#e6f4ea",
}


def _load_pyplot():
    import matplotlib
    from matplotlib import font_manager

    matplotlib.use("Agg")
    font_path = os.path.join(settings.BASE_DIR, "fonts", "SourceHanSansCN-Regular.otf")
    font_manager.fontManager.addfont(font_path)
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    matplotlib.rcParams["font.family"] = font_name
    matplotlib.rcParams["font.sans-serif"] = [font_name]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    return plt


def register_fonts():
    font_path = os.path.join(settings.BASE_DIR, "fonts", "SourceHanSansSC-Regular.ttf")
    pdfmetrics.registerFont(TTFont("SourceHanSans", font_path))


def ensure_reports_dir():
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


def _safe_text(value: Any, default: str = "暂无") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


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


def _extract_recommendation_bucket(text: str) -> str:
    if "买" in text:
        return "买入"
    if "卖" in text:
        return "卖出"
    if "持有" in text:
        return "持有"
    return "观察"


def _score_sentiment(sentiment: str) -> int:
    return {"positive": 2, "neutral": 1, "negative": 0}.get(sentiment, 1)


def _score_risk(risk_level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(risk_level, 1)


def _normalize_analysis_entry(symbol: str, analysis: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    analysis = analysis if isinstance(analysis, dict) else {}
    context = context or {}
    price = context.get("price", {})
    recommendation = analysis.get("recommendation") or "暂无明确建议"
    latest_close = price.get("latest_close")
    change_percent = price.get("change_percent")

    return {
        "symbol": symbol,
        "name": context.get("name") or symbol,
        "exchange": context.get("exchange"),
        "summary": analysis.get("summary") or analysis.get("analysis", {}).get("summary") or "暂无分析摘要",
        "sentiment": analysis.get("sentiment") or "neutral",
        "risk_level": analysis.get("riskLevel") or "medium",
        "recommendation": recommendation,
        "recommendation_bucket": _extract_recommendation_bucket(recommendation),
        "key_points": analysis.get("keyPoints") or [],
        "gs_signal": analysis.get("gs_signal") or "中性",
        "prediction": analysis.get("prediction") or {},
        "indicators": analysis.get("indicators") or context.get("technical_indicators") or {},
        "price_series": context.get("price_series") or [],
        "latest_close": latest_close,
        "change": price.get("change"),
        "change_percent": change_percent,
        "latest_volume": price.get("latest_volume"),
        "conviction_score": (
            _score_sentiment(analysis.get("sentiment") or "neutral") * 35
            - _score_risk(analysis.get("riskLevel") or "medium") * 15
            + (10 if (analysis.get("gs_signal") or "") == "买入" else 0)
            + (5 if change_percent and _to_float(change_percent) and _to_float(change_percent) > 0 else 0)
        ),
    }


def generate_analysis_report(
    results: Dict[str, Any],
    errors: Dict[str, str],
    report_contexts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    report_contexts = report_contexts or {}
    analyses = [
        _normalize_analysis_entry(symbol, analysis, report_contexts.get(symbol))
        for symbol, analysis in results.items()
    ]
    analyses.sort(key=lambda item: item["conviction_score"], reverse=True)

    sentiment_breakdown = {"positive": 0, "neutral": 0, "negative": 0}
    risk_breakdown = {"low": 0, "medium": 0, "high": 0}
    recommendation_breakdown = {"买入": 0, "卖出": 0, "持有": 0, "观察": 0}

    for item in analyses:
        sentiment_breakdown[item["sentiment"]] = sentiment_breakdown.get(item["sentiment"], 0) + 1
        risk_breakdown[item["risk_level"]] = risk_breakdown.get(item["risk_level"], 0) + 1
        recommendation_breakdown[item["recommendation_bucket"]] += 1

    top_focus = analyses[: min(3, len(analyses))]

    return {
        "summary": {
            "total_stocks": len(results) + len(errors),
            "successful_analyses": len(results),
            "failed_analyses": len(errors),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sentiment_breakdown": sentiment_breakdown,
            "risk_breakdown": risk_breakdown,
            "recommendation_breakdown": recommendation_breakdown,
            "top_focus": top_focus,
        },
        "analyses": analyses,
        "errors": errors,
    }


def _build_styles():
    styles = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            name="CoverKicker",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor(THEME["accent"]),
            alignment=0,
            spaceAfter=6,
        ),
        "cover_title": ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName="SourceHanSans",
            fontSize=30,
            leading=36,
            textColor=colors.HexColor(THEME["ink"]),
            alignment=0,
            spaceAfter=10,
        ),
        "cover_subtitle": ParagraphStyle(
            name="CoverSubTitle",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=11,
            leading=17,
            textColor=colors.HexColor(THEME["muted"]),
            alignment=0,
        ),
        "section": ParagraphStyle(
            name="Section",
            parent=styles["Heading1"],
            fontName="SourceHanSans",
            fontSize=18,
            leading=24,
            textColor=colors.HexColor(THEME["ink"]),
            spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            name="SubSection",
            parent=styles["Heading2"],
            fontName="SourceHanSans",
            fontSize=11.5,
            leading=15,
            textColor=colors.HexColor(THEME["ink"]),
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=10.2,
            leading=16,
            textColor=colors.HexColor(THEME["text"]),
        ),
        "small": ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=8.7,
            leading=12,
            textColor=colors.HexColor(THEME["muted"]),
        ),
        "metric_value": ParagraphStyle(
            name="MetricValue",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor(THEME["ink"]),
            alignment=1,
        ),
        "metric_label": ParagraphStyle(
            name="MetricLabel",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor(THEME["muted"]),
            alignment=1,
        ),
        "badge": ParagraphStyle(
            name="Badge",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=9,
            leading=12,
            textColor=colors.white,
            alignment=1,
        ),
        "card_title": ParagraphStyle(
            name="CardTitle",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor(THEME["muted"]),
        ),
        "card_body": ParagraphStyle(
            name="CardBody",
            parent=styles["BodyText"],
            fontName="SourceHanSans",
            fontSize=10,
            leading=15,
            textColor=colors.HexColor(THEME["text"]),
        ),
    }


def _sentiment_chip(sentiment: str) -> tuple[colors.Color, str]:
    mapping = {
        "positive": (colors.HexColor(THEME["success"]), "情绪 Positive"),
        "neutral": (colors.HexColor(THEME["gold"]), "情绪 Neutral"),
        "negative": (colors.HexColor(THEME["danger"]), "情绪 Negative"),
    }
    return mapping.get(sentiment, (colors.HexColor(THEME["gold"]), "情绪 Neutral"))


def _risk_chip(risk_level: str) -> tuple[colors.Color, str]:
    mapping = {
        "low": (colors.HexColor(THEME["success"]), "风险 Low"),
        "medium": (colors.HexColor(THEME["gold"]), "风险 Medium"),
        "high": (colors.HexColor(THEME["danger"]), "风险 High"),
    }
    return mapping.get(risk_level, (colors.HexColor(THEME["gold"]), "风险 Medium"))


def _signal_chip(signal: str) -> tuple[colors.Color, str]:
    mapping = {
        "买入": (colors.HexColor(THEME["accent"]), "GS 买入"),
        "卖出": (colors.HexColor(THEME["danger"]), "GS 卖出"),
        "超买": (colors.HexColor(THEME["gold"]), "GS 超买"),
        "超卖": (colors.HexColor(THEME["gold"]), "GS 超卖"),
    }
    return mapping.get(signal, (colors.HexColor(THEME["ink"]), f"GS {signal}"))


def _pill(text: str, color: colors.Color, style: ParagraphStyle, width: float = 1.18 * inch) -> Table:
    table = Table([[Paragraph(text, style)]], colWidths=[width], rowHeights=[0.3 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _card(content: List[List[Any]], col_widths: List[float], background: str = "panel", border_color: Optional[str] = None) -> Table:
    table = Table(content, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(THEME[background])),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(THEME[border_color or "line"])),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def _metric_card(value: str, label: str, width: float, styles: Dict[str, ParagraphStyle]) -> Table:
    return _card(
        [[Paragraph(f"<b>{value}</b>", styles["metric_value"])], [Paragraph(label, styles["metric_label"])]],
        [width],
        background="panel",
    )


def _key_value_rows(rows: List[List[Any]], widths: List[float]) -> Table:
    table = Table(rows, colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor(THEME["line"])),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(THEME["line"])),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _chart_image(buffer: io.BytesIO, width: float, height: float) -> Image:
    buffer.seek(0)
    image = Image(buffer, width=width, height=height)
    image.hAlign = "CENTER"
    return image


def _plot_empty_chart(message: str, width: float, height: float) -> io.BytesIO:
    plt = _load_pyplot()
    fig, ax = plt.subplots(figsize=(width, height), dpi=140)
    fig.patch.set_facecolor("#ffffff")
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color=THEME["muted"])
    ax.axis("off")
    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return buffer


def _plot_trend_chart(analysis: Dict[str, Any]) -> io.BytesIO:
    price_series = analysis.get("price_series") or []
    if not price_series:
        return _plot_empty_chart("暂无可用趋势数据", 7.2, 2.7)

    plt = _load_pyplot()
    closes = [_to_float(item.get("close")) for item in price_series]
    labels = [item.get("date", "")[5:] for item in price_series]
    volumes = [_to_float(item.get("volume")) or 0 for item in price_series]
    x = np.arange(len(price_series))

    fig, ax = plt.subplots(figsize=(7.2, 2.7), dpi=140)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fbfcfe")

    valid_idx = [i for i, value in enumerate(closes) if value is not None]
    if valid_idx:
        close_values = [closes[i] for i in valid_idx]
        change_percent = _to_float(analysis.get("change_percent")) or 0.0
        line_color = THEME["success"] if change_percent >= 0 else THEME["danger"]
        fill_color = THEME["success_soft"] if change_percent >= 0 else THEME["danger_soft"]
        ax.plot(valid_idx, close_values, color=line_color, linewidth=2.3, solid_capstyle="round")
        ax.fill_between(valid_idx, close_values, min(close_values), color=fill_color, alpha=0.85)

        ma20 = []
        for i in range(len(closes)):
            window = [v for v in closes[max(0, i - 19): i + 1] if v is not None]
            ma20.append(sum(window) / len(window) if len(window) >= 5 else None)
        ma_idx = [i for i, value in enumerate(ma20) if value is not None]
        ma_values = [ma20[i] for i in ma_idx]
        ax.plot(ma_idx, ma_values, color=THEME["gold"], linewidth=1.3, linestyle=(0, (4, 3)))

        latest = close_values[-1]
        start = close_values[0]
        high = max(close_values)
        low = min(close_values)
        ax.scatter(valid_idx[-1], latest, color=line_color, s=32, zorder=4, edgecolors="white", linewidths=0.9)
        ax.scatter(valid_idx[0], start, color=THEME["ink"], s=18, zorder=4, edgecolors="white", linewidths=0.7)
        ax.annotate(f"{latest:.2f}", (valid_idx[-1], latest), textcoords="offset points", xytext=(6, 8), fontsize=8, color=THEME["ink"])

        ax.axhline(high, color="#cbd5e1", linewidth=0.8, linestyle=":")
        ax.axhline(low, color="#cbd5e1", linewidth=0.8, linestyle=":")
        ax.text(0.01, 0.97, f"High {high:.2f}", transform=ax.transAxes, ha="left", va="top", fontsize=7.5, color=THEME["muted"])
        ax.text(0.01, 0.04, f"Low {low:.2f}", transform=ax.transAxes, ha="left", va="bottom", fontsize=7.5, color=THEME["muted"])
        ax.text(
            0.985,
            0.96,
            f"Last {_format_number(latest)}\nMove {_format_percent(change_percent)}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color=THEME["ink"],
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#ffffff",
                "edgecolor": "#d8dee8",
                "linewidth": 0.8,
            },
        )
        if ma_values:
            ax.text(
                0.985,
                0.74,
                f"MA20 {_format_number(ma_values[-1])}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=7.5,
                color=THEME["gold"],
            )

    volume_ax = ax.twinx()
    volume_colors = [fill_color if i in valid_idx else "#ced8e4" for i in range(len(x))]
    volume_ax.bar(x, volumes, color=volume_colors, alpha=0.18, width=0.72)
    volume_ax.set_yticks([])
    volume_ax.spines["right"].set_visible(False)

    step = max(1, len(labels) // 6)
    ticks = x[::step] if len(x) else []
    ax.set_xticks(ticks)
    ax.set_xticklabels([labels[i] for i in ticks], fontsize=8, color=THEME["muted"])
    ax.tick_params(axis="y", labelsize=8, colors=THEME["muted"])
    ax.grid(axis="y", color="#e5ebf3", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d7e0ea")
    ax.spines["bottom"].set_color("#d7e0ea")
    ax.set_title("Price Trend & Volume", fontsize=10.5, color=THEME["ink"], loc="left", pad=8)
    ax.text(
        0.0,
        1.05,
        f"{analysis['symbol']}  {_safe_text(analysis.get('name', analysis['symbol']))}",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color=THEME["muted"],
    )

    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return buffer


def _plot_indicator_chart(analysis: Dict[str, Any]) -> io.BytesIO:
    price_series = analysis.get("price_series") or []
    if not price_series:
        return _plot_empty_chart("暂无可用技术指标数据", 7.2, 2.9)

    plt = _load_pyplot()
    closes = np.array([_to_float(item.get("close")) or 0 for item in price_series], dtype=float)
    x = np.arange(len(closes))

    delta = np.diff(closes, prepend=closes[0])
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    rsi_values: List[float] = []
    for idx in range(len(closes)):
        start = max(0, idx - 13)
        avg_gain = gains[start: idx + 1].mean() if idx >= 1 else 0.0
        avg_loss = losses[start: idx + 1].mean() if idx >= 1 else 0.0
        if avg_loss == 0:
            rsi_values.append(100.0 if avg_gain > 0 else 50.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

    ema12, ema26 = [], []
    m12, m26 = 2 / 13, 2 / 27
    for idx, value in enumerate(closes):
        if idx == 0:
            ema12.append(value)
            ema26.append(value)
        else:
            ema12.append((value - ema12[-1]) * m12 + ema12[-1])
            ema26.append((value - ema26[-1]) * m26 + ema26[-1])
    macd = np.array(ema12) - np.array(ema26)
    signal = []
    ms = 2 / 10
    for idx, value in enumerate(macd):
        if idx == 0:
            signal.append(value)
        else:
            signal.append((value - signal[-1]) * ms + signal[-1])
    signal = np.array(signal)
    hist = macd - signal

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 2.9), dpi=140, sharex=True)
    fig.patch.set_facecolor("#ffffff")

    axes[0].set_facecolor("#fbfcfe")
    axes[0].axhspan(70, 100, color=THEME["danger_soft"], alpha=0.8)
    axes[0].axhspan(30, 70, color="#f8fafc", alpha=1.0)
    axes[0].axhspan(0, 30, color=THEME["success_soft"], alpha=0.8)
    axes[0].plot(x, rsi_values, color=THEME["accent"], linewidth=1.9)
    axes[0].axhline(70, color=THEME["danger"], linewidth=1, linestyle=(0, (4, 3)))
    axes[0].axhline(30, color=THEME["success"], linewidth=1, linestyle=(0, (4, 3)))
    axes[0].set_ylim(0, 100)
    axes[0].set_title("RSI", fontsize=10, color=THEME["ink"], loc="left")
    axes[0].grid(axis="y", color="#e5ebf3", linewidth=0.8)
    if len(rsi_values):
        axes[0].text(0.985, 0.82, f"{rsi_values[-1]:.1f}", transform=axes[0].transAxes, ha="right", va="center", fontsize=8, color=THEME["ink"])
        axes[0].text(0.985, 0.97, "Overbought", transform=axes[0].transAxes, ha="right", va="top", fontsize=7.2, color=THEME["danger"])
        axes[0].text(0.985, 0.03, "Oversold", transform=axes[0].transAxes, ha="right", va="bottom", fontsize=7.2, color=THEME["success"])

    axes[1].set_facecolor("#fbfcfe")
    axes[1].plot(x, macd, color=THEME["ink"], linewidth=1.4, label="MACD")
    axes[1].plot(x, signal, color=THEME["gold"], linewidth=1.2, label="Signal")
    axes[1].bar(x, hist, color=[THEME["success"] if v >= 0 else THEME["danger"] for v in hist], alpha=0.55, width=0.72)
    axes[1].axhline(0, color="#94a3b8", linewidth=1)
    axes[1].set_title("MACD", fontsize=10, color=THEME["ink"], loc="left")
    axes[1].legend(loc="upper left", fontsize=8, frameon=False)
    axes[1].grid(axis="y", color="#e5ebf3", linewidth=0.8)
    if len(macd):
        axes[1].text(
            0.985,
            0.94,
            f"MACD {_format_number(macd[-1])}\nSignal {_format_number(signal[-1])}",
            transform=axes[1].transAxes,
            ha="right",
            va="top",
            fontsize=7.6,
            color=THEME["ink"],
            bbox={
                "boxstyle": "round,pad=0.28",
                "facecolor": "#ffffff",
                "edgecolor": "#d8dee8",
                "linewidth": 0.7,
            },
        )

    labels = [item.get("date", "")[5:] for item in price_series]
    step = max(1, len(labels) // 6)
    ticks = x[::step] if len(x) else []
    axes[1].set_xticks(ticks)
    axes[1].set_xticklabels([labels[i] for i in ticks], fontsize=8, color=THEME["muted"])

    for ax in axes:
        ax.tick_params(axis="y", labelsize=8, colors=THEME["muted"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#d7e0ea")
        ax.spines["bottom"].set_color("#d7e0ea")

    buffer = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return buffer


def _summary_stats_row(summary: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    cards = [
        _metric_card(str(summary["successful_analyses"]), "Successful Names", 2.0 * inch, styles),
        _metric_card(str(summary["failed_analyses"]), "Failed Names", 2.0 * inch, styles),
        _metric_card(str(summary["risk_breakdown"]["high"]), "High-Risk Flags", 2.0 * inch, styles),
    ]
    table = Table([cards], colWidths=[2.05 * inch, 2.05 * inch, 2.05 * inch])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return table


def _summary_insight_card(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    summary = report_data["summary"]
    top_focus = summary["top_focus"]
    recommendations = summary["recommendation_breakdown"]
    sentiment = summary["sentiment_breakdown"]
    risk = summary["risk_breakdown"]

    focus_lines = []
    for item in top_focus:
        focus_lines.append(
            f"<b>{item['symbol']}</b>  {_safe_text(item['recommendation'])}，风险 {_safe_text(item['risk_level'])}，GS {_safe_text(item['gs_signal'])}"
        )
    if not focus_lines:
        focus_lines.append("本次没有生成可用的重点标的。")

    body = (
        f"本次批量分析共覆盖 <b>{summary['total_stocks']}</b> 个标的，其中情绪正面的标的有 <b>{sentiment['positive']}</b> 个，"
        f"高风险标的有 <b>{risk['high']}</b> 个。建议分布上，买入/卖出/持有/观察分别为 "
        f"<b>{recommendations['买入']}</b>/<b>{recommendations['卖出']}</b>/<b>{recommendations['持有']}</b>/<b>{recommendations['观察']}</b>。"
        f"<br/><br/><b>Top Focus</b><br/>" + "<br/>".join([f"• {line}" for line in focus_lines])
    )
    return _card([[Paragraph(body, styles["card_body"])]], [6.2 * inch], background="panel", border_color="accent")


def _overview_table(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    summary = report_data["summary"]
    analyses = report_data["analyses"][:8]
    rows: List[List[Any]] = [[
        Paragraph("<b>Name</b>", styles["small"]),
        Paragraph("<b>Price</b>", styles["small"]),
        Paragraph("<b>Change</b>", styles["small"]),
        Paragraph("<b>Sentiment</b>", styles["small"]),
        Paragraph("<b>Risk</b>", styles["small"]),
        Paragraph("<b>GS</b>", styles["small"]),
    ]]
    for item in analyses:
        rows.append([
            Paragraph(f"{_safe_text(item['name'])}<br/><font size='8'>{item['symbol']}</font>", styles["body"]),
            Paragraph(_format_number(item["latest_close"]), styles["body"]),
            Paragraph(_format_percent(item["change_percent"]), styles["body"]),
            Paragraph(_safe_text(item["sentiment"]), styles["body"]),
            Paragraph(_safe_text(item["risk_level"]), styles["body"]),
            Paragraph(_safe_text(item["gs_signal"]), styles["body"]),
        ])

    if not analyses:
        rows.append([Paragraph("暂无数据", styles["body"]), "", "", "", "", ""])

    return _key_value_rows(rows, [1.95 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch])


def _build_cover_page(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    summary = report_data["summary"]
    cover_card = _card(
        [[
            Paragraph("ALPHABOT BATCH RESEARCH", styles["cover_kicker"]),
        ], [
            Paragraph("批量股票分析报告", styles["cover_title"]),
        ], [
            Paragraph(
                "A concise research-style report with executive highlights, price trend visuals, technical signal panels, and per-name conviction notes.",
                styles["cover_subtitle"],
            )
        ], [
            Paragraph(
                f"生成时间 {summary['generated_at']}<br/>覆盖标的 {summary['total_stocks']} 个，成功分析 {summary['successful_analyses']} 个。",
                styles["body"],
            )
        ]],
        [6.2 * inch],
        background="panel",
        border_color="ink",
    )
    return [
        Spacer(1, 0.7 * inch),
        cover_card,
        Spacer(1, 0.35 * inch),
        _summary_stats_row(summary, styles),
        Spacer(1, 0.35 * inch),
        _summary_insight_card(report_data, styles),
        PageBreak(),
    ]


def _build_summary_page(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    return [
        Paragraph("Executive Summary", styles["section"]),
        Paragraph(
            "这一页对应业界报告中的 investment highlights。先看总量、重点标的和全局分布，再进入单页个股分析。",
            styles["body"],
        ),
        Spacer(1, 0.14 * inch),
        _summary_stats_row(report_data["summary"], styles),
        Spacer(1, 0.2 * inch),
        _summary_insight_card(report_data, styles),
        Spacer(1, 0.2 * inch),
        Paragraph("Research Dashboard", styles["subsection"]),
        _overview_table(report_data, styles),
        PageBreak(),
    ]


def _highlights_block(item: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Paragraph:
    points = item["key_points"][:4] if item["key_points"] else []
    if not points:
        points = ["暂无补充亮点，建议结合主图和技术面一起判断。"]
    bullets = "<br/>".join([f"• {_safe_text(point)}" for point in points])
    return Paragraph(f"<b>Investment Highlights</b><br/>{bullets}", styles["card_body"])


def _thesis_block(item: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(
        f"<b>Core Thesis</b><br/>{_safe_text(item['summary'])}<br/><br/><b>Action</b><br/>{_safe_text(item['recommendation'])}",
        styles["card_body"],
    )


def _metrics_panel(item: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Table:
    indicators = item["indicators"]
    prediction = item["prediction"] or {}
    supports = " / ".join([_format_number(level) for level in prediction.get("support_levels", [])[:2]]) or "N/A"
    resistances = " / ".join([_format_number(level) for level in prediction.get("resistance_levels", [])[:2]]) or "N/A"
    forecast = prediction.get("price_trend", [])[:3]
    forecast_text = "；".join([f"D{point.get('day')}: {_format_number(point.get('predicted_price'))}" for point in forecast]) or "N/A"

    rows: List[List[Any]] = [
        [Paragraph("<b>Key Metrics</b>", styles["subsection"]), ""],
        [Paragraph("Latest Close", styles["small"]), Paragraph(_format_number(item["latest_close"]), styles["body"])],
        [Paragraph("Daily Change", styles["small"]), Paragraph(_format_percent(item["change_percent"]), styles["body"])],
        [Paragraph("RSI / MACD", styles["small"]), Paragraph(f"{_format_number(indicators.get('RSI'))} / {_format_number(indicators.get('MACD'))}", styles["body"])],
        [Paragraph("MA20 / MA200", styles["small"]), Paragraph(f"{_format_number(indicators.get('SMA_20'))} / {_format_number(indicators.get('SMA_200'))}", styles["body"])],
        [Paragraph("Support / Resistance", styles["small"]), Paragraph(f"{supports}<br/>{resistances}", styles["body"])],
        [Paragraph("3-Day Projection", styles["small"]), Paragraph(forecast_text, styles["body"])],
    ]
    table = Table(rows, colWidths=[1.55 * inch, 1.55 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(THEME["panel_alt"])),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(THEME["line"])),
        ("INNERGRID", (0, 1), (-1, -1), 0.5, colors.HexColor(THEME["line"])),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("SPAN", (0, 0), (1, 0)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _build_stock_section(item: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    sentiment_color, sentiment_label = _sentiment_chip(item["sentiment"])
    risk_color, risk_label = _risk_chip(item["risk_level"])
    signal_color, signal_label = _signal_chip(item["gs_signal"])

    headline = Table(
        [[
            Paragraph(
                f"<b>{_safe_text(item['name'])}</b><br/><font size='9'>{item['symbol']} · {_safe_text(item.get('exchange'), 'Exchange N/A')}</font>",
                styles["body"],
            ),
            _pill(sentiment_label, sentiment_color, styles["badge"]),
            _pill(risk_label, risk_color, styles["badge"]),
            _pill(signal_label, signal_color, styles["badge"]),
        ]],
        colWidths=[3.2 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch],
    )
    headline.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    trend_chart = _chart_image(_plot_trend_chart(item), 4.1 * inch, 2.45 * inch)
    thesis_card = _card(
        [[_thesis_block(item, styles)], [Spacer(1, 0.02 * inch)], [_highlights_block(item, styles)]],
        [2.2 * inch],
        background="panel",
        border_color="accent",
    )
    top_row = Table([[trend_chart, thesis_card]], colWidths=[4.15 * inch, 2.15 * inch])
    top_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    indicator_chart = _chart_image(_plot_indicator_chart(item), 3.1 * inch, 2.25 * inch)
    metrics_panel = _metrics_panel(item, styles)
    bottom_row = Table([[indicator_chart, metrics_panel]], colWidths=[3.15 * inch, 3.15 * inch])
    bottom_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    return [
        Paragraph("Single-Name Detail", styles["section"]),
        headline,
        Spacer(1, 0.14 * inch),
        top_row,
        Spacer(1, 0.14 * inch),
        bottom_row,
        PageBreak(),
    ]


def _build_conclusion_page(report_data: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    analyses = report_data["analyses"]
    top_focus = report_data["summary"]["top_focus"]
    focus_text = "<br/>".join([
        f"• <b>{item['symbol']}</b>：{_safe_text(item['recommendation'])}"
        for item in top_focus
    ]) or "• 本次没有筛出明确的重点标的。"

    high_risk = "、".join([item["symbol"] for item in analyses if item["risk_level"] == "high"][:6]) or "暂无"
    positive = "、".join([item["symbol"] for item in analyses if item["sentiment"] == "positive"][:6]) or "暂无"

    conclusion_card = _card(
        [[Paragraph(
            f"<b>What Stands Out</b><br/>{focus_text}<br/><br/>"
            f"<b>Positive Tone Names</b><br/>{positive}<br/><br/>"
            f"<b>High Risk Names</b><br/>{high_risk}",
            styles["card_body"],
        )]],
        [6.2 * inch],
        background="panel",
        border_color="ink",
    )

    elements: List[Any] = [
        Paragraph("Closing Notes", styles["section"]),
        Paragraph(
            "结论页只保留决策上最需要回看的信息，避免把前面已经展示过的表格再重复一遍。",
            styles["body"],
        ),
        Spacer(1, 0.14 * inch),
        conclusion_card,
    ]

    if report_data["errors"]:
        error_rows: List[List[Any]] = [[Paragraph("<b>Failed Name</b>", styles["small"]), Paragraph("<b>Reason</b>", styles["small"])]]
        for symbol, error in report_data["errors"].items():
            error_rows.append([Paragraph(symbol, styles["body"]), Paragraph(_safe_text(error), styles["body"])])
        elements.extend([
            Spacer(1, 0.18 * inch),
            Paragraph("Exceptions", styles["subsection"]),
            _key_value_rows(error_rows, [1.3 * inch, 4.95 * inch]),
        ])

    return elements


def _draw_page_frame(canvas, doc):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(colors.HexColor("#f5f7fb"))
    canvas.rect(0, 0, width, height, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#ffffff"))
    canvas.rect(doc.leftMargin - 10, doc.bottomMargin - 6, doc.width + 20, doc.height + 12, stroke=0, fill=1)
    canvas.setStrokeColor(colors.HexColor(THEME["line"]))
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin - 10, height - 34, doc.leftMargin + 90, height - 34)
    canvas.setFont("SourceHanSans", 8)
    canvas.setFillColor(colors.HexColor(THEME["muted"]))
    canvas.drawRightString(width - doc.rightMargin, 22, f"AlphaBot Batch Research  |  Page {canvas.getPageNumber()}")
    canvas.restoreState()


def save_report_to_pdf(report_data: Dict[str, Any], output_path: str):
    ensure_reports_dir()
    register_fonts()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.52 * inch,
    )
    styles = _build_styles()

    elements: List[Any] = []
    elements.extend(_build_cover_page(report_data, styles))
    elements.extend(_build_summary_page(report_data, styles))
    for item in report_data["analyses"]:
        elements.extend(_build_stock_section(item, styles))
    elements.extend(_build_conclusion_page(report_data, styles))

    doc.build(elements, onFirstPage=_draw_page_frame, onLaterPages=_draw_page_frame)


def get_report_path(task_id: str) -> str:
    reports_dir = ensure_reports_dir()
    return os.path.join(reports_dir, f"time_series_analysis_{task_id}.pdf")
