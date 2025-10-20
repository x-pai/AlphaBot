FROM python:3.9-slim

WORKDIR /app

# 设置 APT 国内镜像源
RUN if [ -d "/etc/apt/sources.list.d" ] && [ -f "/etc/apt/sources.list.d/debian.sources" ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    else \
        echo "deb http://mirrors.ustc.edu.cn/debian bullseye main contrib non-free" > /etc/apt/sources.list && \
        echo "deb http://mirrors.ustc.edu.cn/debian bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
        echo "deb http://mirrors.ustc.edu.cn/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list; \
    fi

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 设置 pip 镜像并安装依赖
COPY requirements.txt .
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY --chown=appuser:appuser . .

# 创建模型目录并设置权限
RUN mkdir -p /app/models && chown -R appuser:appuser /app/models

# 设置环境变量
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADMIN_USERNAME=admin \
    ADMIN_EMAIL=admin@example.com \
    ADMIN_PASSWORD=admin123

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 复制并设置入口点脚本
COPY --chown=appuser:appuser entrypoint.sh /backend/entrypoint.sh
# 处理 Windows 行尾符问题
RUN sed -i 's/\r$//' /backend/entrypoint.sh && chmod +x /backend/entrypoint.sh

ENTRYPOINT ["/backend/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]