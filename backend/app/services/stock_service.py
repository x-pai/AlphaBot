import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from app.core.config import settings
from app.models.stock import Stock, StockPrice, SavedStock
from app.schemas.stock import StockInfo, StockPriceHistory, StockPricePoint, SavedStock as SavedStockSchema
from app.services.data_sources.factory import DataSourceFactory
from app.models.user import User

logger = logging.getLogger("uvicorn")

class StockService:
    """股票服务类，处理股票数据的获取和处理"""
    
    @staticmethod
    async def search_stocks(query: str, data_source: str = None, db: Session = None) -> List[StockInfo]:
        """搜索股票"""
        data_source = DataSourceFactory.get_data_source(data_source)
        stocks = await data_source.search_stocks(query)
        
        # 如果提供了数据库会话，则创建或更新股票记录
        if db is not None:
            for stock_info in stocks:
                try:
                    # 查找现有股票
                    existing_stock = db.query(Stock).filter(Stock.symbol == stock_info.symbol).first()
                    
                    if existing_stock:
                        # 更新现有股票信息
                        existing_stock.name = stock_info.name
                        existing_stock.exchange = stock_info.exchange
                        existing_stock.currency = stock_info.currency
                        existing_stock.last_updated = datetime.utcnow()
                    else:
                        # 创建新股票记录
                        new_stock = Stock(
                            symbol=stock_info.symbol,
                            name=stock_info.name,
                            exchange=stock_info.exchange,
                            currency=stock_info.currency,
                            last_updated=datetime.utcnow()
                        )
                        db.add(new_stock)
                    
                    db.commit()
                except Exception as e:
                    print(f"保存股票 {stock_info.symbol} 时出错: {str(e)}")
                    db.rollback()
        
        return stocks
    
    @staticmethod
    async def get_stock_info(symbol: str, data_source: str = None) -> Optional[StockInfo]:
        """获取股票详细信息"""
        data_source = DataSourceFactory.get_data_source(data_source)
        return await data_source.get_stock_info(symbol)
    
    @staticmethod
    async def get_stock_price_history(
        symbol: str, 
        interval: str = "daily", 
        range: str = "1m",
        data_source: str = None
    ) -> Optional[StockPriceHistory]:
        """获取股票历史价格数据"""
        data_source = DataSourceFactory.get_data_source(data_source)
        return await data_source.get_stock_price_history(symbol, interval, range)
    
    @staticmethod
    async def save_stock_to_db(db: Session, user_id: int, symbol: str, notes: Optional[str] = None) -> Optional[SavedStockSchema]:
        """保存股票到用户的收藏夹"""
        try:
            # 查找股票
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                return None

            # 检查是否已经收藏
            existing = db.query(SavedStock).filter(
                and_(
                    SavedStock.user_id == user_id,
                    SavedStock.stock_id == stock.id
                )
            ).first()

            if existing:
                # 如果已存在，更新笔记
                existing.notes = notes
                saved_stock = existing
            else:
                # 如果不存在，创建新的收藏
                saved_stock = SavedStock(
                    user_id=user_id,
                    stock_id=stock.id,
                    notes=notes
                )
                db.add(saved_stock)

            db.commit()
            db.refresh(saved_stock)
            
            # 创建包含所有必要字段的字典
            stock_dict = {
                "symbol": stock.symbol,
                "name": stock.name,
                "exchange": stock.exchange,
                "currency": stock.currency
            }
            
            saved_stock_dict = {
                "id": saved_stock.id,
                "stock_id": saved_stock.stock_id,
                "user_id": saved_stock.user_id,
                "symbol": stock.symbol,  # 从关联的stock中获取
                "added_at": saved_stock.added_at,
                "notes": saved_stock.notes,
                "stock": stock_dict
            }
            
            return SavedStockSchema(**saved_stock_dict)
        except Exception as e:
            print(f"保存股票时出错: {str(e)}")
            db.rollback()
            return None
    
    @staticmethod
    async def get_saved_stocks(db: Session, user_id: int) -> List[SavedStockSchema]:
        """获取用户保存的股票列表"""
        try:
            saved_stocks = db.query(SavedStock).filter(SavedStock.user_id == user_id).all()
            result = []
            for saved_stock in saved_stocks:
                # 创建包含所有必要字段的字典
                stock_dict = {
                    "symbol": saved_stock.stock.symbol,
                    "name": saved_stock.stock.name,
                    "exchange": saved_stock.stock.exchange,
                    "currency": saved_stock.stock.currency
                }
                
                saved_stock_dict = {
                    "id": saved_stock.id,
                    "stock_id": saved_stock.stock_id,
                    "user_id": saved_stock.user_id,
                    "symbol": saved_stock.stock.symbol,  # 从关联的stock中获取
                    "added_at": saved_stock.added_at,
                    "notes": saved_stock.notes,
                    "stock": stock_dict
                }
                
                result.append(SavedStockSchema(**saved_stock_dict))
            return result
        except Exception as e:
            print(f"获取收藏股票时出错: {str(e)}")
            return []
    
    @staticmethod
    async def delete_saved_stock(db: Session, user_id: int, symbol: str) -> bool:
        """从用户的收藏夹中删除股票"""
        try:
            # 查找股票
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                return False

            # 删除收藏
            result = db.query(SavedStock).filter(
                and_(
                    SavedStock.user_id == user_id,
                    SavedStock.stock_id == stock.id
                )
            ).delete()

            db.commit()
            return result > 0
        except Exception:
            db.rollback()
            return False
            
    @staticmethod
    async def update_stock_data(symbol: str = None, db: Session = None) -> Dict[str, Any]:
        """更新股票数据
        
        如果指定了symbol，则只更新该股票的数据
        否则更新所有已保存的股票数据
        """
        logger.info(f"开始更新股票数据: {symbol if symbol else '所有股票'}")
        try:
            if symbol:
                # 直接从数据源获取最新数据
                stock_info = await StockService.get_stock_info(symbol)
                price_history = await StockService.get_stock_price_history(symbol)
                if db and stock_info:
                    # 更新或创建股票基本信息
                    existing_stock = db.query(Stock).filter(Stock.symbol == symbol).first()
                    if existing_stock:
                        existing_stock.name = stock_info.name
                        existing_stock.exchange = stock_info.exchange
                        existing_stock.currency = stock_info.currency
                        existing_stock.last_updated = datetime.utcnow()
                    else:
                        new_stock = Stock(
                            symbol=symbol,
                            name=stock_info.name,
                            exchange=stock_info.exchange,
                            currency=stock_info.currency,
                            last_updated=datetime.utcnow()
                        )
                        db.add(new_stock)
                        db.flush()  # 获取新创建的stock_id
                        existing_stock = new_stock

                    # 保存历史价格数据
                    if price_history and price_history.data:
                        for price_point in price_history.data:
                            # 检查是否已存在该日期的价格记录
                            existing_price = db.query(StockPrice).filter(
                                and_(
                                    StockPrice.stock_id == existing_stock.id,
                                    StockPrice.date == price_point.date
                                )
                            ).first()

                            if existing_price:
                                # 更新现有价格记录
                                existing_price.open = price_point.open
                                existing_price.high = price_point.high
                                existing_price.low = price_point.low
                                existing_price.close = price_point.close
                                existing_price.volume = price_point.volume
                                existing_price.last_updated = datetime.utcnow()
                            else:
                                # 确保日期是datetime对象
                                price_date = (
                                    price_point.date 
                                    if isinstance(price_point.date, datetime) 
                                    else datetime.fromisoformat(str(price_point.date))
                                )
                                
                                # 创建新的价格记录
                                new_price = StockPrice(
                                    stock_id=existing_stock.id,
                                    date=price_date,  # 使用转换后的日期
                                    open=price_point.open,
                                    high=price_point.high,
                                    low=price_point.low,
                                    close=price_point.close,
                                    volume=price_point.volume,
                                    last_updated=datetime.utcnow()
                                )
                                db.add(new_price)

                    try:
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        print(f"保存股票 {symbol} 数据时出错: {str(e)}")
                        return {"success": False, "error": f"保存股票数据时出错: {str(e)}"}
                logger.info(f"已更新股票 {symbol} 的数据")
                return {"success": True, "data": {"message": f"已更新股票 {symbol} 的数据"}}
            else:
                # 如果没有提供数据库会话，则只返回成功消息
                if db is None:
                    return {"success": True, "data": {"message": "已触发更新所有股票数据的任务"}}
                
                # 从数据库获取所有保存的股票
                try:
                    stocks = db.query(Stock).all()
                    updated_count = 0
                    failed_count = 0
                    
                    # 逐个更新股票数据
                    for stock in stocks:
                        try:
                            result = await StockService.update_stock_data(stock.symbol, db)
                            if result["success"]:
                                updated_count += 1
                            else:
                                failed_count += 1
                        except Exception as e:
                            failed_count += 1
                            print(f"更新股票 {stock.symbol} 数据时出错: {str(e)}")
                    logger.info(f"成功更新 {updated_count}/{len(stocks)} 个股票的数据，失败 {failed_count} 个")
                    return {
                        "success": True, 
                        "data": {
                            "message": f"成功更新 {updated_count}/{len(stocks)} 个股票的数据，失败 {failed_count} 个"
                        }
                    }
                except Exception as e:
                    print(f"获取所有股票时出错: {str(e)}")
                    return {"success": False, "error": f"获取所有股票时出错: {str(e)}"}
        except Exception as e:
            print(f"更新股票数据时出错: {str(e)}")
            return {"success": False, "error": f"更新股票数据时出错: {str(e)}"}
    
    @staticmethod
    async def get_stock_intraday(
        symbol: str,
        refresh: bool = False,
        data_source: str = None
    ) -> Dict[str, Any]:
        """获取股票分时数据"""
        data_source = DataSourceFactory.get_data_source(data_source)
        return await data_source.get_intraday_data(symbol, refresh)
    
    @staticmethod
    async def get_market_news(db: Session, symbol: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """获取市场新闻"""
        # TODO: 实现从数据源获取新闻的逻辑
        data_source = DataSourceFactory.get_data_source()
        return await data_source.get_market_news(symbol, limit)
        # 模拟实现
        # 返回一些模拟数据
        return [
            {
                "id": 1,
                "title": "市场行情分析：A股震荡上行",
                "source": "财经日报",
                "url": "https://example.com/news/1",
                "published_at": "2023-03-30T10:00:00Z",
                "summary": "今日A股市场整体呈现震荡上行态势，科技板块表现活跃。"
            },
            {
                "id": 2,
                "title": "央行降准0.5个百分点",
                "source": "金融时报",
                "url": "https://example.com/news/2",
                "published_at": "2023-03-29T14:30:00Z",
                "summary": "中国人民银行宣布全面降准0.5个百分点，释放长期资金1万亿元。"
            },
            # 根据需要调整返回的新闻数量
        ][:limit]
    
    @staticmethod
    async def get_stock_fundamentals(
        symbol: str,
        report_type: str = "all",
        data_source: str = None
    ) -> Dict[str, Any]:
        """
        获取股票基本面数据，包括财务报表、业绩报告等
        
        Args:
            symbol: 股票代码
            report_type: 报表类型
            data_source: 数据源
            
        Returns:
            包含基本面数据的字典
        """
        try:
            # 获取数据源
            data_source_obj = DataSourceFactory.get_data_source(data_source)
            
            # 获取基本面数据
            fundamentals = await data_source_obj.get_fundamentals(symbol)
            
            # 如果指定了特定类型的报表且该类型存在于结果中，则只返回该类型
            if report_type != "all" and report_type in fundamentals:
                return {report_type: fundamentals[report_type]}
            
            return fundamentals
                
        except Exception as e:
            logger.error(f"获取基本面数据时出错: {str(e)}")
            return {"error": f"获取基本面数据时出错: {str(e)}"} 