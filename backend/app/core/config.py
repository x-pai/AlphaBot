from pydantic_settings import BaseSettings
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
    
    # 基础目录
    BASE_DIR: str = os.getenv("BASE_DIR", "./") 
    
    # 数据源配置
    # 可选值: "alphavantage", "tushare", "akshare", "hk_stock"
    DEFAULT_DATA_SOURCE: str = os.getenv("DEFAULT_DATA_SOURCE", "alphavantage")
    
    # Alpha Vantage API配置
    ALPHAVANTAGE_API_BASE_URL: str = os.getenv("ALPHAVANTAGE_API_BASE_URL", "https://www.alphavantage.co/query")
    ALPHAVANTAGE_API_KEY: str = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
    
    # Tushare API配置
    TUSHARE_API_TOKEN: str = os.getenv("TUSHARE_API_TOKEN", "")
    
    # AKShare配置
    # AKShare 不需要 API 密钥，但可以配置一些参数
    AKSHARE_USE_PROXY: bool = os.getenv("AKSHARE_USE_PROXY", "False").lower() == "true"
    AKSHARE_PROXY_URL: str = os.getenv("AKSHARE_PROXY_URL", "")
    
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
    
    # AI分析配置
    # 可选值: "rule", "ml", "llm"
    DEFAULT_ANALYSIS_MODE: str = os.getenv("DEFAULT_ANALYSIS_MODE", "rule")
    
    # AI模型配置
    AI_MODEL_PATH: str = os.getenv("AI_MODEL_PATH", "./models/stock_analysis_model.pkl")
    
    # OpenAI配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "1000"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局设置对象
settings = Settings() 