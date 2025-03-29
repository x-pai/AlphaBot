from app.db.session import SessionLocal
from app.services.stock_service import StockService

async def update_stock_data_with_db(symbol: str = None):
    """包装函数，在执行时创建数据库会话"""
    db = SessionLocal()
    try:
        return await StockService.update_stock_data(symbol, db)
    finally:
        db.close() 