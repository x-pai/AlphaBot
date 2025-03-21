from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import asyncio
from contextlib import asynccontextmanager

from app.core.config import settings

# 创建同步数据库引擎（用于模型创建和同步操作）
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

# 创建异步数据库引擎（如果不是SQLite）
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite不支持异步操作，我们将使用线程池来模拟异步
    async_engine = None
else:
    # 将同步URL转换为异步URL
    async_db_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
    async_db_url = async_db_url.replace('mysql://', 'mysql+aiomysql://')
    async_engine = create_async_engine(async_db_url)

# 创建同步会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建异步会话工厂（如果不是SQLite）
if async_engine:
    AsyncSessionLocal = sessionmaker(
        class_=AsyncSession, 
        expire_on_commit=False, 
        autocommit=False, 
        autoflush=False, 
        bind=async_engine
    )

# 创建基础模型类
Base = declarative_base()

# 获取数据库会话的依赖函数（同步）
def get_db():
    """获取数据库会话的依赖函数（同步）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 获取数据库会话的依赖函数（异步）
async def get_async_db():
    """获取数据库会话的依赖函数（异步）"""
    if async_engine:
        # 使用异步引擎
        async with AsyncSessionLocal() as session:
            yield session
    else:
        # 使用线程池模拟异步
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

# 在线程池中运行同步数据库操作
async def run_db_in_thread(func, *args, **kwargs):
    """在线程池中运行同步数据库操作"""
    return await asyncio.to_thread(func, *args, **kwargs) 