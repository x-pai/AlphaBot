import requests
import json
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.middleware.logging import logger
from datetime import datetime

class SearchService:
    """搜索服务，支持多种搜索引擎"""
    
    def __init__(self):
        self.search_engine = settings.SEARCH_ENGINE
        self.is_enabled = settings.SEARCH_API_ENABLED
        
        # 初始化可用的搜索引擎配置
        self.search_engines = {
            "serpapi": {
                "api_key": settings.SERPAPI_API_KEY,
                "base_url": settings.SERPAPI_API_BASE_URL,
                "enabled": bool(settings.SERPAPI_API_KEY),
            },
            "googleapi": {
                "api_key": settings.GOOGLE_SEARCH_API_KEY,
                "cx": settings.GOOGLE_SEARCH_CX,
                "base_url": settings.GOOGLE_SEARCH_BASE_URL,
                "enabled": bool(settings.GOOGLE_SEARCH_API_KEY and settings.GOOGLE_SEARCH_CX),
            },
            "bingapi": {
                "api_key": settings.BING_SEARCH_API_KEY,
                "base_url": settings.BING_SEARCH_BASE_URL,
                "enabled": bool(settings.BING_SEARCH_API_KEY),
            }
        }
        
        # 记录初始化信息
        logger.info(f"搜索服务初始化: 引擎={self.search_engine}, 已启用={self.is_enabled}")
        
    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """统一搜索接口
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            
        Returns:
            包含搜索结果的字典
        """
        if not self.is_enabled:
            logger.warning("搜索API未启用")
            return self._create_error_response("搜索API未启用")
        
        logger.info(f"使用搜索引擎: {self.search_engine}, 查询: {query}")
        # 选择搜索引擎
        if self.search_engine == "serpapi" and self.search_engines["serpapi"]["enabled"]:
            return await self._search_serpapi(query, limit)
        elif self.search_engine == "googleapi" and self.search_engines["googleapi"]["enabled"]:
            return await self._search_google(query, limit)
        elif self.search_engine == "bingapi" and self.search_engines["bingapi"]["enabled"]:
            return await self._search_bing(query, limit)
        else:
            # 尝试找到一个可用的搜索引擎
            for engine, config in self.search_engines.items():
                if config["enabled"]:
                    logger.info(f"使用后备搜索引擎: {engine}")
                    self.search_engine = engine
                    return await self.search(query, limit)
            
            # 没有可用的搜索引擎
            logger.error("没有配置可用的搜索引擎")
            return self._create_error_response("没有配置可用的搜索引擎")
        
    async def _search_serpapi(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """使用SerpAPI进行搜索
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            
        Returns:
            包含搜索结果的字典
        """
        try:
            config = self.search_engines["serpapi"]
            params = {
                "q": query,
                "num": limit,
                "api_key": config["api_key"],
                "engine": "google"
            }
            
            response = requests.get(config["base_url"], params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("organic_results", [])[:limit]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "serpapi"
                })
            
            return self._create_success_response(query, results)
        except Exception as e:
            logger.error(f"SerpAPI搜索错误: {str(e)}")
            return self._create_error_response(f"SerpAPI搜索错误: {str(e)}")
    
    async def _search_google(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """使用Google Custom Search API进行搜索
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            
        Returns:
            包含搜索结果的字典
        """
        try:
            config = self.search_engines["googleapi"]
            params = {
                "q": query,
                "key": config["api_key"],
                "cx": config["cx"],
                "num": min(limit, 10)  # Google API最多返回10个结果
            }
            
            response = requests.get(config["base_url"], params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("items", [])[:limit]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "google"
                })
            
            return self._create_success_response(query, results)
        except Exception as e:
            logger.error(f"Google API搜索错误: {str(e)}")
            return self._create_error_response(f"Google API搜索错误: {str(e)}")
    
    async def _search_bing(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """使用Bing Search API进行搜索
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            
        Returns:
            包含搜索结果的字典
        """
        try:
            config = self.search_engines["bingapi"]
            headers = {"Ocp-Apim-Subscription-Key": config["api_key"]}
            params = {
                "q": query,
                "count": limit,
                "responseFilter": "Webpages"
            }
            
            response = requests.get(config["base_url"], headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("webPages", {}).get("value", [])[:limit]:
                results.append({
                    "title": item.get("name", ""),
                    "link": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "bing"
                })
            
            return self._create_success_response(query, results)
        except Exception as e:
            logger.error(f"Bing API搜索错误: {str(e)}")
            return self._create_error_response(f"Bing API搜索错误: {str(e)}")
    
    def _create_success_response(self, query: str, results: List[Dict[str, str]]) -> Dict[str, Any]:
        """创建成功的响应对象"""
        return {
            "success": True,
            "query": query,
            "results": results,
            "result_count": len(results),
            "timestamp": datetime.now().isoformat(),
            "engine": self.search_engine
        }
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """创建错误的响应对象"""
        return {
            "success": False,
            "error": error_message,
            "results": [],
            "result_count": 0,
            "timestamp": datetime.now().isoformat(),
            "engine": self.search_engine
        }
        
# 创建全局单例
search_service = SearchService() 