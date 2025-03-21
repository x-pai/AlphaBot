# AlphaBot 一键部署脚本
# 作者: BenalexCheung
# 版本: 1.0.0

# 颜色定义
$GREEN = "Green"
$YELLOW = "Yellow"
$RED = "Red"

# 打印带颜色的消息
function Print-Message {
    param ([string]$Message)
    Write-Host "[信息] $Message" -ForegroundColor $GREEN
}

function Print-Warning {
    param ([string]$Message)
    Write-Host "[警告] $Message" -ForegroundColor $YELLOW
}

function Print-Error {
    param ([string]$Message)
    Write-Host "[错误] $Message" -ForegroundColor $RED
}

# 检查 Docker 是否安装
function Check-Docker {
    Print-Message "正在检查 Docker 是否安装..."
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Print-Error "未安装 Docker。请先安装 Docker: https://docs.docker.com/get-docker/"
        exit 1
    }
    Print-Message "Docker 已安装 ✓"

    Print-Message "正在检查 Docker Compose 是否安装..."
    if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        Print-Error "未安装 Docker Compose。请先安装 Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    }
    Print-Message "Docker Compose 已安装 ✓"
}

# 检查环境文件
function Check-EnvFile {
    Print-Message "正在检查环境配置文件..."
    if (-not (Test-Path ".\backend\.env")) {
        Print-Warning "未找到 backend\.env 文件，将从示例文件创建"
        if (Test-Path ".\backend\.env.example") {
            Copy-Item -Path ".\backend\.env.example" -Destination ".\backend\.env"
            Print-Message "已从示例文件创建 .env 文件，请编辑 .\backend\.env 配置您的环境变量"
        } else {
            Print-Error "未找到 .env.example 文件，请手动创建 .env 文件"
            exit 1
        }
    } else {
        Print-Message "环境配置文件已存在 ✓"
    }
}

# 训练机器学习模型
function Train-MLModel {
    Print-Message "正在检查是否需要训练机器学习模型..."
    if (-not (Test-Path ".\backend\models\stock_analysis_model.pkl")) {
        Print-Message "未找到预训练模型，开始训练..."

        # 使用 Docker 运行训练脚本
        docker-compose run --rm backend python train_model.py

        if ($LASTEXITCODE -eq 0) {
            Print-Message "模型训练成功 ✓"
        } else {
            Print-Error "模型训练失败，将使用规则分析模式"
            # 确保 .env 文件中使用规则分析模式
            (Get-Content -Path ".\backend\.env") -replace "DEFAULT_ANALYSIS_MODE=.*", "DEFAULT_ANALYSIS_MODE=`"rule`"" | Set-Content -Path ".\backend\.env"
        }
    } else {
        Print-Message "预训练模型已存在 ✓"
    }
}

# 构建并启动服务
function Build-AndStart {
    Print-Message "正在构建并启动服务..."
    docker-compose down
    docker-compose build
    docker-compose up -d

    if ($LASTEXITCODE -eq 0) {
        Print-Message "服务启动成功 ✓"
        Print-Message "后端API: http://localhost:8000/api/v1/docs"
        Print-Message "前端界面: http://localhost:3000"
    } else {
        Print-Error "服务启动失败，请检查日志"
        exit 1
    }
}

# 显示日志
function Show-Logs {
    $response = Read-Host "是否查看服务日志? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        docker-compose logs -f
    }
}

# 主函数
function Main {
    Write-Host "=================================================="
    Write-Host "       AlphaBot 一键部署脚本                     "
    Write-Host "=================================================="

    # 检查 Docker
    Check-Docker

    # 检查环境文件
    Check-EnvFile

    # 训练机器学习模型
    Train-MLModel

    # 构建并启动服务
    Build-AndStart

    # 显示日志
    Show-Logs

    Write-Host "=================================================="
    Write-Host "       部署完成                                  "
    Write-Host "=================================================="
}

# 执行主函数
Main