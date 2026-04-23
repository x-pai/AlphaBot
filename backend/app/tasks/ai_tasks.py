"""
AI相关的异步任务
"""
from typing import Dict, Any, Optional, List
import asyncio
import logging
from app.core.celery_app import celery_app
from app.services.ai_service import AIService
from app.schemas.stock import AIAnalysis

logger = logging.getLogger(__name__)
@celery_app.task(name="app.tasks.ai_tasks.analyze_stock_task", bind=True)
def analyze_stock_task(self, symbol: str, data_source: Optional[str] = None, 
                       analysis_type: Optional[str] = "llm") -> AIAnalysis:
    """
    异步执行股票分析任务
    
    Args:
        symbol: 股票代码
        data_source: 数据源
        analysis_type: 分析类型
        
    Returns:
        分析结果
    """
    task_id = self.request.id
    self.update_state(state="PROGRESS", meta={"status": "正在获取股票数据"})
    
    try:
        # 创建事件循环并执行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        analysis = loop.run_until_complete(AIService.analyze_stock(symbol, data_source, analysis_type))
        loop.close()
        # 将AIAnalysis对象转换为可序列化的字典
        if analysis:
            analysis_dict = analysis.dict()
            self.update_state(state="SUCCESS", meta={"status": "分析完成", "analysis": analysis_dict})
            return analysis_dict
        else:
            self.update_state(state="SUCCESS", meta={"status": "分析完成，但没有结果"})
        return analysis
    except Exception as e:
        self.update_state(
            state="FAILURE", 
            meta={"error": f"分析失败: {str(e)}"}
        )
        raise e


@celery_app.task(name="app.tasks.ai_tasks.analyze_time_series_task", bind=True)
def analyze_time_series_task(self, symbol: str, interval: str = "daily", range: str = "1m",
                            data_source: Optional[str] = None, 
                            analysis_type: Optional[str] = "llm") -> AIAnalysis:
    """
    异步执行股票时间序列分析任务
    
    Args:
        symbol: 股票代码
        interval: 数据间隔
        range: 时间范围
        data_source: 数据源
        analysis_type: 分析类型
        
    Returns:
        分析结果
    """
    task_id = self.request.id
    self.update_state(state="PROGRESS", meta={"status": "正在获取股票时间序列数据"})
    
    try:
        # 创建事件循环并执行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        analysis = loop.run_until_complete(AIService.analyze_time_series(symbol, interval, range, data_source, analysis_type))
        loop.close()

        # 将AIAnalysis对象转换为可序列化的字典
        if analysis:
            analysis_dict = analysis.dict()
            self.update_state(state="SUCCESS", meta={"status": "分析完成", "analysis": analysis_dict})
            return analysis_dict
        else:
            self.update_state(state="SUCCESS", meta={"status": "分析完成，但没有结果"}) 
        return analysis
    except Exception as e:
        self.update_state(
            state="FAILURE", 
            meta={"error": f"分析失败: {str(e)}"}
        )
        raise e


@celery_app.task(name="app.tasks.ai_tasks.analyze_intraday_task", bind=True)
def analyze_intraday_task(self, symbol: str, data_source: Optional[str] = None,
                         analysis_type: Optional[str] = "llm") -> AIAnalysis:
    """
    异步执行股票盘中数据分析任务
    
    Args:
        symbol: 股票代码
        data_source: 数据源
        analysis_type: 分析类型
        
    Returns:
        分析结果
    """
    task_id = self.request.id
    self.update_state(state="PROGRESS", meta={"status": "正在获取盘中数据"})
    
    try:
        # 创建事件循环并执行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        analysis = loop.run_until_complete(AIService.analyze_intraday(symbol, data_source, analysis_type))
        loop.close()

        # 将AIAnalysis对象转换为可序列化的字典
        if analysis:
            analysis_dict = analysis.dict()
            self.update_state(state="SUCCESS", meta={"status": "分析完成", "analysis": analysis_dict})
            return analysis_dict
        else:
            self.update_state(state="SUCCESS", meta={"status": "分析完成，但没有结果"}) 
        return analysis
    except Exception as e:
        self.update_state(
            state="FAILURE", 
            meta={"error": f"分析失败: {str(e)}"}
        )
        raise e 


@celery_app.task(name="app.tasks.ai_tasks.batch_analyze_time_series_task", bind=True)
def batch_analyze_time_series_task(
    self,
    symbols: List[str],
    interval: str = "daily",
    range: str = "1m",
    data_source: Optional[str] = None,
    analysis_type: Optional[str] = "llm"
) -> Dict[str, Any]:
    """
    批量执行股票时间序列分析任务
    
    Args:
        symbols: 股票代码列表
        interval: 数据间隔
        range: 时间范围
        data_source: 数据源
        analysis_type: 分析类型
    """
    from app.services.report_service import generate_analysis_report, save_report_to_pdf, get_report_path

    task_id = self.request.id
    total_stocks = len(symbols)
    processed_stocks = 0
    results: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    self.update_state(
        state="PROGRESS",
        meta={
            "status": f"批量分析任务已启动，共 {total_stocks} 个股票",
            "current_symbol": None,
            "progress": 0,
            "completed": 0,
            "total": total_stocks,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "errors": {},
            "results": {},
        }
    )

    for symbol in symbols:
        try:
            # 创建事件循环并执行异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            analysis = loop.run_until_complete(AIService.analyze_time_series(symbol, interval, range, data_source, analysis_type))
            loop.close()
            results[symbol] = analysis.dict() if hasattr(analysis, "dict") else analysis
        except Exception as e:
            logger.error(f"分析股票 {symbol} 时出错: {str(e)}")
            errors[symbol] = str(e)

        processed_stocks += 1
        self.update_state(
            state="PROGRESS",
            meta={
                "status": f"正在分析 {symbol} ({processed_stocks}/{total_stocks})",
                "current_symbol": symbol,
                "progress": (processed_stocks / total_stocks) * 100,
                "completed": processed_stocks,
                "total": total_stocks,
                "successful_analyses": len(results),
                "failed_analyses": len(errors),
                "errors": errors,
                "results": results,
            }
        )
    
    # 生成分析报告
    try:
        report_data = generate_analysis_report(results, errors)
        report_path = get_report_path(task_id)
        save_report_to_pdf(report_data, report_path)
    except Exception as e:
        logger.error(f"生成报告失败: {str(e)}")
        self.update_state(
            state="FAILURE",
            meta={"error": f"生成报告失败: {str(e)}"}
        )
        raise e

    result_summaries = {}
    for symbol, analysis in results.items():
        if isinstance(analysis, dict):
            result_summaries[symbol] = {
                "summary": analysis.get("summary"),
                "sentiment": analysis.get("sentiment"),
                "recommendation": analysis.get("recommendation"),
                "riskLevel": analysis.get("riskLevel"),
            }

    return {
        "status": "分析完成",
        "message": f"已完成 {total_stocks} 个股票的批量分析",
        "progress": 100,
        "current_symbol": symbols[-1] if symbols else None,
        "completed": total_stocks,
        "total": total_stocks,
        "successful_analyses": len(results),
        "failed_analyses": len(errors),
        "errors": errors,
        "results": result_summaries,
        "report_url": f"/api/v1/reports/{task_id}/download"
    }
