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
        """获取市场新闻和公告
        
        Args:
            db: 数据库会话
            symbol: 股票代码（可选）
            limit: 返回新闻条数
            
        Returns:
            新闻列表
        """
        try:
            # 获取数据源
            data_source = DataSourceFactory.get_data_source()
            
            # 如果提供了股票代码，获取特定股票的新闻
            if symbol:
                # 尝试使用数据源的news_sentiment方法获取新闻
                news_data = await data_source.get_news_sentiment(symbol)
                
                # 检查返回的数据格式
                if "feed" in news_data and isinstance(news_data["feed"], list):
                    # 提取并格式化新闻数据
                    result = []
                    for i, news in enumerate(news_data["feed"]):
                        if i >= limit:
                            break
                            
                        # 标准化新闻数据格式
                        news_item = {
                            "title": news.get("title", ""),
                            "summary": news.get("summary", news.get("content", "")),
                            "url": news.get("url", ""),
                            "published_at": news.get("time_published", news.get("published_at", "")),
                            "source": news.get("source", ""),
                            "sentiment": news.get("overall_sentiment_score", 0)
                        }
                        result.append(news_item)
                    
                    return result
                
                # 如果没有feed字段，可能是不同的数据结构
                if "latest_news" in news_data and isinstance(news_data["latest_news"], list):
                    result = []
                    for i, news in enumerate(news_data["latest_news"]):
                        if i >= limit:
                            break
                            
                        # 港股数据源的格式可能不同
                        news_item = {
                            "title": news.get("标题", ""),
                            "summary": news.get("内容", ""),
                            "url": news.get("链接", ""),
                            "published_at": news.get("日期", ""),
                            "source": "港股资讯",
                            "sentiment": 0  # 默认中性
                        }
                        result.append(news_item)
                    
                    return result
            
            # 如果没有提供股票代码或者获取特定股票新闻失败，获取市场概览新闻
            try:
                # 使用AKShare获取市场概览新闻
                # 切换到AKShare数据源
                ak_source = DataSourceFactory.get_data_source("akshare")
                
                # 获取财经新闻
                try:
                    # 尝试获取宏观经济新闻
                    result = []
                    
                    # 尝试获取东方财富网财经新闻
                    news_df = await ak_source._run_sync(ak_source.ak.news_economic_baidu)
                    
                    if not news_df.empty:
                        for i, row in news_df.iterrows():
                            if i >= limit:
                                break
                                
                            news_item = {
                                "title": row.get("title", ""),
                                "summary": row.get("content", "")[:100] + "...",
                                "url": row.get("url", ""),
                                "published_at": row.get("date", ""),
                                "source": "百度财经",
                                "sentiment": 0  # 默认中性
                            }
                            result.append(news_item)
                        
                        return result
                except Exception as e:
                    logger.error(f"获取财经新闻出错: {str(e)}")
                    
                # 如果特定新闻源获取失败，尝试获取其他新闻源
                try:
                    # 尝试获取雪球新闻
                    news_df = await ak_source._run_sync(ak_source.ak.stock_zh_a_alerts_cls)
                    
                    if not news_df.empty:
                        result = []
                        for i, row in news_df.iterrows():
                            if i >= limit:
                                break
                                
                            news_item = {
                                "title": row.get("title", ""),
                                "summary": row.get("content", "")[:100] + "..." if "content" in row else "",
                                "url": "",
                                "published_at": row.get("datetime", ""),
                                "source": "A股预警",
                                "sentiment": 0  # 默认中性
                            }
                            result.append(news_item)
                        
                        return result
                except Exception as e:
                    logger.error(f"获取A股预警新闻出错: {str(e)}")
            
            except Exception as e:
                logger.error(f"获取市场新闻出错: {str(e)}")
            
            # 如果所有方法都失败，返回一些模拟数据
            return [
                {
                    "title": "市场资讯暂时不可用",
                    "summary": "我们正在努力恢复市场新闻数据，请稍后再试。",
                    "url": "",
                    "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "系统消息",
                    "sentiment": 0
                }
            ]
        
        except Exception as e:
            logger.error(f"获取市场新闻和公告时出错: {str(e)}")
            return [] 