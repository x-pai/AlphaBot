import unittest
import pytest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime
import os

from app.services.search_service import SearchService, search_service


class TestSearchService(unittest.TestCase):
    """测试搜索服务"""
    
    def setUp(self):
        """测试前准备"""
        # 模拟设置
        self.mock_settings = {
            "SEARCH_API_ENABLED": True,
            "SEARCH_ENGINE": "serpapi",
            "SERPAPI_API_KEY": "mock_key",
            "SERPAPI_API_BASE_URL": "https://serpapi.com/search",
            "GOOGLE_SEARCH_API_KEY": "mock_google_key",
            "GOOGLE_SEARCH_CX": "mock_cx",
            "GOOGLE_SEARCH_BASE_URL": "https://www.googleapis.com/customsearch/v1",
            "BING_SEARCH_API_KEY": "mock_bing_key",
            "BING_SEARCH_BASE_URL": "https://api.bing.microsoft.com/v7.0/search"
        }
        
        # 创建一个测试搜索服务实例
        self.patcher = patch("app.services.search_service.settings", **self.mock_settings)
        self.mock_settings_obj = self.patcher.start()
        for key, value in self.mock_settings.items():
            setattr(self.mock_settings_obj, key, value)
            
        self.search_service = SearchService()
    
    def tearDown(self):
        """测试后清理"""
        self.patcher.stop()
    
    @patch("app.services.search_service.requests.get")
    async def test_search_serpapi(self, mock_get):
        """测试SerpAPI搜索功能"""
        # 模拟API响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "organic_results": [
                {
                    "title": "测试结果1",
                    "link": "https://example.com/1",
                    "snippet": "这是一个测试结果1"
                },
                {
                    "title": "测试结果2",
                    "link": "https://example.com/2",
                    "snippet": "这是一个测试结果2"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # 执行搜索
        result = await self.search_service.search("测试查询")
        
        # 验证结果
        assert result["success"] is True
        assert result["query"] == "测试查询"
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "测试结果1"
        assert result["results"][0]["link"] == "https://example.com/1"
        assert result["results"][0]["snippet"] == "这是一个测试结果1"
        assert result["results"][0]["source"] == "serpapi"
        
        # 验证API调用
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://serpapi.com/search"
        assert kwargs["params"]["q"] == "测试查询"
        assert kwargs["params"]["api_key"] == "mock_key"
    
    @patch("app.services.search_service.requests.get")
    async def test_search_google(self, mock_get):
        """测试Google搜索功能"""
        # 修改引擎为Google
        self.search_service.search_engine = "googleapi"
        
        # 模拟API响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "Google测试结果1",
                    "link": "https://example.com/g1",
                    "snippet": "这是一个Google测试结果1"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # 执行搜索
        result = await self.search_service.search("Google测试")
        
        # 验证结果
        assert result["success"] is True
        assert result["query"] == "Google测试"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Google测试结果1"
        assert result["results"][0]["source"] == "google"
        
        # 验证API调用
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://www.googleapis.com/customsearch/v1"
        assert kwargs["params"]["q"] == "Google测试"
        assert kwargs["params"]["key"] == "mock_google_key"
        assert kwargs["params"]["cx"] == "mock_cx"
    
    @patch("app.services.search_service.requests.get")
    async def test_search_error(self, mock_get):
        """测试搜索错误处理"""
        # 模拟API错误
        mock_get.side_effect = Exception("API调用失败")
        
        # 执行搜索
        result = await self.search_service.search("错误测试")
        
        # 验证结果
        assert result["success"] is False
        assert "错误" in result["error"]
        assert len(result["results"]) == 0
    
    @patch("app.services.search_service.settings")
    async def test_search_disabled(self, mock_settings):
        """测试禁用搜索API"""
        # 模拟设置
        mock_settings.SEARCH_API_ENABLED = False
        
        # 创建一个禁用API的搜索服务
        disabled_service = SearchService()
        
        # 执行搜索
        result = await disabled_service.search("测试查询")
        
        # 验证结果
        assert result["success"] is False
        assert "未启用" in result["error"]


if __name__ == "__main__":
    unittest.main() 