#!/bin/sh

# 等待数据库准备就绪（如果需要的话）
# python wait_for_db.py

# 运行数据库迁移（如果需要的话）
# alembic upgrade head

# 初始化数据库表
python -c "from app.db.init_db import init_database; init_database()"

# 创建管理员用户
python app/cli/create_admin.py

# 启动应用
exec "$@" 