"""
数据库初始化模块
用于创建数据库表和初始化数据库
"""

from sqlalchemy import inspect, text

from app.db.session import engine, Base
from app.models.user import User, InviteCode, McpToken
from app.models.stock import Stock, StockPrice, SavedStock
from app.models.conversation import Conversation
from app.models.portfolio import Position, TradeLog
from app.models.alert import AlertRule, AlertTrigger
from app.models.user_profile import UserProfile
from app.models.sim_portfolio import SimAccount, SimPosition


def _ensure_users_table_columns() -> None:
    """轻量补齐 users 表新增列，兼容当前项目未使用 Alembic 的部署方式。"""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    ddl_statements = []
    update_statements = []

    if "mcp_daily_usage_count" not in existing_columns:
        ddl_statements.append(
            "ALTER TABLE users ADD COLUMN mcp_daily_usage_count INTEGER DEFAULT 0"
        )
    if "mcp_last_reset_at" not in existing_columns:
        ddl_statements.append(
            "ALTER TABLE users ADD COLUMN mcp_last_reset_at DATETIME"
        )
        update_statements.append(
            "UPDATE users SET mcp_last_reset_at = COALESCE(last_reset_at, CURRENT_TIMESTAMP) "
            "WHERE mcp_last_reset_at IS NULL"
        )

    if not ddl_statements and not update_statements:
        return

    with engine.begin() as connection:
        for ddl in ddl_statements:
            connection.execute(text(ddl))
        for update_sql in update_statements:
            connection.execute(text(update_sql))


def init_database():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)
    _ensure_users_table_columns()
