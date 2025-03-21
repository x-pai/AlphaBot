#!/bin/bash

# AlphaBot一键部署脚本
# 作者: BenalexCheung
# 版本: 1.0.0

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否安装
check_docker() {
    print_message "检查 Docker 是否安装..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    print_message "Docker 已安装 ✓"

    print_message "检查 Docker Compose 是否安装..."
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安装，请先安装 Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_message "Docker Compose 已安装 ✓"
}

# 检查环境文件
check_env_file() {
    print_message "检查环境配置文件..."
    if [ ! -f "./backend/.env" ]; then
        print_warning "未找到 backend/.env 文件，将从示例文件创建"
        if [ -f "./backend/.env.example" ]; then
            cp ./backend/.env.example ./backend/.env
            print_message "已从示例文件创建 .env 文件，请编辑 ./backend/.env 文件配置您的环境变量"
        else
            print_error "未找到 .env.example 文件，请手动创建 .env 文件"
            exit 1
        fi
    else
        print_message "环境配置文件已存在 ✓"
    fi
}

# 训练机器学习模型
train_ml_model() {
    print_message "检查是否需要训练机器学习模型..."
    if [ ! -f "./backend/models/stock_analysis_model.pkl" ]; then
        print_message "未找到预训练模型，开始训练..."
        
        # 使用Docker运行训练脚本
        docker-compose run --rm backend python train_model.py
        
        if [ $? -eq 0 ]; then
            print_message "模型训练成功 ✓"
        else
            print_error "模型训练失败，将使用规则分析模式"
            # 确保 .env 文件中使用规则分析模式
            sed -i 's/DEFAULT_ANALYSIS_MODE=.*/DEFAULT_ANALYSIS_MODE="rule"/' ./backend/.env
        fi
    else
        print_message "预训练模型已存在 ✓"
    fi
}

# 构建并启动服务
build_and_start() {
    print_message "构建并启动服务..."
    docker-compose down
    
    print_message "构建Docker镜像..."
    if ! docker-compose build; then
        print_error "Docker镜像构建失败，请检查错误信息"
        exit 1
    fi
    print_message "Docker镜像构建成功 ✓"
    
    print_message "启动服务..."
    if ! docker-compose up -d; then
        print_error "服务启动失败，请检查Docker日志"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        print_message "服务启动成功 ✓"
        print_message "后端API: http://localhost:8000/api/v1/docs"
        print_message "前端界面: http://localhost:3000"
    else
        print_error "服务启动失败，请检查日志"
        exit 1
    fi
}

# 显示日志
show_logs() {
    read -p "是否查看服务日志? (y/n): " show_logs
    if [[ $show_logs == "y" || $show_logs == "Y" ]]; then
        docker-compose logs -f
    fi
}

# 主函数
main() {
    echo "=================================================="
    echo "       AlphaBot一键部署脚本                    "
    echo "=================================================="
    
    # 检查Docker
    check_docker
    
    # 检查环境文件
    check_env_file
    
    # 训练机器学习模型
    train_ml_model
    
    # 构建并启动服务
    build_and_start
    
    # 显示日志
    show_logs
    
    echo "=================================================="
    echo "       部署完成                                   "
    echo "=================================================="
}

# 执行主函数
main 