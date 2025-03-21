# 后端

后端 API 服务，使用 Python FastAPI 构建。

## 功能特点

- **多数据源支持**：支持 Alpha Vantage、Tushare 和 AKShare 三种数据源，可以获取全球和中国股票市场数据
- **多种分析模式**：支持三种股票分析模式
  - 规则计算分析：基于技术指标和基本面数据的规则计算
  - 机器学习模型分析：使用训练好的机器学习模型进行预测
  - 大语言模型分析：利用 OpenAI API 进行深度分析
- **股票搜索**：支持按名称或代码搜索股票
- **股票信息**：获取股票的基本信息，如价格、市值等
- **历史数据**：获取股票的历史价格和交易量数据
- **技术分析**：计算常用技术指标，如移动平均线、RSI、MACD 等
- **AI 分析**：提供股票分析和投资建议

## 技术栈

- **FastAPI**：高性能 API 框架
- **Pandas**：数据处理
- **SQLAlchemy**：数据库 ORM
- **Pydantic**：数据验证
- **OpenAI API**：大语言模型分析
- **机器学习库**：XGBoost、LightGBM 等

## 安装

1. 克隆仓库
```bash
git clone https://github.com/x-pai/ai-stock-assistant.git
cd ai-stock-assistant/backend
```

2. 创建并激活虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

2. 安装依赖

创建并激活虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
创建 `.env` 文件并设置以下变量：
```
# 应用配置
APP_NAME=AlphaBot
API_V1_STR=/api/v1

# 数据源配置
DEFAULT_DATA_SOURCE=alphavantage  # 可选值: alphavantage, tushare, akshare

# Alpha Vantage API 配置
ALPHA_VANTAGE_API_KEY=your_api_key
ALPHA_VANTAGE_API_URL=https://www.alphavantage.co/query

# Tushare API 配置
TUSHARE_API_TOKEN=your_api_token
TUSHARE_API_URL=http://api.tushare.pro

# AKShare 配置
AKSHARE_CONFIG=default

# 数据库配置
DATABASE_URL=sqlite:///./stock_app.db

# 安全配置
SECRET_KEY=your_secret_key

# AI 分析配置
DEFAULT_ANALYSIS_MODE=rule  # 可选值: rule, ml, llm
AI_MODEL_PATH=./models/stock_analysis_model.pkl

# OpenAI 配置
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_API_BASE=https://api.openai.com/v1

# CORS 配置
CORS_ORIGINS=["http://localhost:3000"]
```

4. 训练机器学习模型（可选）
```bash
python train_model.py
```

5. 启动服务
```bash
python run.py
# 或
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/api/v1/docs 查看 Swagger API 文档

## API 端点

### 股票搜索

```
GET /api/v1/stocks/search?q={query}&data_source={data_source}
```

参数：
- `q`：搜索关键词（必填）
- `data_source`：数据源（可选，默认使用 DEFAULT_DATA_SOURCE 环境变量）

响应：
```json
[
  {
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "type": "股票",
    "region": "美国"
  },
  ...
]
```

### 股票信息

```
GET /api/v1/stocks/{symbol}?data_source={data_source}
```

参数：
- `symbol`：股票代码（必填）
- `data_source`：数据源（可选）

响应：
```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "price": 150.25,
  "change": 2.5,
  "changePercent": 1.67,
  "marketCap": 2500000000000,
  "peRatio": 28.5,
  "dividend": 0.82,
  "volume": 75000000
}
```

### 股票历史数据

```
GET /api/v1/stocks/{symbol}/history?interval={interval}&data_source={data_source}
```

参数：
- `symbol`：股票代码（必填）
- `interval`：时间间隔（可选，默认为 "daily"，可选值：daily, weekly, monthly）
- `data_source`：数据源（可选）

响应：
```json
[
  {
    "date": "2023-01-01",
    "open": 148.5,
    "high": 151.2,
    "low": 147.8,
    "close": 150.25,
    "volume": 75000000
  },
  ...
]
```

### 股票 AI 分析

```
GET /api/v1/stocks/{symbol}/analysis?data_source={data_source}&analysis_mode={analysis_mode}
```

参数：
- `symbol`：股票代码（必填）
- `data_source`：数据源（可选）
- `analysis_mode`：分析模式（可选，默认使用 DEFAULT_ANALYSIS_MODE 环境变量，可选值：rule, ml, llm）

响应：
```json
{
  "summary": "Apple Inc.目前交易价格为150.25，较前一交易日1.67%。基于技术分析和市场情绪，股票当前呈现积极态势。风险水平评估为中等。",
  "sentiment": "positive",
  "keyPoints": [
    "价格高于50日均线，显示上升趋势",
    "RSI为65.2，处于中性区间",
    "市盈率为28.5，相对较高",
    "股息收益率为0.55%"
  ],
  "recommendation": "考虑买入或持有。技术指标和市场情绪都相对积极。",
  "riskLevel": "medium"
}
```

## 多数据源支持

系统支持三种数据源：

1. **Alpha Vantage**：提供全球股票市场数据，包括美股、港股等
2. **Tushare**：专注于中国股票市场数据，包括 A 股、港股等
3. **AKShare**：开源财经数据接口，提供中国和全球市场数据

### 配置默认数据源

在 `.env` 文件中设置默认数据源：

```
DEFAULT_DATA_SOURCE=alphavantage  # 可选值: alphavantage, tushare, akshare
```

### 在 API 请求中指定数据源

在 API 请求中可以通过 `data_source` 参数指定使用的数据源：

```
GET /api/v1/stocks/search?q=apple&data_source=alphavantage
GET /api/v1/stocks/000001.SZ?data_source=tushare
GET /api/v1/stocks/600000.SH/history?data_source=akshare
```

## 多种分析模式

系统支持三种股票分析模式：

1. **规则计算分析（rule）**：基于技术指标和基本面数据的规则计算，不依赖外部模型
2. **机器学习模型分析（ml）**：使用训练好的机器学习模型进行预测，需要先运行 `train_model.py` 训练模型
3. **大语言模型分析（llm）**：利用 OpenAI API 进行深度分析，需要配置 OpenAI API 密钥

### 配置默认分析模式

在 `.env` 文件中设置默认分析模式：

```
DEFAULT_ANALYSIS_MODE=rule  # 可选值: rule, ml, llm
```

### 在 API 请求中指定分析模式

在 API 请求中可以通过 `analysis_mode` 参数指定使用的分析模式：

```
GET /api/v1/stocks/AAPL/analysis?analysis_mode=rule
GET /api/v1/stocks/000001.SZ/analysis?analysis_mode=ml
GET /api/v1/stocks/600000.SH/analysis?analysis_mode=llm
```

### 分析模式特点

- **规则计算分析（rule）**：
  - 速度快，不依赖外部服务
  - 基于预设规则和阈值
  - 适合基本的技术分析

- **机器学习模型分析（ml）**：
  - 基于历史数据训练的模型
  - 可以预测趋势、风险和情绪
  - 需要先训练模型

- **大语言模型分析（llm）**：
  - 提供最全面和深入的分析
  - 考虑多种因素，包括新闻情绪
  - 需要 OpenAI API 密钥
  - 分析质量最高，但速度较慢

## 开发指南

### 项目结构
```
.
├── app/                    # 主应用目录
│   ├── api/               # API 路由
│   ├── core/              # 核心配置
│   ├── db/                # 数据库
│   ├── models/            # 数据模型
│   ├── schemas/           # 数据验证
│   ├── services/          # 业务逻辑
│   └── utils/             # 工具函数
├── tests/                 # 测试用例
├── models/                # ML模型
├── Dockerfile             # 容器配置
└── requirements.txt       # 依赖清单
```

### 添加新数据源
1. 在 `app/services/data_sources/` 创建新数据源类
2. 实现标准数据接口
3. 在配置中注册数据源

### 开发新分析模式
1. 在 `app/services/analysis/` 添加分析类
2. 实现分析接口
3. 在配置中注册分析模式

### 运行测试
```bash
pytest tests/
```

## 部署说明

### Docker 部署
```bash
docker build -t ai-stock-assistant .
docker run -p 8000:8000 ai-stock-assistant
```
