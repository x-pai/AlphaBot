import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.config import settings
from app.models.stock import Stock, StockPrice, SavedStock
from app.schemas.stock import StockInfo, StockPriceHistory, StockPricePoint, SavedStock as SavedStockSchema
from app.services.data_sources.factory import DataSourceFactory
from app.models.user import User

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
        try:
            if symbol:
                # 直接从数据源获取最新数据
                await StockService.get_stock_info(symbol)
                await StockService.get_stock_price_history(symbol)
                
                return {"success": True, "data": {"message": f"已更新股票 {symbol} 的数据"}}
            else:
                # 如果没有提供数据库会话，则只返回成功消息
                if db is None:
                    return {"success": True, "data": {"message": "已触发更新所有股票数据的任务"}}
                
                # 从数据库获取所有保存的股票
                try:
                    stocks = db.query(Stock).all()
                    updated_count = 0
                    
                    # 逐个更新股票数据
                    for stock in stocks:
                        try:
                            await StockService.get_stock_info(stock.symbol)
                            await StockService.get_stock_price_history(stock.symbol)
                            updated_count += 1
                        except Exception as e:
                            print(f"更新股票 {stock.symbol} 数据时出错: {str(e)}")
                    
                    return {
                        "success": True, 
                        "data": {
                            "message": f"已更新 {updated_count}/{len(stocks)} 个股票的数据"
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