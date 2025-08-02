import akshare as ak
from typing import List, Optional, Dict, Any
import pandas as pd
from datetime import datetime, timedelta
import re
import asyncio
from functools import partial

from app.core.config import settings
from app.services.data_sources.base import DataSourceBase
from app.schemas.stock import StockInfo, StockPriceHistory, StockPricePoint

class HKStockDataSource(DataSourceBase):
    """港股数据源实现"""
    
    def __init__(self):
        # 配置代理（如果需要）
        # AKShare 不直接支持代理设置，需要通过环境变量或系统代理
        if settings.AKSHARE_USE_PROXY and settings.AKSHARE_PROXY_URL:
            import os
            # 设置环境变量来配置代理
            os.environ['HTTP_PROXY'] = settings.AKSHARE_PROXY_URL
            os.environ['HTTPS_PROXY'] = settings.AKSHARE_PROXY_URL
    
    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        return await asyncio.to_thread(func, *args, **kwargs)
    
    async def search_stocks(self, query: str) -> List[StockInfo]:
        print(f"搜索港股: {query}")
        """搜索港股"""
        try:
            # 获取港股股票列表
            stock_info_hk_df = await self._run_sync(ak.stock_hk_spot_em)
            
            # 过滤匹配的股票
            filtered_stocks = stock_info_hk_df[
                stock_info_hk_df['代码'].str.contains(query) | 
                stock_info_hk_df['名称'].str.contains(query)
            ]
            
            results = []
            for _, row in filtered_stocks.iterrows():
                stock_info = StockInfo(
                    symbol=f"{row['代码']}.HK",
                    name=row['名称'],
                    exchange="香港联合交易所",
                    currency='HKD'
                )
                results.append(stock_info)
            
            return results[:10]  # 限制返回数量
        except Exception as e:
            print(f"搜索港股时出错: {str(e)}")
            return []
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """获取港股详细信息"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return None
            
            code = code_match.group(1)
            
            # 获取实时行情
            df = await self._run_sync(ak.stock_hk_spot_em)
            df = df[df['代码'] == code]
            
            if df.empty:
                return None
            
            row = df.iloc[0]
            
            # 计算涨跌幅
            price = float(row['最新价']) if not pd.isna(row['最新价']) else 0.0
            change = float(row['涨跌额']) if not pd.isna(row['涨跌额']) else 0.0
            change_percent = float(row['涨跌幅']) if not pd.isna(row['涨跌幅']) else 0.0
            
            # 获取市值（亿港元转为港元）
            market_cap = float(row['总市值']) * 100000000 if '总市值' in row and not pd.isna(row['总市值']) else 0
            
            # 获取成交量
            volume = int(float(row['成交量'])) if '成交量' in row and not pd.isna(row['成交量']) else 0
            
            stock_info = StockInfo(
                symbol=symbol,
                name=row['名称'],
                exchange="香港联合交易所",
                currency='HKD',
                price=price,
                change=change,
                changePercent=change_percent,
                marketCap=market_cap,
                volume=volume
            )
            return stock_info
        except Exception as e:
            print(f"获取港股信息时出错: {str(e)}")
            return None
    
    async def get_stock_price_history(
        self, 
        symbol: str, 
        interval: str = "daily", 
        range: str = "1m"
    ) -> Optional[StockPriceHistory]:
        """获取港股历史价格数据"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return None
            
            code = code_match.group(1)
            
            # 计算开始日期
            end_date = datetime.now()
            
            if range == "1m":
                start_date = end_date - timedelta(days=30)
            elif range == "3m":
                start_date = end_date - timedelta(days=90)
            elif range == "6m":
                start_date = end_date - timedelta(days=180)
            elif range == "1y":
                start_date = end_date - timedelta(days=365)
            else:  # 5y
                start_date = end_date - timedelta(days=365 * 5)
            
            # 格式化日期
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            
            # 获取历史数据
            df = await self._run_sync(ak.stock_hk_hist, symbol=code, period="daily", start_date=start_date_str, end_date=end_date_str, adjust="qfq")
            
            if df.empty:
                return None

            # 构建响应数据
            price_points = []
            for _, row in df.iterrows():
                # 将日期转换为字符串格式
                date_str = row['日期']
                if isinstance(date_str, datetime):
                    date_str = date_str.strftime('%Y-%m-%d')
                elif isinstance(date_str, pd.Timestamp):
                    date_str = date_str.strftime('%Y-%m-%d')
                elif isinstance(date_str, str):
                    date_str = date_str
                else:
                    date_str = str(date_str)
                
                price_point = StockPricePoint(
                    date=date_str,
                    open=float(row['开盘']),
                    high=float(row['最高']),
                    low=float(row['最低']),
                    close=float(row['收盘']),
                    volume=int(row['成交量'])
                )
                price_points.append(price_point)
            
            return StockPriceHistory(symbol=symbol, data=price_points)
        except Exception as e:
            print(f"获取港股历史价格时出错: {str(e)}")
            return None
    
    async def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """获取港股公司基本面数据"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return {}
            
            code = code_match.group(1)
            return {}
            # 获取公司基本信息
            stock_info = await self._run_sync(ak.stock_hk_spot_em)
            stock_info = stock_info[stock_info['代码'] == code]
            
            # 获取财务指标
            financial_indicator = await self._run_sync(ak.stock_hk_financial_analysis_indicator, symbol=code)
            
            # 合并数据
            result = {}
            
            # 处理公司基本信息
            if not stock_info.empty:
                row = stock_info.iloc[0]
                result["公司名称"] = row['名称']
                result["当前价格"] = row['最新价']
                result["涨跌幅"] = row['涨跌幅']
                result["成交量"] = row['成交量']
                result["总市值"] = row['总市值']
            
            # 处理最新的财务指标
            if not financial_indicator.empty:
                latest_financial = financial_indicator.iloc[0]
                for col in financial_indicator.columns:
                    result[f"fin_{col}"] = latest_financial[col]
            
            # 添加一些常用指标的映射
            if not financial_indicator.empty:
                latest_indicator = financial_indicator.iloc[0]
                result["PERatio"] = latest_indicator["市盈率"] if "市盈率" in latest_indicator else "N/A"
                result["PBRatio"] = latest_indicator["市净率"] if "市净率" in latest_indicator else "N/A"
            
            return result
        except Exception as e:
            print(f"获取港股基本面数据时出错: {str(e)}")
            return {}
    
    async def get_historical_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取港股历史数据"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return None
            
            code = code_match.group(1)
            
            # 获取最近一年的数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            # 格式化日期
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            
            # 获取历史数据
            df = await self._run_sync(ak.stock_hk_hist, symbol=code, period="daily", start_date=start_date_str, end_date=end_date_str, adjust="qfq")
            
            if df.empty:
                return None
            print(f"获取历史数据: {len(df)}")
            # 设置日期索引
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.set_index('日期')
            
            # 重命名列以匹配 Alpha Vantage 格式
            df = df.rename(columns={
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            })
            
            return df
        except Exception as e:
            print(f"获取港股历史数据时出错: {str(e)}")
            return None
    
    async def get_news_sentiment(self, symbol: str) -> Dict[str, Any]:
        """获取港股新闻情绪分析"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return {}
            
            code = code_match.group(1)
            return {}
            # 获取新闻数据
            news_df = await self._run_sync(ak.stock_hk_news, symbol=code)
            
            if news_df.empty:
                return {
                    "sentiment": "neutral",
                    "score": 0.0,
                    "news_count": 0,
                    "latest_news": []
                }
            
            # 简单的情绪分析（基于标题关键词）
            positive_words = ["上涨", "突破", "增长", "利好", "突破", "创新高"]
            negative_words = ["下跌", "跌破", "下滑", "利空", "创新低"]
            
            sentiment_scores = []
            for title in news_df['标题']:
                score = 0
                for word in positive_words:
                    if word in title:
                        score += 1
                for word in negative_words:
                    if word in title:
                        score -= 1
                sentiment_scores.append(score)
            
            avg_score = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            
            # 确定情绪
            if avg_score > 0.2:
                sentiment = "positive"
            elif avg_score < -0.2:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            
            # 获取最新新闻
            latest_news = news_df.head(5).to_dict('records')
            
            return {
                "sentiment": sentiment,
                "score": avg_score,
                "news_count": len(news_df),
                "latest_news": latest_news
            }
        except Exception as e:
            print(f"获取港股新闻情绪分析时出错: {str(e)}")
            return {}
    
    async def get_sector_linkage(self, symbol: str) -> Dict[str, Any]:
        """获取港股板块联动性分析"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return self._default_sector_linkage()
            
            code = code_match.group(1)
            return self._default_sector_linkage()
            # 获取股票所属板块
            try:
                # 获取港股行业分类数据
                stock_info = await self._run_sync(ak.stock_hk_spot_em)
                stock_row = stock_info[stock_info['代码'] == code]
                
                if stock_row.empty:
                    return self._default_sector_linkage()
                
                # 提取行业信息
                sector_name = stock_row.iloc[0].get('所属行业', '未知板块')
                
                # 获取同行业股票
                sector_stocks = stock_info[stock_info['所属行业'] == sector_name]
                sector_total = len(sector_stocks)
                
                if sector_total <= 1:
                    return self._default_sector_linkage(sector_name)
                
                # 获取板块内所有股票的历史数据
                sector_codes = sector_stocks['代码'].tolist()
                
                # 限制处理的股票数量，避免请求过多
                max_stocks = min(20, len(sector_codes))
                sector_codes = sector_codes[:max_stocks]
                
                # 获取当前股票的历史数据
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
                
                target_stock_data = await self._run_sync(
                    ak.stock_hk_hist, 
                    symbol=code, 
                    period="daily", 
                    start_date=start_date, 
                    end_date=end_date, 
                    adjust="qfq"
                )
                
                if target_stock_data.empty:
                    return self._default_sector_linkage(sector_name)
                
                # 提取目标股票的收盘价序列
                target_stock_data['日期'] = pd.to_datetime(target_stock_data['日期'])
                target_stock_prices = target_stock_data.set_index('日期')['收盘']
                
                # 获取板块内其他股票的数据
                all_prices = {}
                for sector_code in sector_codes:
                    if sector_code == code:
                        all_prices[sector_code] = target_stock_prices
                        continue
                    
                    try:
                        stock_data = await self._run_sync(
                            ak.stock_hk_hist, 
                            symbol=sector_code, 
                            period="daily", 
                            start_date=start_date, 
                            end_date=end_date, 
                            adjust="qfq"
                        )
                        
                        if not stock_data.empty:
                            stock_data['日期'] = pd.to_datetime(stock_data['日期'])
                            all_prices[sector_code] = stock_data.set_index('日期')['收盘']
                    except:
                        continue
                
                # 计算相关性和带动性
                correlations = {}
                returns = {}
                
                # 计算每只股票的日收益率
                for code, prices in all_prices.items():
                    returns[code] = prices.pct_change().dropna()
                
                # 计算目标股票与其他股票的相关性
                target_returns = returns.get(code)
                if target_returns is None or len(target_returns) < 10:
                    return self._default_sector_linkage(sector_name)
                
                for other_code, other_returns in returns.items():
                    if other_code == code:
                        continue
                    
                    # 确保两个序列有相同的索引
                    common_idx = target_returns.index.intersection(other_returns.index)
                    if len(common_idx) < 10:
                        continue
                    
                    # 计算相关性
                    corr = target_returns.loc[common_idx].corr(other_returns.loc[common_idx])
                    correlations[other_code] = corr
                
                if not correlations:
                    return self._default_sector_linkage(sector_name)
                
                # 计算平均相关性
                avg_correlation = sum(correlations.values()) / len(correlations)
                
                # 计算带动性（使用滞后相关性作为近似）
                lag_influences = []
                for other_code, other_returns in returns.items():
                    if other_code == code:
                        continue
                    
                    # 确保两个序列有相同的索引
                    target_lagged = target_returns.shift(1).dropna()
                    common_idx = target_lagged.index.intersection(other_returns.index)
                    if len(common_idx) < 10:
                        continue
                    
                    # 计算滞后相关性
                    lag_corr = target_lagged.loc[common_idx].corr(other_returns.loc[common_idx])
                    lag_influences.append(max(0, lag_corr))  # 只考虑正向影响
                
                driving_force = sum(lag_influences) / len(lag_influences) if lag_influences else 0
                
                # 计算板块内排名
                rank = 1
                target_return = (target_stock_data['收盘'].iloc[-1] / target_stock_data['收盘'].iloc[0] - 1) * 100
                
                for other_code in sector_codes:
                    if other_code == code:
                        continue
                    
                    try:
                        other_data = await self._run_sync(
                            ak.stock_hk_hist, 
                            symbol=other_code, 
                            period="daily", 
                            start_date=start_date, 
                            end_date=end_date, 
                            adjust="qfq"
                        )
                        
                        if not other_data.empty:
                            other_return = (other_data['收盘'].iloc[-1] / other_data['收盘'].iloc[0] - 1) * 100
                            if other_return > target_return:
                                rank += 1
                    except:
                        continue
                
                # 返回结果
                return {
                    "sector_name": sector_name,
                    "correlation": float(min(1.0, max(0.0, avg_correlation))),
                    "driving_force": float(min(1.0, max(0.0, driving_force * 2))),
                    "rank_in_sector": rank,
                    "total_in_sector": sector_total
                }
            
            except Exception as e:
                print(f"获取港股板块联动性时出错: {str(e)}")
                return self._default_sector_linkage()
        
        except Exception as e:
            print(f"获取港股板块联动性时出错: {str(e)}")
            return self._default_sector_linkage()
    
    def _default_sector_linkage(self, sector_name="未知板块") -> Dict[str, Any]:
        """返回默认的板块联动性分析数据"""
        return {
            "sector_name": sector_name,
            "correlation": 0.0,
            "driving_force": 0.0,
            "rank_in_sector": 1,
            "total_in_sector": 1
        }
    
    async def get_concept_distribution(self, symbol: str) -> Dict[str, Any]:
        """获取港股概念涨跌分布分析"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return self._default_concept_distribution()
            
            code = code_match.group(1)
            
            return self._default_concept_distribution()
            # 获取概念板块数据
            concept_df = await self._run_sync(ak.stock_hk_concept_spot_em)
            
            if concept_df.empty:
                return self._default_concept_distribution()
            
            # 统计概念板块涨跌分布
            concept_distribution = {
                "up": [],
                "down": [],
                "neutral": []
            }
            
            for _, row in concept_df.iterrows():
                concept_name = row['板块名称']
                change_percent = float(row['涨跌幅']) if not pd.isna(row['涨跌幅']) else 0.0
                
                if change_percent > 0.5:
                    concept_distribution["up"].append({
                        "name": concept_name,
                        "change_percent": change_percent
                    })
                elif change_percent < -0.5:
                    concept_distribution["down"].append({
                        "name": concept_name,
                        "change_percent": change_percent
                    })
                else:
                    concept_distribution["neutral"].append({
                        "name": concept_name,
                        "change_percent": change_percent
                    })
            
            return concept_distribution
        except Exception as e:
            print(f"获取港股概念涨跌分布分析时出错: {str(e)}")
            return self._default_concept_distribution()
    
    def _default_concept_distribution(self) -> Dict[str, Any]:
        """返回默认的概念涨跌分布分析数据"""
        return {
            "up": [],
            "down": [],
            "neutral": []
        }
    
    async def get_intraday_data(self, symbol: str, refresh: bool = False) -> Dict[str, Any]:
        """获取港股分时数据"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match or code_match.group(2) != 'HK':
                return self._generate_mock_intraday_data(symbol)
            
            code = code_match.group(1)
            
            # 获取分时数据
            # 获取当天的数据
            today = datetime.now()
            start_date = datetime(today.year, today.month, today.day, 0, 0)
            end_date = datetime(today.year, today.month, today.day, 23, 59)

            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            intraday_df = await self._run_sync(ak.stock_hk_hist_min_em, symbol=code, period="1", start_date=start_date_str, end_date=end_date_str)  
            
            if intraday_df.empty:
                return self._generate_mock_intraday_data(symbol)
            
            # 构建分时数据结构
            result = {
                "symbol": symbol,
                "data": []
            }
            
            # 处理分时数据
            for _, row in intraday_df.iterrows():
                # 获取时间
                time_str = row['时间'] if '时间' in row else str(row.name)
                
                # 获取价格和成交量
                price = float(row['收盘']) if not pd.isna(row['收盘']) else 0.0
                volume = int(float(row['成交量'])) if not pd.isna(row['成交量']) else 0
                
                # 添加数据点
                data_point = {
                    "time": time_str,
                    "price": price,
                    "volume": volume
                }
                
                result["data"].append(data_point)
            
            return result
        except Exception as e:
            print(f"获取港股分时数据时出错: {str(e)}")
            return self._generate_mock_intraday_data(symbol)
    
    def _generate_mock_intraday_data(self, symbol: str) -> Dict[str, Any]:
        """生成模拟的分时数据"""
        import random
        from datetime import datetime, timedelta
        
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
        
        # 生成上午9:30-12:00的数据
        current_time = datetime(today.year, today.month, today.day, 9, 30)
        end_morning = datetime(today.year, today.month, today.day, 12, 0)
        
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
            
        # 生成下午13:00-16:00的数据
        current_time = datetime(today.year, today.month, today.day, 13, 0)
        end_afternoon = datetime(today.year, today.month, today.day, 16, 0)
        
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
    
    async def get_market_news(self, symbol: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """获取港股相关的市场新闻和公告
        
        Args:
            symbol: 股票代码（可选）
            limit: 返回新闻条数
            
        Returns:
            新闻列表，每条新闻包含标题、内容摘要、URL、发布时间等信息
        """
        try:
            result = []
            
            # 如果提供了股票代码，获取特定港股的新闻
            if symbol:
                # 解析股票代码
                code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
                if code_match and code_match.group(2) == 'HK':
                    code = code_match.group(1)
                    
                    try:
                        # 获取港股新闻
                        news_df = await self._run_sync(ak.stock_hk_news, symbol=code)
                        
                        if not news_df.empty:
                            for i, row in news_df.iterrows():
                                if i >= limit:
                                    break
                                
                                # 根据新闻标题判断情绪
                                sentiment = 0
                                if "上涨" in row.get("标题", "") or "增长" in row.get("标题", "") or "利好" in row.get("标题", ""):
                                    sentiment = 0.5
                                elif "下跌" in row.get("标题", "") or "下滑" in row.get("标题", "") or "利空" in row.get("标题", ""):
                                    sentiment = -0.5
                                
                                news_item = {
                                    "title": row.get("标题", ""),
                                    "summary": row.get("内容", "")[:100] + "..." if len(row.get("内容", "")) > 100 else row.get("内容", ""),
                                    "url": row.get("链接", ""),
                                    "published_at": row.get("发布时间", ""),
                                    "source": "港股资讯",
                                    "sentiment": sentiment
                                }
                                result.append(news_item)
                            
                            return result
                    except Exception as e:
                        print(f"获取港股新闻时出错: {str(e)}")
            
            # 获取港股市场概览新闻
            try:
                # 尝试获取港股通新闻
                news_df = await self._run_sync(ak.stock_hk_ggt_components_em)
                
                # 由于这是成分股而非新闻，我们改为获取港股实时行情作为资讯
                hk_market_df = await self._run_sync(ak.stock_hk_spot_em)
                
                if not hk_market_df.empty:
                    # 按涨跌幅排序
                    hk_market_df = hk_market_df.sort_values(by="涨跌幅", ascending=False)
                    
                    # 提取涨幅最高和跌幅最低的股票作为市场动态
                    top_gainers = hk_market_df.head(3)
                    top_losers = hk_market_df.tail(3)
                    
                    # 生成涨幅最高的新闻
                    for _, row in top_gainers.iterrows():
                        if len(result) >= limit:
                            break
                        
                        news_item = {
                            "title": f"港股资讯: {row.get('名称', '')}({row.get('代码', '')})涨幅达{row.get('涨跌幅', '')}%",
                            "summary": f"当前价格: {row.get('最新价', '')}港元，涨跌: {row.get('涨跌额', '')}港元，成交量: {row.get('成交量', '')}，成交额: {row.get('成交额', '')}",
                            "url": "",
                            "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "source": "港股行情",
                            "sentiment": 0.5  # 上涨为正面情绪
                        }
                        result.append(news_item)
                    
                    # 生成跌幅最大的新闻
                    for _, row in top_losers.iterrows():
                        if len(result) >= limit:
                            break
                        
                        news_item = {
                            "title": f"港股资讯: {row.get('名称', '')}({row.get('代码', '')})跌幅达{abs(row.get('涨跌幅', ''))}%",
                            "summary": f"当前价格: {row.get('最新价', '')}港元，涨跌: {row.get('涨跌额', '')}港元，成交量: {row.get('成交量', '')}，成交额: {row.get('成交额', '')}",
                            "url": "",
                            "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "source": "港股行情",
                            "sentiment": -0.5  # 下跌为负面情绪
                        }
                        result.append(news_item)
                    
                    # 补充恒生指数信息
                    try:
                        hsi_df = await self._run_sync(ak.stock_hk_index_spot_em)
                        
                        if not hsi_df.empty:
                            for _, row in hsi_df.iterrows():
                                if "恒生指数" in row.get('名称', '') and len(result) < limit:
                                    sentiment = 0.3 if row.get('涨跌幅', 0) > 0 else -0.3
                                    
                                    news_item = {
                                        "title": f"港股大盘: {row.get('名称', '')}{'上涨' if row.get('涨跌幅', 0) > 0 else '下跌'}{abs(row.get('涨跌幅', 0))}%",
                                        "summary": f"当前点位: {row.get('最新价', '')}，涨跌: {row.get('涨跌额', '')}，成交额: {row.get('成交额', '')}",
                                        "url": "",
                                        "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "source": "港股指数",
                                        "sentiment": sentiment
                                    }
                                    result.append(news_item)
                                    break
                    except Exception as e:
                        print(f"获取恒生指数信息时出错: {str(e)}")
            except Exception as e:
                print(f"获取港股市场概览时出错: {str(e)}")
            
            return result
        except Exception as e:
            print(f"获取港股市场新闻和公告时出错: {str(e)}")
            return [] 