"""
股票分析机器学习模型训练脚本

这个脚本用于训练一个机器学习模型，用于预测股票的走势和风险水平。
模型将基于真实历史价格数据和技术指标进行训练。
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
from datetime import datetime, timedelta
import sys
import requests
import time
import akshare as ak
import tushare as ts
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目根目录到 Python 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.core.config import settings

def fetch_stock_data_alphavantage(symbols, api_key=None):
    """
    从Alpha Vantage获取股票历史数据
    
    Args:
        symbols: 股票代码列表
        api_key: Alpha Vantage API密钥，如果为None则使用环境变量中的密钥
    
    Returns:
        包含所有股票历史数据的字典
    """
    if api_key is None:
        api_key = settings.ALPHAVANTAGE_API_KEY
    
    base_url = settings.ALPHAVANTAGE_API_BASE_URL
    all_data = {}
    
    for symbol in symbols:
        logger.info(f"从Alpha Vantage获取{symbol}的历史数据...")
        
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": api_key
        }
        
        try:
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if "Time Series (Daily)" not in data:
                logger.warning(f"无法获取{symbol}的数据: {data.get('Note', data)}")
                continue
            
            # 转换为DataFrame
            time_series = data["Time Series (Daily)"]
            df = pd.DataFrame.from_dict(time_series, orient='index')
            
            # 重命名列
            df.rename(columns={
                '1. open': 'open',
                '2. high': 'high',
                '3. low': 'low',
                '4. close': 'close',
                '5. volume': 'volume'
            }, inplace=True)
            
            # 转换为数值类型
            for col in df.columns:
                df[col] = pd.to_numeric(df[col])
            
            # 添加日期列
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            
            all_data[symbol] = df
            
            # Alpha Vantage有API调用限制，每分钟最多5次
            time.sleep(12)
            
        except Exception as e:
            logger.error(f"获取{symbol}数据时出错: {str(e)}")
    
    return all_data

def fetch_stock_data_akshare(symbols):
    """
    从AKShare获取A股历史数据
    
    Args:
        symbols: 股票代码列表，格式如 ["000001.SZ", "600000.SH"]
    
    Returns:
        包含所有股票历史数据的字典
    """
    all_data = {}
    
    for symbol in symbols:
        logger.info(f"从AKShare获取{symbol}的历史数据...")
        
        try:
            # 解析股票代码
            code_match = symbol.split('.')
            if len(code_match) != 2:
                logger.warning(f"无效的股票代码格式: {symbol}")
                continue
            
            code = code_match[0]
            market = code_match[1]
            
            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=code, 
                period="daily", 
                start_date="20180101", 
                end_date=datetime.now().strftime("%Y%m%d"), 
                adjust="qfq"
            )
            
            # 重命名列
            df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            }, inplace=True)
            
            # 设置日期索引
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 选择需要的列
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            all_data[symbol] = df
            
            # 避免频繁请求
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"获取{symbol}数据时出错: {str(e)}")
    
    return all_data

def fetch_stock_data_tushare(symbols, token=None):
    """
    从Tushare获取A股历史数据
    
    Args:
        symbols: 股票代码列表，格式如 ["000001.SZ", "600000.SH"]
        token: Tushare API Token，如果为None则使用环境变量中的Token
    
    Returns:
        包含所有股票历史数据的字典
    """
    if token is None:
        token = settings.TUSHARE_API_TOKEN
    
    # 初始化Tushare
    ts.set_token(token)
    pro = ts.pro_api()
    
    all_data = {}
    
    for symbol in symbols:
        logger.info(f"从Tushare获取{symbol}的历史数据...")
        
        try:
            # 获取历史数据
            df = pro.daily(
                ts_code=symbol,
                start_date='20180101',
                end_date=datetime.now().strftime('%Y%m%d')
            )
            
            # 转换日期并设置为索引
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df.sort_values('trade_date', inplace=True)
            df.set_index('trade_date', inplace=True)
            
            # 重命名列
            df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume'
            }, inplace=True)
            
            # 选择需要的列
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            all_data[symbol] = df
            
            # 避免频繁请求
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"获取{symbol}数据时出错: {str(e)}")
    
    return all_data

def add_technical_indicators(df):
    """
    添加技术指标
    
    Args:
        df: 包含OHLCV数据的DataFrame
    
    Returns:
        添加了技术指标的DataFrame
    """
    # 确保索引是日期类型
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # 添加技术指标
    # SMA - 简单移动平均线
    df['sma_5'] = df['close'].rolling(window=5).mean()
    df['sma_10'] = df['close'].rolling(window=10).mean()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # EMA - 指数移动平均线
    df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    # MACD - 移动平均收敛散度
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # RSI - 相对强弱指标
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 波动率 - 标准差
    df['volatility_5'] = df['close'].rolling(window=5).std()
    df['volatility_10'] = df['close'].rolling(window=10).std()
    df['volatility_20'] = df['close'].rolling(window=20).std()
    
    # 布林带
    df['bollinger_mid'] = df['close'].rolling(window=20).mean() # 20日均线
    df['bollinger_std'] = df['close'].rolling(window=20).std() # 20日均线标准差 
    df['bollinger_upper'] = df['bollinger_mid'] + 2 * df['bollinger_std']
    df['bollinger_lower'] = df['bollinger_mid'] - 2 * df['bollinger_std']
    
    # 价格变化率
    df['price_change_1d'] = df['close'].pct_change(1)
    df['price_change_5d'] = df['close'].pct_change(5)
    df['price_change_10d'] = df['close'].pct_change(10)
    df['price_change_20d'] = df['close'].pct_change(20)
    
    # 成交量变化率
    df['volume_change_1d'] = df['volume'].pct_change(1)
    df['volume_change_5d'] = df['volume'].pct_change(5)
    
    # 成交量移动平均
    df['volume_sma_5'] = df['volume'].rolling(window=5).mean()
    df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
    
    # 添加目标变量
    # 1. 未来5天的价格变化百分比
    df['future_return_5d'] = df['close'].shift(-5) / df['close'] - 1
    
    # 2. 走势标签 (1: 上涨, 0: 下跌)
    df['trend'] = df['future_return_5d'].apply(lambda x: 1 if x > 0 else 0)
    
    # 3. 风险水平 (0: 低, 1: 中, 2: 高)
    # 处理NaN值
    volatility_pct = df['volatility_20'] / df['close'] * 100
    df['risk'] = pd.cut(volatility_pct, bins=[0, 1, 3, float('inf')], labels=[0, 1, 2])
    # 将NaN值填充为中等风险(1)
    df['risk'] = df['risk'].fillna(1).astype(int)
    
    # 4. 情绪标签 (0: 负面, 1: 中性, 2: 积极)
    df['sentiment'] = pd.cut(df['future_return_5d'], bins=[-float('inf'), -0.02, 0.02, float('inf')], labels=[0, 1, 2])
    # 将NaN值填充为中性(1)
    df['sentiment'] = df['sentiment'].fillna(1).astype(int)
    
    # 删除含有 NaN 的行
    df = df.dropna()
    
    return df

def prepare_training_data(stock_data_dict):
    """
    准备训练数据
    
    Args:
        stock_data_dict: 包含多只股票历史数据的字典
    
    Returns:
        合并后的训练数据
    """
    all_processed_data = []
    
    for symbol, df in stock_data_dict.items():
        try:
            # 确保数据没有缺失值
            df = df.copy()
            
            # 检查并处理缺失值
            if df.isnull().any().any():
                logger.warning(f"{symbol} 数据中存在缺失值，进行填充处理")
                # 对于OHLCV数据，使用前向填充
                df.fillna(method='ffill', inplace=True)
                # 如果仍有缺失值（例如序列开头），使用后向填充
                df.fillna(method='bfill', inplace=True)
            
            # 确保没有负值或零值，这可能导致计算技术指标时出现问题
            for col in ['open', 'high', 'low', 'close']:
                if (df[col] <= 0).any():
                    logger.warning(f"{symbol} 的 {col} 列中存在非正值，进行修正")
                    df[col] = df[col].apply(lambda x: max(x, 0.01))
            
            if (df['volume'] <= 0).any():
                logger.warning(f"{symbol} 的 volume 列中存在非正值，进行修正")
                df['volume'] = df['volume'].apply(lambda x: max(x, 1))
            
            # 添加技术指标
            processed_df = add_technical_indicators(df)
            
            # 确保没有NaN值
            if processed_df.isnull().any().any():
                logger.warning(f"{symbol} 处理后的数据中仍存在缺失值，进行填充处理")
                processed_df = processed_df.fillna(method='ffill').fillna(method='bfill')
            
            # 添加股票代码列
            processed_df['symbol'] = symbol
            
            all_processed_data.append(processed_df)
            
        except Exception as e:
            logger.error(f"处理{symbol}数据时出错: {str(e)}")
    
    # 合并所有数据
    if all_processed_data:
        combined_data = pd.concat(all_processed_data)
        logger.info(f"合并后的数据集大小: {combined_data.shape}")
        return combined_data
    else:
        logger.error("没有可用的处理数据")
        return None

def train_models(data_source='akshare', symbols=None):
    """
    训练模型并保存
    
    Args:
        data_source: 数据源 ('alphavantage', 'akshare', 'tushare')
        symbols: 股票代码列表，如果为None则使用默认列表
    """
    # 默认股票列表
    if symbols is None:
        if data_source == 'alphavantage':
            # 美股代码
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'WMT']
        else:
            # A股代码
            symbols = ['000001.SZ', '600000.SH', '600036.SH', '601318.SH', '600519.SH', 
                      '000858.SZ', '601988.SH', '600276.SH', '601166.SH', '000333.SZ']
    
    # 获取股票数据
    logger.info(f"使用{data_source}数据源获取{len(symbols)}只股票的历史数据...")
    
    if data_source == 'alphavantage':
        stock_data = fetch_stock_data_alphavantage(symbols)
    elif data_source == 'akshare':
        stock_data = fetch_stock_data_akshare(symbols)
    elif data_source == 'tushare':
        stock_data = fetch_stock_data_tushare(symbols)
    else:
        logger.error(f"不支持的数据源: {data_source}")
        return
    
    if not stock_data:
        logger.error("未能获取任何股票数据，使用生成的样本数据进行训练")
        df = generate_sample_data(2000)
    else:
        # 准备训练数据
        df = prepare_training_data(stock_data)
        if df is None or len(df) < 1000:
            logger.warning("真实数据不足，补充生成样本数据")
            sample_df = generate_sample_data(2000)
            if df is not None:
                df = pd.concat([df, sample_df])
            else:
                df = sample_df
    
    # 最后检查数据是否有NaN值
    if df.isnull().any().any():
        logger.warning("数据中仍存在NaN值，进行最终填充")
        df = df.fillna(method='ffill').fillna(method='bfill')
        # 如果仍有NaN值，删除这些行
        df = df.dropna()
        
    logger.info(f"最终训练数据集大小: {df.shape}")
    
    # 准备特征和目标变量
    features = [
        'open', 'high', 'low', 'close', 'volume',
        'sma_5', 'sma_10', 'sma_20', 'sma_50', 'sma_200',
        'ema_12', 'ema_26', 'macd', 'macd_signal', 'macd_hist',
        'rsi', 'volatility_5', 'volatility_10', 'volatility_20',
        'bollinger_mid', 'bollinger_std', 'bollinger_upper', 'bollinger_lower',
        'price_change_1d', 'price_change_5d', 'price_change_10d', 'price_change_20d',
        'volume_change_1d', 'volume_change_5d', 'volume_sma_5', 'volume_sma_20'
    ]
    
    # 确保所有特征都存在
    for feature in features:
        if feature not in df.columns:
            logger.error(f"特征 '{feature}' 不在数据集中")
            return
    
    X = df[features]
    y_trend = df['trend']
    y_risk = df['risk']
    y_sentiment = df['sentiment']
    
    # 检查目标变量是否有足够的类别
    if len(y_trend.unique()) < 2 or len(y_risk.unique()) < 2 or len(y_sentiment.unique()) < 2:
        logger.error("目标变量类别不足，无法训练模型")
        return
    
    # 划分训练集和测试集
    try:
        X_train, X_test, y_trend_train, y_trend_test = train_test_split(X, y_trend, test_size=0.2, random_state=42)
        _, _, y_risk_train, y_risk_test = train_test_split(X, y_risk, test_size=0.2, random_state=42)
        _, _, y_sentiment_train, y_sentiment_test = train_test_split(X, y_sentiment, test_size=0.2, random_state=42)
    except Exception as e:
        logger.error(f"划分训练集和测试集时出错: {str(e)}")
        return
    
    # 标准化特征
    try:
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
    except Exception as e:
        logger.error(f"标准化特征时出错: {str(e)}")
        return
    
    # 训练趋势预测模型
    try:
        logger.info("训练趋势预测模型...")
        trend_model = RandomForestClassifier(n_estimators=100, random_state=42)
        trend_model.fit(X_train_scaled, y_trend_train)
        
        # 评估趋势模型
        y_trend_pred = trend_model.predict(X_test_scaled)
        trend_accuracy = accuracy_score(y_trend_test, y_trend_pred)
        logger.info(f"趋势模型准确率: {trend_accuracy:.4f}")
        logger.info(f"趋势模型分类报告:\n{classification_report(y_trend_test, y_trend_pred)}")
    except Exception as e:
        logger.error(f"训练趋势模型时出错: {str(e)}")
        return
    
    # 训练风险预测模型
    try:
        logger.info("训练风险预测模型...")
        risk_model = GradientBoostingClassifier(n_estimators=100, random_state=42)
        risk_model.fit(X_train_scaled, y_risk_train)
        
        # 评估风险模型
        y_risk_pred = risk_model.predict(X_test_scaled)
        risk_accuracy = accuracy_score(y_risk_test, y_risk_pred)
        logger.info(f"风险模型准确率: {risk_accuracy:.4f}")
        logger.info(f"风险模型分类报告:\n{classification_report(y_risk_test, y_risk_pred)}")
    except Exception as e:
        logger.error(f"训练风险模型时出错: {str(e)}")
        return
    
    # 训练情绪预测模型
    try:
        logger.info("训练情绪预测模型...")
        sentiment_model = RandomForestClassifier(n_estimators=100, random_state=42)
        sentiment_model.fit(X_train_scaled, y_sentiment_train)
        
        # 评估情绪模型
        y_sentiment_pred = sentiment_model.predict(X_test_scaled)
        sentiment_accuracy = accuracy_score(y_sentiment_test, y_sentiment_pred)
        logger.info(f"情绪模型准确率: {sentiment_accuracy:.4f}")
        logger.info(f"情绪模型分类报告:\n{classification_report(y_sentiment_test, y_sentiment_pred)}")
    except Exception as e:
        logger.error(f"训练情绪模型时出错: {str(e)}")
        return
    
    # 创建模型目录
    try:
        model_dir = os.path.dirname(settings.AI_MODEL_PATH)
        os.makedirs(model_dir, exist_ok=True)
        
        # 保存模型
        model_data = {
            'scaler': scaler,
            'trend_model': trend_model,
            'risk_model': risk_model,
            'sentiment_model': sentiment_model,
            'features': features,
            'training_date': datetime.now().strftime('%Y-%m-%d'),
            'data_source': data_source,
            'metrics': {
                'trend_accuracy': trend_accuracy,
                'risk_accuracy': risk_accuracy,
                'sentiment_accuracy': sentiment_accuracy
            }
        }
        
        joblib.dump(model_data, settings.AI_MODEL_PATH)
        logger.info(f"模型已保存到 {settings.AI_MODEL_PATH}")
    except Exception as e:
        logger.error(f"保存模型时出错: {str(e)}")
        return

def generate_sample_data(n_samples=1000):
    """生成示例训练数据"""
    # 生成日期序列
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_samples)
    dates = pd.date_range(start=start_date, end=end_date, periods=n_samples)
    
    # 生成特征
    data = {
        'date': dates,
        'close': np.random.normal(100, 10, n_samples).cumsum() + 1000,
        'open': np.zeros(n_samples),
        'high': np.zeros(n_samples),
        'low': np.zeros(n_samples),
        'volume': np.random.randint(1000000, 10000000, n_samples),
    }
    
    # 创建 DataFrame
    df = pd.DataFrame(data)
    df.set_index('date', inplace=True)
    
    # 确保没有负值或零值，这可能导致计算技术指标时出现问题
    df['close'] = df['close'].apply(lambda x: max(x, 0.01))
    df['volume'] = df['volume'].apply(lambda x: max(x, 1))
    
    # 生成开盘价、最高价和最低价
    for i in range(n_samples):
        close = df['close'].iloc[i]
        daily_volatility = close * 0.02  # 假设每日波动率为2%
        
        df['open'].iloc[i] = close * (1 + np.random.normal(0, 0.01))  # 开盘价
        df['high'].iloc[i] = close * (1 + abs(np.random.normal(0, 0.015)))  # 最高价
        df['low'].iloc[i] = close * (1 - abs(np.random.normal(0, 0.015)))  # 最低价
    
    # 确保 high >= open >= low 和 high >= close >= low
    df['high'] = df[['high', 'open', 'close']].max(axis=1)
    df['low'] = df[['low', 'open', 'close']].min(axis=1)
    
    # 确保所有值都是正数
    df['open'] = df['open'].apply(lambda x: max(x, 0.01))
    df['high'] = df['high'].apply(lambda x: max(x, 0.01))
    df['low'] = df['low'].apply(lambda x: max(x, 0.01))
    
    # 添加技术指标
    processed_df = add_technical_indicators(df)
    
    # 确保没有NaN值
    processed_df = processed_df.fillna(method='ffill').fillna(method='bfill')
    
    return processed_df

if __name__ == "__main__":
    train_models() 