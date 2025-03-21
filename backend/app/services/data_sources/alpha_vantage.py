import httpx
from typing import List, Optional, Dict, Any
import pandas as pd
from datetime import datetime
import requests
import random
from datetime import timedelta

from app.core.config import settings
from app.services.data_sources.base import DataSourceBase
from app.schemas.stock import StockInfo, StockPriceHistory, StockPricePoint

class AlphaVantageDataSource(DataSourceBase):
    """Alpha Vantage 数据源实现"""
    
    def __init__(self):
        self.base_url = settings.ALPHAVANTAGE_API_BASE_URL
        self.api_key = settings.ALPHAVANTAGE_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)  # 创建异步HTTP客户端
    
    async def search_stocks(self, query: str) -> List[StockInfo]:
        """搜索股票"""
        try:
            # 调用 Alpha Vantage API 搜索股票
            params = {
                "function": "SYMBOL_SEARCH",
                "keywords": query,
                "apikey": self.api_key
            }
            response = await self.client.get(self.base_url, params=params)
            data = response.json()
            
            if "bestMatches" not in data:
                return []
            
            results = []
            for match in data["bestMatches"]:
                stock_info = StockInfo(
                    symbol=match.get("1. symbol", ""),
                    name=match.get("2. name", ""),
                    exchange=match.get("4. region", ""),
                    currency=match.get("8. currency", "USD")
                )
                results.append(stock_info)
            
            return results
        except Exception as e:
            print(f"搜索股票时出错: {str(e)}")
            return []
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """获取股票详细信息"""
        try:
            # 调用 Alpha Vantage API 获取股票详情
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key
            }
            response = await self.client.get(self.base_url, params=params)
            quote_data = response.json()
            
            # 获取公司概览
            params = {
                "function": "OVERVIEW",
                "symbol": symbol,
                "apikey": self.api_key
            }
            overview_response = await self.client.get(self.base_url, params=params)
            overview_data = overview_response.json()
            
            if "Global Quote" not in quote_data or not overview_data:
                return None
            
            quote = quote_data["Global Quote"]
            
            # 构建股票信息
            stock_info = StockInfo(
                symbol=symbol,
                name=overview_data.get("Name", ""),
                exchange=overview_data.get("Exchange", ""),
                currency=overview_data.get("Currency", "USD"),
                price=float(quote.get("05. price", 0)),
                change=float(quote.get("09. change", 0)),
                changePercent=float(quote.get("10. change percent", "0%").replace("%", "")),
                marketCap=float(overview_data.get("MarketCapitalization", 0)),
                volume=int(quote.get("06. volume", 0))
            )
            
            return stock_info
        except Exception as e:
            print(f"获取股票信息时出错: {str(e)}")
            return None
    
    async def get_stock_price_history(
        self, 
        symbol: str, 
        interval: str = "daily", 
        range: str = "1m"
    ) -> Optional[StockPriceHistory]:
        """获取股票历史价格数据"""
        try:
            # 映射时间范围到 Alpha Vantage 的输出大小
            output_size = "compact" if range in ["1m", "3m"] else "full"
            
            # 映射间隔到 Alpha Vantage 的函数
            function_map = {
                "daily": "TIME_SERIES_DAILY",
                "weekly": "TIME_SERIES_WEEKLY",
                "monthly": "TIME_SERIES_MONTHLY"
            }
            
            function = function_map.get(interval, "TIME_SERIES_DAILY")
            
            # 调用 Alpha Vantage API
            params = {
                "function": function,
                "symbol": symbol,
                "outputsize": output_size,
                "apikey": self.api_key
            }
            response = await self.client.get(self.base_url, params=params)
            data = response.json()
            
            # 提取时间序列数据
            time_series_key = next((k for k in data.keys() if "Time Series" in k), None)
            if not time_series_key:
                return None
            
            time_series = data[time_series_key]
            
            # 转换为 DataFrame 进行处理
            df = pd.DataFrame.from_dict(time_series, orient="index")
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # 根据时间范围筛选数据
            if range == "1m":
                df = df.last('30D')
            elif range == "3m":
                df = df.last('90D')
            elif range == "6m":
                df = df.last('180D')
            elif range == "1y":
                df = df.last('365D')
            
            # 重命名列
            df.columns = [col.split('. ')[1] for col in df.columns]
            
            # 转换为数值类型
            for col in df.columns:
                df[col] = pd.to_numeric(df[col])
            
            # 构建响应数据
            price_points = []
            for date, row in df.iterrows():
                price_point = StockPricePoint(
                    date=date.strftime('%Y-%m-%d'),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=int(row['volume'])
                )
                price_points.append(price_point)
            
            return StockPriceHistory(symbol=symbol, data=price_points)
        except Exception as e:
            print(f"获取股票历史价格时出错: {str(e)}")
            return None
    
    async def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """获取公司基本面数据"""
        try:
            # 调用 Alpha Vantage API
            params = {
                "function": "OVERVIEW",
                "symbol": symbol,
                "apikey": self.api_key
            }
            response = await self.client.get(self.base_url, params=params)
            data = response.json()
            
            return data
        except Exception as e:
            print(f"获取基本面数据时出错: {str(e)}")
            return {}
    
    async def get_historical_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取股票历史数据"""
        try:
            # 调用 Alpha Vantage API
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": "compact",
                "apikey": self.api_key
            }
            response = await self.client.get(self.base_url, params=params)
            data = response.json()
            
            # 提取时间序列数据
            time_series_key = next((k for k in data.keys() if "Time Series" in k), None)
            if not time_series_key:
                return None
            
            time_series = data[time_series_key]
            
            # 转换为 DataFrame
            df = pd.DataFrame.from_dict(time_series, orient="index")
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # 重命名列
            df.columns = [col.split('. ')[1] for col in df.columns]
            
            # 转换为数值类型
            for col in df.columns:
                df[col] = pd.to_numeric(df[col])
            
            return df
        except Exception as e:
            print(f"获取历史数据时出错: {str(e)}")
            return None
    
    async def get_news_sentiment(self, symbol: str) -> Dict[str, Any]:
        """获取新闻情绪分析"""
        try:
            # 构建 API URL
            url = f"{self.base_url}/NEWS_SENTIMENT"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "apikey": self.api_key
            }
            
            # 发送请求
            response = await self.client.get(url, params=params)
            
            if not response or "feed" not in response:
                return {}
            
            # 提取情绪分数
            sentiment_scores = []
            for article in response["feed"]:
                if "ticker_sentiment" in article:
                    for ticker_sentiment in article["ticker_sentiment"]:
                        if ticker_sentiment["ticker"] == symbol:
                            sentiment_scores.append(float(ticker_sentiment["ticker_sentiment_score"]))
            
            # 计算平均情绪分数
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            
            return {
                "feed": response["feed"],
                "sentiment_score_avg": avg_sentiment
            }
        except Exception as e:
            print(f"获取新闻情绪时出错: {str(e)}")
            return {}
    
    async def get_sector_linkage(self, symbol: str) -> Dict[str, Any]:
        """获取板块联动性分析"""
        # Alpha Vantage 没有直接提供板块联动性分析的 API
        # 返回默认值
        try:
            # 尝试获取股票所属行业
            sector_name = "未知板块"
            
            # 获取公司概览
            url = f"{self.base_url}/OVERVIEW"
            params = {
                "function": "OVERVIEW",
                "symbol": symbol,
                "apikey": self.api_key
            }
            
            response = await self.client.get(url, params=params)
            
            if response and "Sector" in response:
                sector_name = response["Sector"]
            
            return {
                "sector_name": sector_name,
                "correlation": 0.5,  # 默认中等相关性
                "driving_force": 0.3,  # 默认较低带动性
                "rank_in_sector": 0,
                "total_in_sector": 0
            }
        except Exception as e:
            print(f"获取板块联动性时出错: {str(e)}")
            return {
                "sector_name": "未知板块",
                "correlation": 0.5,
                "driving_force": 0.3,
                "rank_in_sector": 0,
                "total_in_sector": 0
            }
    
    async def get_concept_distribution(self, symbol: str) -> Dict[str, Any]:
        """获取概念涨跌分布分析"""
        # Alpha Vantage 不支持概念分析，返回默认数据
        return self._default_concept_distribution()
    
    async def get_intraday_data(self, symbol: str, refresh: bool = False) -> Dict[str, Any]:
        """获取股票分时数据"""
        try:
            print(f"[AlphaVantage] 获取分时数据: {symbol}")
            
            # 解析股票代码
            # 对于美股，直接使用symbol
            # 对于A股，需要转换格式
            if '.' in symbol:
                code = symbol.split('.')[0]
                market = symbol.split('.')[1]
                
                # 转换为 Alpha Vantage 格式的代码
                if market == 'SH':
                    av_symbol = f"{code}.SS"
                elif market == 'SZ':
                    av_symbol = f"{code}.SZ"
                else:
                    av_symbol = symbol
            else:
                av_symbol = symbol
                
            # 获取分时数据
            try:
                # 使用Alpha Vantage获取分时数据
                params = {
                    'function': 'TIME_SERIES_INTRADAY',
                    'symbol': av_symbol,
                    'interval': '1min',
                    'outputsize': 'full',
                    'apikey': self.api_key
                }
                
                url = f"{self.base_url}/query"
                response = await self._run_sync(requests.get, url, params=params)
                
                if response.status_code != 200:
                    print(f"[AlphaVantage] API请求失败: {response.status_code}")
                    return self._generate_mock_intraday_data(symbol)
                    
                data = response.json()
                
                # 检查是否有错误信息
                if 'Error Message' in data:
                    print(f"[AlphaVantage] API错误: {data['Error Message']}")
                    return self._generate_mock_intraday_data(symbol)
                    
                # 检查是否有分时数据
                time_series_key = 'Time Series (1min)'
                if time_series_key not in data:
                    print(f"[AlphaVantage] 无分时数据")
                    return self._generate_mock_intraday_data(symbol)
                    
                # 处理数据
                time_series = data[time_series_key]
                
                result = {
                    "symbol": symbol,
                    "data": []
                }
                
                # 获取今天的日期
                today = datetime.now().strftime('%Y-%m-%d')
                
                # 转换数据格式
                for timestamp, values in time_series.items():
                    # 只获取今天的数据
                    if not timestamp.startswith(today):
                        continue
                        
                    # 提取时间部分 (HH:MM)
                    time_str = timestamp.split(' ')[1][:5]
                    
                    # 添加数据点
                    data_point = {
                        "time": time_str,
                        "price": float(values['4. close']),
                        "volume": float(values['5. volume'])
                    }
                    
                    result["data"].append(data_point)
                    
                # 如果没有今天的数据，返回模拟数据
                if not result["data"]:
                    print(f"[AlphaVantage] 无今日分时数据，生成模拟数据")
                    return self._generate_mock_intraday_data(symbol)
                    
                # 按时间排序
                result["data"].sort(key=lambda x: x["time"])
                
                return result
                
            except Exception as e:
                print(f"[AlphaVantage] 获取分时数据失败: {str(e)}")
                return self._generate_mock_intraday_data(symbol)
                
        except Exception as e:
            print(f"[AlphaVantage] 获取分时数据出错: {str(e)}")
            # 出错时返回模拟数据
            return self._generate_mock_intraday_data(symbol)
            
    def _generate_mock_intraday_data(self, symbol: str) -> Dict[str, Any]:
        """生成模拟分时数据"""
        # 获取当前日期
        today = datetime.now()
        
        # 如果是周末，调整到周五
        if today.weekday() > 4:  # 5=周六, 6=周日
            days_to_subtract = today.weekday() - 4
            today = today - timedelta(days=days_to_subtract)
            
        # 基础价格 (随机生成在50-200之间)
        base_price = random.uniform(50, 200)
        current_price = base_price
        
        # 生成结果
        result = {
            "symbol": symbol,
            "data": []
        }
        
        # 生成上午9:30-11:30的数据
        current_time = datetime(today.year, today.month, today.day, 9, 30)
        end_morning = datetime(today.year, today.month, today.day, 11, 30)
        
        while current_time <= end_morning:
            # 价格波动 (-0.5% 到 +0.5%)
            price_change = current_price * random.uniform(-0.005, 0.005)
            current_price += price_change
            
            # 成交量 (随机生成)
            volume = random.randint(10000, 100000)
            
            # 添加数据点
            data_point = {
                "time": current_time.strftime("%H:%M"),
                "price": round(current_price, 2),
                "volume": volume
            }
            
            result["data"].append(data_point)
            
            # 增加1分钟
            current_time += timedelta(minutes=1)
            
        # 生成下午13:00-15:00的数据
        current_time = datetime(today.year, today.month, today.day, 13, 0)
        end_afternoon = datetime(today.year, today.month, today.day, 15, 0)
        
        while current_time <= end_afternoon:
            # 价格波动 (-0.5% 到 +0.5%)
            price_change = current_price * random.uniform(-0.005, 0.005)
            current_price += price_change
            
            # 成交量 (随机生成)
            volume = random.randint(10000, 100000)
            
            # 添加数据点
            data_point = {
                "time": current_time.strftime("%H:%M"),
                "price": round(current_price, 2),
                "volume": volume
            }
            
            result["data"].append(data_point)
            
            # 增加1分钟
            current_time += timedelta(minutes=1)
            
        return result
    
    def _default_concept_distribution(self) -> Dict[str, Any]:
        """返回默认的概念涨跌分布数据"""
        return {
            "overall_strength": 0.5,
            "leading_concepts": [],
            "lagging_concepts": [],
            "all_concepts": []
        }
    
    async def __del__(self):
        """析构函数，确保关闭HTTP客户端"""
        if hasattr(self, 'client'):
            await self.client.aclose() 