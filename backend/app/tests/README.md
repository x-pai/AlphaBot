## 如何开始测试

### 测试Web搜索功能
 
要开始测试Web搜索功能，你可以通过以下几种方式：

1. 运行单元测试:
```
cd backend
python -m pytest app/tests/test_search_service.py -v
```

2. 手动测试API端点:
```
curl -X GET "http://localhost:8000/api/v1/search/web?query=NVIDIA股价" -H "Authorization: Bearer 你的令牌"
```

3. 在前端测试:
在AgentChat界面中，向智能助手提问一些需要实时信息的问题，如"查找最近的NVIDIA股票新闻"或"搜索特斯拉最新财报"。

注意：确保已在`.env`文件中配置了相应的搜索引擎API密钥，例如：
```
SEARCH_API_ENABLED=True
SEARCH_ENGINE=serpapi
SERPAPI_API_KEY=你的SerpAPI密钥
```
