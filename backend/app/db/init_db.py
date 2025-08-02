"""
数据库初始化模块
用于创建数据库表和初始化数据库
"""

from app.db.session import engine, Base
from app.models.user import User, InviteCode
from app.models.stock import Stock, StockPrice, SavedStock
from app.models.conversation import Conversation

def init_database():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine) 