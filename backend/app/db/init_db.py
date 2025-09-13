"""
数据库初始化模块
用于创建数据库表和初始化数据库
"""

import os
from app.db.session import engine, Base
from app.models.user import User, InviteCode
from app.models.stock import Stock, StockPrice, SavedStock
from app.models.conversation import Conversation

def init_database():
    """初始化数据库，创建所有表"""
    # 确保数据库目录存在
    db_path = engine.url.database
    print("Database path:", db_path)
    if db_path and db_path != ":memory:":
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    Base.metadata.create_all(bind=engine) 