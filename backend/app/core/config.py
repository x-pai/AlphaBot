from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from dotenv import load_dotenv
from typing import List, Literal

# 加载环境变量
load_dotenv()


class Settings(BaseSettings):
    """应用配置设置"""
    
    # 应用信息
    APP_NAME: str = "AI Stock Assistant API"
    API_V1_STR: str = "/api/v1"
    APP_PUBLIC_BASE_URL: str = os.getenv("APP_PUBLIC_BASE_URL", "")
    APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "Asia/Shanghai")
    APP_CIPHER_KEY_MATERIAL: str = os.getenv("APP_CIPHER_KEY_MATERIAL", "")
    
    # 基础目录
    BASE_DIR: str = os.getenv("BASE_DIR", "./") 
    
    # 数据源配置
    # 可选值: "alphavantage", "tushare", "akshare", "hk_stock", "tdx"
    DEFAULT_DATA_SOURCE: str = os.getenv("DEFAULT_DATA_SOURCE", "alphavantage")
    # 市场域数据源：默认源 + 按数据集绑定（JSON，如 {"pools":"eastmoney","quotes":"xgb"}）
    DEFAULT_MARKET_DATA_SOURCE: str = os.getenv("DEFAULT_MARKET_DATA_SOURCE", "xgb")
    MARKET_DATA_BINDINGS: str = os.getenv("MARKET_DATA_BINDINGS", "")
    # 官方 SDK 独立于旧 HTTP TDX 股票源；Key 由私密配置注入子进程临时 INI。
    TDXAIDATA_TOKEN: SecretStr = SecretStr(os.getenv("TDXAIDATA_TOKEN", ""))
    TDXAIDATA_LIB_DIR: str = os.getenv("TDXAIDATA_LIB_DIR", "")
    TDXAIDATA_TIMEOUT: float = float(os.getenv("TDXAIDATA_TIMEOUT", "30"))
    TDXAIDATA_MAX_PENDING: int = int(os.getenv("TDXAIDATA_MAX_PENDING", "8"))
    TDXAIDATA_MAX_SYMBOLS: int = int(os.getenv("TDXAIDATA_MAX_SYMBOLS", "100"))
    XGB_FLASH_API_BASE: str = os.getenv("XGB_FLASH_API_BASE", "")
    XGB_DDC_MARKET_API_BASE: str = os.getenv("XGB_DDC_MARKET_API_BASE", "")
    XGB_TREND_API_BASE: str = os.getenv("XGB_TREND_API_BASE", "")
    XGB_REFERER: str = os.getenv("XGB_REFERER", "")
    
    # Alpha Vantage API配置
    ALPHAVANTAGE_API_BASE_URL: str = os.getenv("ALPHAVANTAGE_API_BASE_URL", "https://www.alphavantage.co/query")
    ALPHAVANTAGE_API_KEY: str = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
    
    # Tushare API配置
    TUSHARE_API_TOKEN: str = os.getenv("TUSHARE_API_TOKEN", "")
    
    # AKShare配置
    # AKShare 不需要 API 密钥，但可以配置一些参数
    AKSHARE_USE_PROXY: bool = os.getenv("AKSHARE_USE_PROXY", "False").lower() == "true"
    AKSHARE_PROXY_URL: str = os.getenv("AKSHARE_PROXY_URL", "")

    # 雪球配置（用于AKShare的部分接口）
    XUEQIU_TOKEN: str = os.getenv("XUEQIU_TOKEN", "")

    # TDX 配置
    TDX_API_BASE_URL: str = os.getenv("TDX_API_BASE_URL", "")
    TDX_TIMEOUT: float = float(os.getenv("TDX_TIMEOUT", "10"))
    
    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./stock_assistant.db")
    
    # 搜索API配置
    SEARCH_API_ENABLED: bool = os.getenv("SEARCH_API_ENABLED", "True").lower() == "true"
    SEARCH_ENGINE: str = os.getenv("SEARCH_ENGINE", "serpapi") # 可选: serpapi, googleapi, bingapi
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    SERPAPI_API_BASE_URL: str = os.getenv("SERPAPI_API_BASE_URL", "https://serpapi.com/search")
    GOOGLE_SEARCH_API_KEY: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_CX: str = os.getenv("GOOGLE_SEARCH_CX", "")
    GOOGLE_SEARCH_BASE_URL: str = os.getenv("GOOGLE_SEARCH_BASE_URL", "https://www.googleapis.com/customsearch/v1")
    BING_SEARCH_API_KEY: str = os.getenv("BING_SEARCH_API_KEY", "")
    BING_SEARCH_BASE_URL: str = os.getenv("BING_SEARCH_BASE_URL", "https://api.bing.microsoft.com/v7.0/search")
    
    # CORS配置 - 允许本地开发和Docker环境
    CORS_ORIGINS: list = [
        "http://localhost:3000",  # 本地开发环境
        "http://localhost:8000",  # 本地后端
        "http://frontend:3000",   # Docker环境中的前端服务
        "http://backend:8000",    # Docker环境中的后端服务
        "*",                      # 允许所有来源（仅用于测试，生产环境应移除）
    ]
    
    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-for-development-only")
    
    # AI分析配置（Phase 5 AnalysisModeRegistry）
    # 可选值: "rule", "ml", "llm"
    DEFAULT_ANALYSIS_MODE: str = os.getenv("DEFAULT_ANALYSIS_MODE", "rule")
    # Agent 工具白名单：逗号分隔，空则全部启用（Phase 5 ToolRegistry）
    ENABLED_AGENT_TOOLS: str = os.getenv("ENABLED_AGENT_TOOLS", "")
    
    # AI模型配置（传统本地模型）
    AI_MODEL_PATH: str = os.getenv("AI_MODEL_PATH", "./models/stock_analysis_model.pkl")

    # LLM 配置（LiteLLM 统一接口，无 OpenAI 兼容层）
    # 模型格式：provider/model_name，如 openai/gpt-4o-mini、deepseek/deepseek-chat
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1000"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    # 逗号分隔的可用模型列表，供前端/API 切换
    LLM_AVAILABLE_MODELS: str = os.getenv("LLM_AVAILABLE_MODELS", "")

    # 可选：多 profile LLM（为不同角色预留，未配置时回退到上面的默认值）
    LLM_DEFAULT_MODEL: str | None = os.getenv("LLM_DEFAULT_MODEL")
    LLM_DEFAULT_API_BASE: str | None = os.getenv("LLM_DEFAULT_API_BASE")
    LLM_DEFAULT_API_KEY: str | None = os.getenv("LLM_DEFAULT_API_KEY")
    LLM_DEFAULT_MAX_TOKENS: int = int(os.getenv("LLM_DEFAULT_MAX_TOKENS", "0"))
    LLM_DEFAULT_TEMPERATURE: float = float(os.getenv("LLM_DEFAULT_TEMPERATURE", "0"))

    LLM_RESEARCH_MODEL: str | None = os.getenv("LLM_RESEARCH_MODEL")
    LLM_RESEARCH_API_BASE: str | None = os.getenv("LLM_RESEARCH_API_BASE")
    LLM_RESEARCH_API_KEY: str | None = os.getenv("LLM_RESEARCH_API_KEY")
    LLM_RESEARCH_MAX_TOKENS: int = int(os.getenv("LLM_RESEARCH_MAX_TOKENS", "0"))
    LLM_RESEARCH_TEMPERATURE: float = float(os.getenv("LLM_RESEARCH_TEMPERATURE", "0"))

    LLM_RISK_MODEL: str | None = os.getenv("LLM_RISK_MODEL")
    LLM_RISK_API_BASE: str | None = os.getenv("LLM_RISK_API_BASE")
    LLM_RISK_API_KEY: str | None = os.getenv("LLM_RISK_API_KEY")
    LLM_RISK_MAX_TOKENS: int = int(os.getenv("LLM_RISK_MAX_TOKENS", "0"))
    LLM_RISK_TEMPERATURE: float = float(os.getenv("LLM_RISK_TEMPERATURE", "0"))
    AGENT_MAX_TOOL_LOOPS: int = int(os.getenv("AGENT_MAX_TOOL_LOOPS", "20"))
    AGENT_COMPOSE_MAX_TOKENS: int = int(os.getenv("AGENT_COMPOSE_MAX_TOKENS", "0"))
    AUTOMATION_LLM_MAX_TOKENS: int = int(os.getenv("AUTOMATION_LLM_MAX_TOKENS", "2000"))
    AUTOMATION_COMPOSE_MAX_TOKENS: int = int(os.getenv("AUTOMATION_COMPOSE_MAX_TOKENS", "6000"))

    # 长期记忆（向量库 Chroma）
    CHROMA_PERSIST_PATH: str = os.getenv("CHROMA_PERSIST_PATH", "./data/chroma")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    # Embedding 独立 provider（可选，未配置时回退到 LLM_API_*）
    EMBEDDING_API_BASE: str = os.getenv("EMBEDDING_API_BASE", "")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    
    # 请求频率限制配置
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    # 默认限制：每分钟60个请求
    RATE_LIMIT_DEFAULT_MINUTE: int = int(os.getenv("RATE_LIMIT_DEFAULT_MINUTE", "60"))
    # 搜索API限制：每分钟30个请求
    RATE_LIMIT_SEARCH_MINUTE: int = int(os.getenv("RATE_LIMIT_SEARCH_MINUTE", "30"))
    # 股票详情API限制：每分钟20个请求
    RATE_LIMIT_STOCK_INFO_MINUTE: int = int(os.getenv("RATE_LIMIT_STOCK_INFO_MINUTE", "20"))
    # AI分析API限制：每分钟10个请求
    RATE_LIMIT_AI_ANALYSIS_MINUTE: int = int(os.getenv("RATE_LIMIT_AI_ANALYSIS_MINUTE", "10"))
    # 后台任务API限制：每分钟5个请求
    RATE_LIMIT_TASK_MINUTE: int = int(os.getenv("RATE_LIMIT_TASK_MINUTE", "5"))
    
    # Celery配置
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 600  # 10分钟任务超时
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = 200  # 防止内存泄漏
    
    # 消息渠道 / 系统共用机器人：凭证仅保存在服务端。
    # QQ：WebSocket，无需公网回调。
    QQ_BOT_ENABLED: bool = False
    QQ_BOT_APP_ID: str = ""
    QQ_BOT_APP_SECRET: SecretStr = SecretStr("")
    QQ_BOT_LOCK_PATH: str = "/tmp/alphabot-qq.lock"

    # Telegram：默认长轮询；配置 webhook secret 后使用回调。
    TELEGRAM_ENABLED: bool = True
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET: str = ""

    # 飞书：事件回调。
    FEISHU_ENABLED: bool = True
    FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
    FEISHU_API_BASE: str = os.getenv("FEISHU_API_BASE", "https://open.feishu.cn")
    FEISHU_VERIFICATION_TOKEN: str = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
    FEISHU_ENCRYPT_KEY: str = os.getenv("FEISHU_ENCRYPT_KEY", "")

    # 自定义 Webhook 推送：具体地址由个人渠道管理维护。
    WEBHOOK_ENABLED: bool = True

    # 外部 MCP / TrendRadar 等 HTTP 接入（可选）
    # TrendRadar MCP 的 URL / API Key 已迁移到 app/config/mcp_servers.yml，
    # 由 McpHostRegistry 通过环境变量占位展开，不再在 Settings 中单独维护。

    # World Cup / Polymarket 配置
    WORLDCUP_POLYMARKET_ENABLED: bool = os.getenv("WORLDCUP_POLYMARKET_ENABLED", "True").lower() == "true"
    WORLDCUP_POLYMARKET_API_BASE: str = os.getenv("WORLDCUP_POLYMARKET_API_BASE", "https://gamma-api.polymarket.com")
    WORLDCUP_POLYMARKET_LIMIT: int = int(os.getenv("WORLDCUP_POLYMARKET_LIMIT", "500"))
    WORLDCUP_POLYMARKET_USE_PROXY: bool = os.getenv("WORLDCUP_POLYMARKET_USE_PROXY", "False").lower() == "true"
    WORLDCUP_POLYMARKET_PROXY_URL: str = os.getenv("WORLDCUP_POLYMARKET_PROXY_URL", "")
    WORLDCUP_SCHEDULE_API_BASE: str = os.getenv("WORLDCUP_SCHEDULE_API_BASE", "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world")
    WORLDCUP_SCHEDULE_START_DATE: str = os.getenv("WORLDCUP_SCHEDULE_START_DATE", "2026-06-11")
    WORLDCUP_SCHEDULE_END_DATE: str = os.getenv("WORLDCUP_SCHEDULE_END_DATE", "2026-07-19")
    WORLDCUP_SCHEDULE_CACHE_SECONDS: int = int(os.getenv("WORLDCUP_SCHEDULE_CACHE_SECONDS", "300"))
    WORLDCUP_API_FOOTBALL_ENABLED: bool = os.getenv("WORLDCUP_API_FOOTBALL_ENABLED", "False").lower() == "true"
    WORLDCUP_API_FOOTBALL_BASE_URL: str = os.getenv("WORLDCUP_API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io")
    WORLDCUP_API_FOOTBALL_KEY: str = os.getenv("WORLDCUP_API_FOOTBALL_KEY", "")
    WORLDCUP_API_FOOTBALL_HOST: str = os.getenv("WORLDCUP_API_FOOTBALL_HOST", "v3.football.api-sports.io")
    WORLDCUP_API_FOOTBALL_TIMEOUT: float = float(os.getenv("WORLDCUP_API_FOOTBALL_TIMEOUT", "10"))
    WORLDCUP_API_FOOTBALL_CACHE_SECONDS: int = int(os.getenv("WORLDCUP_API_FOOTBALL_CACHE_SECONDS", "21600"))
    WORLDCUP_ODDS_API_ENABLED: bool = os.getenv("WORLDCUP_ODDS_API_ENABLED", "False").lower() == "true"
    WORLDCUP_ODDS_API_BASE_URL: str = os.getenv("WORLDCUP_ODDS_API_BASE_URL", "https://api.the-odds-api.com/v4")
    WORLDCUP_ODDS_API_KEY: str = os.getenv("WORLDCUP_ODDS_API_KEY", "")
    WORLDCUP_ODDS_API_SPORT: str = os.getenv("WORLDCUP_ODDS_API_SPORT", "soccer_fifa_world_cup")
    WORLDCUP_ODDS_API_REGIONS: str = os.getenv("WORLDCUP_ODDS_API_REGIONS", "eu,uk,us")
    WORLDCUP_ODDS_API_BOOKMAKERS: str = os.getenv("WORLDCUP_ODDS_API_BOOKMAKERS", "")
    WORLDCUP_ODDS_API_CACHE_SECONDS: int = int(os.getenv("WORLDCUP_ODDS_API_CACHE_SECONDS", "300"))
    WORLDCUP_ODDS_API_TIMEOUT: float = float(os.getenv("WORLDCUP_ODDS_API_TIMEOUT", "10"))
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

# 创建全局设置对象
settings = Settings() 
