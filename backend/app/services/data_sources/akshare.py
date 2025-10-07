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

class AKShareDataSource(DataSourceBase):
    """AKShare 数据源实现"""
    
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
        print(f"搜索股票: {query}")
        """搜索股票"""
        try:
            # 获取A股股票列表
            stock_info_a_code_name_df = await self._run_sync(ak.stock_info_a_code_name)
            
            # 过滤匹配的股票
            filtered_stocks = stock_info_a_code_name_df[
                stock_info_a_code_name_df['code'].str.contains(query) | 
                stock_info_a_code_name_df['name'].str.contains(query)
            ]
            
            results = []
            for _, row in filtered_stocks.iterrows():
                # 判断交易所
                code = row['code']
                if code.startswith('6'):
                    exchange = "上海证券交易所"
                    symbol = f"{code}.SH"
                else:
                    exchange = "深圳证券交易所"
                    symbol = f"{code}.SZ"
                
                stock_info = StockInfo(
                    symbol=symbol,
                    name=row['name'],
                    exchange=exchange,
                    currency='CNY'
                )
                results.append(stock_info)
            
            return results[:10]  # 限制返回数量
        except Exception as e:
            print(f"搜索股票时出错: {str(e)}")
            return []
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """获取股票详细信息"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match:
                return None
            
            code = code_match.group(1)
            market = code_match.group(2)
            
            # 获取实时行情
            if settings.XUEQIU_TOKEN == "":
                    import requests
                    r = requests.get("https://xueqiu.com/hq", headers={"user-agent": "Mozilla"})
                    t = r.cookies["xq_a_token"]
                    settings.XUEQIU_TOKEN = t
            df = await self._run_sync(ak.stock_individual_spot_xq,symbol=market+code,token=settings.XUEQIU_TOKEN)
            
            if df.empty:
                return None
                        
            # 获取股票名称
            name = df[df['item']=='名称'].iloc[0]['value']
            
            # 确定交易所
            exchange = "上海证券交易所" if market == "SH" else "深圳证券交易所"
            
            # 计算涨跌幅
            price = float(df[df['item']=='现价'].iloc[0]['value']) if not pd.isna(df[df['item']=='现价'].iloc[0]['value']) else 0.0
            change = float(df[df['item']=='涨跌'].iloc[0]['value']) if not pd.isna(df[df['item']=='涨跌'].iloc[0]['value']) else 0.0
            change_percent = float(df[df['item']=='涨幅'].iloc[0]['value']) if not pd.isna(df[df['item']=='涨幅'].iloc[0]['value']) else 0.0
            
            # 获取市值（亿元转为元）
            market_cap = float(df[df['item']=='资产净值/总市值'].iloc[0]['value']) if not pd.isna(df[df['item']=='资产净值/总市值'].iloc[0]['value']) else 0.0

            # 获取成交量（单位股）
            volume = int(float(df[df['item']=='成交量'].iloc[0]['value'])) if not pd.isna(df[df['item']=='成交量'].iloc[0]['value']) else 0

            # 获取市盈率
            pe = float(df[df['item']=='市盈率(TTM)'].iloc[0]['value']) if not pd.isna(df[df['item']=='市盈率(TTM)'].iloc[0]['value']) else 0.0
            
            # 获取股息率
            dividend = float(df[df['item']=='股息率(TTM)'].iloc[0]['value']) if not pd.isna(df[df['item']=='股息率(TTM)'].iloc[0]['value']) else 0.0

            # 获取货币
            currency = df[df['item']=='货币'].iloc[0]['value'] if not pd.isna(df[df['item']=='货币'].iloc[0]['value']) else 'CNY'
            
            stock_info = StockInfo(
                symbol=symbol,
                name=name,
                exchange=exchange,
                currency=currency,
                price=price,
                change=change,
                changePercent=change_percent,
                marketCap=market_cap,
                volume=volume,
                pe=pe,
                dividend=dividend
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
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match:
                return None
            
            code = code_match.group(1)
            market = code_match.group(2)
            
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
            
            # 根据间隔选择不同的数据
            if interval == "daily":
                df = await self._run_sync(ak.stock_zh_a_hist, symbol=code, period="daily", start_date=start_date_str, end_date=end_date_str, adjust="qfq")
            elif interval == "weekly":
                df = await self._run_sync(ak.stock_zh_a_hist, symbol=code, period="weekly", start_date=start_date_str, end_date=end_date_str, adjust="qfq")
            else:  # monthly
                df = await self._run_sync(ak.stock_zh_a_hist, symbol=code, period="monthly", start_date=start_date_str, end_date=end_date_str, adjust="qfq")
            
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
            print(f"获取股票历史价格时出错: {str(e)}")
            return None
    
    async def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """获取公司基本面数据"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match:
                return {}
            
            code = code_match.group(1)
            
            # 获取公司基本信息
            stock_info = await self._run_sync(ak.stock_individual_info_em, symbol=code)
            
            # 获取财务指标
            financial_indicator = await self._run_sync(ak.stock_financial_analysis_indicator, symbol=code)
            
            # 合并数据
            result = {}
            
            # 处理公司基本信息
            if not stock_info.empty:
                for _, row in stock_info.iterrows():
                    result[row.iloc[0]] = row.iloc[1]
            
            # 处理最新的财务指标
            if not financial_indicator.empty:
                latest_financial = financial_indicator.iloc[0]
                for col in financial_indicator.columns:
                    result[f"fin_{col}"] = latest_financial[col]
            
            # 获取股息率
            try:
                dividend_info = await self._run_sync(ak.stock_history_dividend_detail, symbol=code, indicator="分红")
                if not dividend_info.empty:
                    latest_dividend = dividend_info.iloc[0]
                    result["DividendYield"] = latest_dividend["派息比例"] if "派息比例" in latest_dividend else "0"
                else:
                    result["DividendYield"] = "0"
            except:
                result["DividendYield"] = "0"
            
            # 获取市值
            try:
                stock_info = await self._run_sync(ak.stock_value_em, symbol=code)
                if not stock_info.empty:
                    result["MarketCapitalization"] = float(stock_info.iloc[0]['总市值']) * 100000000
                    result["PERatio"] = float(stock_info.iloc[0]['PE(TTM)'])
                    result["PBRatio"] = float(stock_info.iloc[0]['市净率'])
                else:
                    result["MarketCapitalization"] = 0
                    result["PERatio"] = 0
                    result["PBRatio"] = 0
            except:
                result["MarketCapitalization"] = 0
                result["PERatio"] = 0
                result["PBRatio"] = 0
            
            return result
        except Exception as e:
            print(f"获取基本面数据时出错: {str(e)}")
            return {}
    
    async def get_historical_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取股票历史数据"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match:
                return None
            
            code = code_match.group(1)
            
            # 获取最近100个交易日的数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            
            df = await self._run_sync(ak.stock_zh_a_hist, symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            print(f"获取历史数据: {len(df)}")
            
            if df.empty:
                return None
            
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
            print(f"获取历史数据时出错: {str(e)}")
            return None
    
    async def get_news_sentiment(self, symbol: str) -> Dict[str, Any]:
        """获取新闻情绪分析和政策共振系数"""
        try:
            # 初始化结果
            result = {
                "feed": [],
                "sentiment_score_avg": 0,
                "policy_resonance": {
                    "coefficient": 0,
                    "policies": []
                }
            }
            
            # 获取股票相关新闻
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if code_match:
                code = code_match.group(1)
                try:
                    # 获取股票相关新闻
                    stock_news = await self._run_sync(ak.stock_news_em, symbol=code)
                    
                    if not stock_news.empty:
                        feed = []
                        for _, row in stock_news.iterrows():
                            feed.append({
                                "title": row["新闻标题"] if "新闻标题" in row else "",
                                "url": row["新闻链接"] if "新闻链接" in row else "",
                                "time_published": row["发布时间"] if "发布时间" in row else "",
                                "overall_sentiment_score": 0  # 没有情感分析，默认为中性
                            })
                        
                        result["feed"] = feed
                except Exception as e:
                    print(f"获取股票新闻时出错: {str(e)}")
            
            # 获取政策新闻并计算政策共振系数
            try:
                # 获取最近的经济政策新闻
                policy_data = await self._run_sync(ak.news_economic_baidu)
                
                if not policy_data.empty:
                    # 获取股票名称
                    stock_name = ""
                    if code_match:
                        try:
                            stock_info = await self.get_stock_info(symbol)
                            if stock_info:
                                stock_name = stock_info.name
                        except:
                            pass
                    
                    # 计算政策共振系数
                    # 1. 提取最近30条政策新闻
                    recent_policies = policy_data.head(30)
                    
                    # 2. 初始化共振分数
                    resonance_score = 0
                    relevant_policies = []
                    
                    # 3. 分析每条政策新闻与股票的相关性
                    for _, policy in recent_policies.iterrows():
                        policy_title = policy.get("title", "")
                        policy_content = policy.get("content", "")
                        policy_date = policy.get("date", "")
                        
                        # 计算相关性分数 (简单的关键词匹配)
                        relevance = 0
                        
                        # 如果政策标题或内容包含股票名称，增加相关性
                        if stock_name and (stock_name in policy_title or stock_name in policy_content):
                            relevance += 3
                        
                        # 分析政策对行业的影响
                        industry_keywords = await self._get_industry_keywords(symbol)
                        for keyword in industry_keywords:
                            if keyword in policy_title:
                                relevance += 2
                            elif keyword in policy_content:
                                relevance += 1
                        
                        # 如果政策相关，添加到相关政策列表
                        if relevance > 0:
                            resonance_score += relevance
                            relevant_policies.append({
                                "title": policy_title,
                                "date": policy_date,
                                "relevance": relevance,
                                "url": policy.get("url", "")
                            })
                    
                    # 4. 计算最终共振系数 (0-1之间)
                    if relevant_policies:
                        # 归一化共振分数 (最大可能分数为30条政策*最高相关性5=150)
                        normalized_score = min(1.0, resonance_score / 30)
                        result["policy_resonance"]["coefficient"] = normalized_score
                        result["policy_resonance"]["policies"] = relevant_policies[:5]  # 只返回最相关的5条
            
            except Exception as e:
                print(f"计算政策共振系数时出错: {str(e)}")
            
            return result
        except Exception as e:
            print(f"获取新闻情绪时出错: {str(e)}")
            return {
                "feed": [],
                "sentiment_score_avg": 0,
                "policy_resonance": {
                    "coefficient": 0,
                    "policies": []
                }
            }
    
    async def _get_industry_keywords(self, symbol: str) -> List[str]:
        """获取行业关键词"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match:
                return []
            
            code = code_match.group(1)
            
            # 获取股票行业分类数据
            stock_row = await self._run_sync(ak.stock_individual_info_em, symbol=code)

            # 提取行业信息
            if not stock_row.empty:
                industry = None
                for col in stock_row.columns:
                    if '所属行业' in col:
                        industry = stock_row.iloc[0][col]
                        break
                
                if industry:
                    return self._industry_to_keywords(industry)
            
            return []
        except Exception as e:
            print(f"获取行业关键词时出错: {str(e)}")
            return []
    
    def _industry_to_keywords(self, industry: str) -> List[str]:
        """根据行业返回相关关键词"""
        # 行业关键词映射
        industry_keywords = {
            "农业": ["农业", "种植", "农产品", "粮食", "农村", "乡村振兴"],
            "采矿业": ["矿业", "采矿", "矿产", "资源", "能源", "开采"],
            "制造业": ["制造", "工业", "生产", "加工", "工厂", "智能制造"],
            "电力": ["电力", "能源", "电网", "发电", "新能源", "碳中和"],
            "建筑业": ["建筑", "房地产", "基建", "工程", "城市建设"],
            "批发和零售业": ["零售", "商业", "消费", "电商", "商超", "贸易"],
            "交通运输": ["交通", "运输", "物流", "航运", "铁路", "公路"],
            "住宿和餐饮业": ["餐饮", "旅游", "酒店", "服务业", "消费"],
            "信息技术": ["科技", "互联网", "软件", "信息", "数字化", "人工智能", "大数据"],
            "金融业": ["金融", "银行", "保险", "证券", "投资", "理财"],
            "房地产业": ["房地产", "地产", "楼市", "住房", "建设"],
            "科学研究": ["科研", "研发", "创新", "技术", "专利"],
            "水利环境": ["环保", "水利", "生态", "环境", "可持续"],
            "居民服务": ["服务", "社区", "民生", "消费"],
            "教育": ["教育", "培训", "学校", "教学", "学习"],
            "卫生和社会工作": ["医疗", "卫生", "健康", "社会保障", "养老"],
            "文化体育娱乐业": ["文化", "体育", "娱乐", "传媒", "影视", "游戏"],
            "公共管理": ["公共", "管理", "政务", "行政"]
        }
        
        # 查找最匹配的行业
        for key, keywords in industry_keywords.items():
            if key in industry:
                return keywords + ["经济", "政策", "发展", "改革"]
        
        # 默认关键词
        return ["经济", "政策", "发展", "改革", "创新", "金融", "市场", "投资"]
    
    async def get_sector_linkage(self, symbol: str) -> Dict[str, Any]:
        """获取板块联动性分析"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match:
                return self._default_sector_linkage()
            
            code = code_match.group(1)
            
            # 获取股票所属板块
            try:
                # 获取股票行业分类数据
                stock_row = await self._run_sync(ak.stock_individual_info_em, symbol=code)

                # 提取行业信息
                industry_info = None
                for _, row in stock_row.iterrows():
                    if row['item'] == '行业':
                        industry_info = row['value']
                        break
                
                # 如果找不到行业信息，使用默认值
                if not industry_info:
                    return self._default_sector_linkage()
                
                # 设置行业名称
                sector_name = industry_info

                # 获取同行业股票
                sector_stocks = await self._run_sync(ak.stock_board_industry_cons_em, symbol=sector_name)
                sector_total = len(sector_stocks)
                
                if sector_total <= 1:
                    return self._default_sector_linkage(sector_name)
                
                # 获取板块内所有股票的历史数据
                sector_data = {}
                sector_codes = sector_stocks['代码'].tolist()
                
                # 限制处理的股票数量，避免请求过多
                max_stocks = min(20, len(sector_codes))
                sector_codes = sector_codes[:max_stocks]
                
                # 获取当前股票的历史数据
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
                
                target_stock_data = await self._run_sync(ak.stock_zh_a_hist, symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                
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
                        stock_data = await self._run_sync(ak.stock_zh_a_hist, symbol=sector_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                        
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
                
                # 计算带动性（使用格兰杰因果检验的简化版本）
                # 这里使用滞后相关性作为带动性的近似
                driving_force = 0
                
                # 计算目标股票对其他股票的滞后影响
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
                
                if lag_influences:
                    driving_force = sum(lag_influences) / len(lag_influences)
                
                # 计算板块内排名
                rank = 1
                for other_code in sector_codes:
                    if other_code == code:
                        continue
                    
                    try:
                        other_data = await self._run_sync(ak.stock_zh_a_hist, symbol=other_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                        
                        if not other_data.empty:
                            # 计算涨幅
                            other_return = (other_data['收盘'].iloc[-1] / other_data['收盘'].iloc[0] - 1) * 100
                            target_return = (target_stock_data['收盘'].iloc[-1] / target_stock_data['收盘'].iloc[0] - 1) * 100
                            
                            if other_return > target_return:
                                rank += 1
                    except:
                        continue
                
                # 返回结果
                return {
                    "sector_name": sector_name,
                    "correlation": float(min(1.0, max(0.0, avg_correlation))),  # 确保在0-1之间
                    "driving_force": float(min(1.0, max(0.0, driving_force * 2))),  # 放大并限制在0-1之间
                    "rank_in_sector": rank,
                    "total_in_sector": sector_total
                }
            
            except Exception as e:
                print(f"获取板块联动性时出错: {str(e)}")
                return self._default_sector_linkage()
        
        except Exception as e:
            print(f"获取板块联动性时出错: {str(e)}")
            return self._default_sector_linkage()
    
    def _default_sector_linkage(self, sector_name="未知板块") -> Dict[str, Any]:
        """返回默认的板块联动性数据"""
        return {
            "sector_name": sector_name,
            "correlation": 0.5,
            "driving_force": 0.3,
            "rank_in_sector": 0,
            "total_in_sector": 0
        }
    
    async def get_concept_distribution(self, symbol: str) -> Dict[str, Any]:
        """获取概念涨跌分布分析"""
        try:
            # 解析股票代码
            code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
            if not code_match:
                return self._default_concept_distribution()
            
            code = code_match.group(1)

            # 计算开始日期和结束日期（只计算一次）
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

            # todo: 获取概念涨跌分布
            return self._default_concept_distribution()
        
        except Exception as e:
            print(f"获取概念涨跌分布时出错: {str(e)}")
            return self._default_concept_distribution()
    
    def _default_concept_distribution(self) -> Dict[str, Any]:
        """返回默认的概念涨跌分布数据"""
        return {
            "overall_strength": 0.5,
            "leading_concepts": [],
            "lagging_concepts": [],
            "all_concepts": []  # 修正了返回键名，与正常返回一致
        }
        
    async def get_intraday_data(self, symbol: str, refresh: bool = False) -> Dict[str, Any]:
        """获取股票分时数据"""
        try:
            print(f"获取分时数据: {symbol}")

            # 解析股票代码
            code = symbol.split('.')[0]
            market = symbol.split('.')[1] if '.' in symbol else ''
            
            # 确定市场
            if market == 'SH':
                market_type = 1  # 上海
            elif market == 'SZ':
                market_type = 0  # 深圳
            else:
                # 根据代码前缀判断
                market_type = 1 if code.startswith('6') else 0
                
            # 获取当天分时数据
            intraday_df = await self._run_sync(
                ak.stock_zh_a_hist_pre_min_em, 
                symbol=code, 
            )
                
            # 如果仍然没有数据，生成模拟数据
            if intraday_df is None or len(intraday_df) == 0:
                print(f"无法获取真实分时数据，生成模拟数据")
                return self._generate_mock_intraday_data(symbol)
                
            # 处理数据
            result = {
                "symbol": symbol,
                "data": []
            }
            
            # 转换数据格式
            for index, row in intraday_df.iterrows():
                # 尝试不同的列名格式
                if 'datetime' in intraday_df.columns:
                    time_str = str(row['datetime'])
                elif '时间' in intraday_df.columns:
                    time_str = str(row['时间'])
                elif 'time' in intraday_df.columns:
                    time_str = str(row['time'])
                else:
                    # 使用索引作为时间
                    time_str = str(index)
                    
                # 尝试不同的价格列名
                price = None
                volume = None
                
                # 价格列
                if 'close' in intraday_df.columns:
                    price = float(row['close'])
                elif '收盘' in intraday_df.columns:
                    price = float(row['收盘'])
                elif 'price' in intraday_df.columns:
                    price = float(row['price'])
                elif '价格' in intraday_df.columns:
                    price = float(row['成交价'])
                    
                # 成交量列
                if 'volume' in intraday_df.columns:
                    volume = float(row['volume'])
                elif '成交量' in intraday_df.columns:
                    volume = float(row['成交量'])
                elif 'vol' in intraday_df.columns:
                    volume = float(row['vol'])
                    
                # 如果没有找到价格或成交量，跳过
                if price is None or volume is None:
                    continue
                    
                # 添加数据点
                data_point = {
                    "time": time_str,
                    "price": price,
                    "volume": volume
                }
                
                result["data"].append(data_point)
                
            return result
            
        except Exception as e:
            print(f"获取分时数据出错: {str(e)}")
            # 出错时返回模拟数据
            return self._generate_mock_intraday_data(symbol)
            
    def _generate_mock_intraday_data(self, symbol: str) -> Dict[str, Any]:
        """生成模拟分时数据"""
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
    
    async def get_market_news(self, symbol: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """获取市场新闻和公告
        
        Args:
            symbol: 股票代码（可选）
            limit: 返回新闻条数
            
        Returns:
            新闻列表，每条新闻包含标题、内容摘要、URL、发布时间等信息
        """
        try:
            result = []
            
            # 如果提供了股票代码，获取特定股票的新闻
            if symbol:
                # 解析股票代码
                code_match = re.match(r'(\d+)\.([A-Z]+)', symbol)
                if code_match:
                    code = code_match.group(1)
                    market = code_match.group(2)
                    
                    try:
                        # 获取股票相关新闻
                        stock_news = await self._run_sync(ak.stock_news_em, symbol=code)
                        
                        if not stock_news.empty:
                            for i, row in stock_news.iterrows():
                                if i >= limit:
                                    break
                                    
                                news_item = {
                                    "title": row.get("新闻标题", ""),
                                    "summary": row.get("新闻内容", "")[:100] + "..." if len(row.get("新闻内容", "")) > 100 else row.get("新闻内容", ""),
                                    "url": row.get("新闻链接", ""),
                                    "published_at": row.get("发布时间", ""),
                                    "source": "东方财富",
                                    "sentiment": 0  # 默认中性
                                }
                                result.append(news_item)
                            
                            return result
                    except Exception as e:
                        print(f"获取股票新闻时出错: {str(e)}")
            
            # 获取市场概览新闻
            try:
                # 尝试获取财经新闻
                news_df = await self._run_sync(ak.news_economic_baidu)
                
                if not news_df.empty:
                    for i, row in news_df.iterrows():
                        if i >= limit:
                            break
                            
                        news_item = {
                            "title": row.get("title", ""),
                            "summary": row.get("content", "")[:100] + "..." if len(row.get("content", "")) > 100 else row.get("content", ""),
                            "url": row.get("url", ""),
                            "published_at": row.get("date", ""),
                            "source": "百度财经",
                            "sentiment": 0  # 默认中性
                        }
                        result.append(news_item)
                    
                    return result
            except Exception as e:
                print(f"获取百度财经新闻时出错: {str(e)}")
            
            # 如果百度财经新闻获取失败，尝试其他来源
            try:
                # 尝试获取东方财富快讯
                news_df = await self._run_sync(ak.stock_zh_a_alerts_cls)
                
                if not news_df.empty:
                    for i, row in news_df.iterrows():
                        if i >= limit:
                            break
                            
                        news_item = {
                            "title": row.get("title", ""),
                            "summary": row.get("content", "")[:100] + "..." if len(row.get("content", "")) > 100 else row.get("content", ""),
                            "url": "",
                            "published_at": row.get("datetime", ""),
                            "source": "A股快讯",
                            "sentiment": 0  # 默认中性
                        }
                        result.append(news_item)
                    
                    return result
            except Exception as e:
                print(f"获取东方财富快讯时出错: {str(e)}")
            
            # 如果所有来源都失败，尝试获取新浪财经新闻
            try:
                # 尝试获取新浪财经新闻
                news_df = await self._run_sync(ak.stock_zh_a_new)
                
                if not news_df.empty:
                    for i, row in news_df.iterrows():
                        if i >= limit:
                            break
                            
                        news_item = {
                            "title": row.get("标题", ""),
                            "summary": row.get("内容", "")[:100] + "..." if len(row.get("内容", "")) > 100 else row.get("内容", ""),
                            "url": row.get("链接", ""),
                            "published_at": row.get("时间", ""),
                            "source": "新浪财经",
                            "sentiment": 0  # 默认中性
                        }
                        result.append(news_item)
                    
                    return result
            except Exception as e:
                print(f"获取新浪财经新闻时出错: {str(e)}")
            
            return result
        except Exception as e:
            print(f"获取市场新闻和公告时出错: {str(e)}")
            return []