from typing import Dict, Any
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app.core.config import settings

def register_fonts():
    """注册中文字体"""
    # 使用思源黑体
    font_path = os.path.join(settings.BASE_DIR, "fonts", "SourceHanSansSC-Regular.ttf")
    pdfmetrics.registerFont(TTFont('SourceHanSans', font_path))

def ensure_reports_dir():
    """确保reports目录存在"""
    reports_dir = os.path.join(settings.BASE_DIR, "reports")
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    return reports_dir

def generate_analysis_report(results: Dict[str, Any], errors: Dict[str, str]) -> Dict[str, Any]:
    """生成分析报告数据"""
    report_data = {
        "summary": {
            "total_stocks": len(results) + len(errors),
            "successful_analyses": len(results),
            "failed_analyses": len(errors),
            "generated_at": datetime.now().isoformat()
        },
        "analyses": results,
        "errors": errors
    }
    return report_data

def save_report_to_pdf(report_data: Dict[str, Any], output_path: str):
    """将报告保存为PDF文件"""
    ensure_reports_dir()
    register_fonts()
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # 更新样式使用思源黑体
    styles.add(ParagraphStyle(
        name='ChineseTitle',
        fontName='SourceHanSans',  # 更改字体名称
        fontSize=24,
        leading=30,
        alignment=1,
    ))
    
    styles.add(ParagraphStyle(
        name='ChineseNormal',
        fontName='SourceHanSans',  # 更改字体名称
        fontSize=12,
        leading=14,
    ))
    
    styles.add(ParagraphStyle(
        name='ChineseHeading1',
        fontName='SourceHanSans',  # 更改字体名称
        fontSize=18,
        leading=22,
    ))
    
    styles.add(ParagraphStyle(
        name='ChineseHeading2',
        fontName='SourceHanSans',  # 更改字体名称
        fontSize=14,
        leading=18,
    ))

    elements = []
    
    # 使用中文样式替换原有样式
    elements.append(Paragraph("股票时间序列分析报告", styles['ChineseTitle']))
    
    elements.append(Paragraph(
        f"生成时间: {report_data['summary']['generated_at']}", 
        styles['ChineseNormal']
    ))
    
    # 添加摘要信息
    summary = report_data['summary']
    elements.append(Paragraph("分析总结", styles['ChineseHeading1']))
    elements.append(Paragraph(
        f"总计分析股票: {summary['total_stocks']}\n"
        f"成功分析: {summary['successful_analyses']}\n"
        f"失败分析: {summary['failed_analyses']}\n",
        styles['ChineseNormal']
    ))
    
    # 添加详细分析结果
    elements.append(Paragraph("分析结果", styles['ChineseHeading1']))
    for symbol, analysis in report_data['analyses'].items():
        elements.append(Paragraph(f"股票: {symbol}", styles['ChineseHeading2']))
        if isinstance(analysis, dict):
            for key, value in analysis.items():
                if key not in ['error', 'status']:
                    elements.append(Paragraph(f"{key}: {value}", styles['ChineseNormal']))
    
    # 添加错误信息
    if report_data['errors']:
        elements.append(Paragraph("错误信息", styles['ChineseHeading1']))
        for symbol, error in report_data['errors'].items():
            elements.append(Paragraph(f"{symbol}: {error}", styles['ChineseNormal']))
    
    doc.build(elements)

def get_report_path(task_id: str) -> str:
    """获取报告文件路径"""
    reports_dir = ensure_reports_dir()
    return os.path.join(reports_dir, f"time_series_analysis_{task_id}.pdf") 