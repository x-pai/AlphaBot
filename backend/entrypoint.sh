#!/bin/sh

# 等待数据库准备就绪（如果需要的话）
# python wait_for_db.py

# 运行数据库迁移（如果需要的话）
# alembic upgrade head

# 创建管理员用户
python /backend/app/cli/create_admin.py

# 启动应用
exec "$@" 