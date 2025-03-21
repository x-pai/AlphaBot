"""
机器学习服务，用于使用训练好的模型进行预测
"""

import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
import os
import asyncio

from app.core.config import settings
from app.schemas.stock import AIAnalysis

class MLService:
    """机器学习服务类，用于使用训练好的模型进行预测"""
    
    def __init__(self):
        """初始化模型"""
        self.model_data = None
        self.load_model()
    
    def load_model(self):
        """加载模型"""
        try:
            if os.path.exists(settings.AI_MODEL_PATH):
                self.model_data = joblib.load(settings.AI_MODEL_PATH)
                print(f"成功加载模型: {settings.AI_MODEL_PATH}")
            else:
                print(f"模型文件不存在: {settings.AI_MODEL_PATH}")
        except Exception as e:
            print(f"加载模型时出错: {str(e)}")
    
    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        return await asyncio.to_thread(func, *args, **kwargs)
    
    async def analyze_stock(
        self, 
        symbol: str, 
        historical_data: pd.DataFrame,
        fundamentals: Dict[str, Any],
        technical_indicators: Dict[str, float]
    ) -> Optional[AIAnalysis]:
        """使用机器学习模型分析股票"""
        try:
            if self.model_data is None:
                print("模型未加载，无法进行分析")
                return None
            
            # 准备特征
            features = await self._run_sync(self._prepare_features, historical_data, technical_indicators)
            
            # 标准化特征
            scaler = self.model_data['scaler']
            X_scaled = await self._run_sync(scaler.transform, [features])
            
            # 预测
            trend_model = self.model_data['trend_model']
            risk_model = self.model_data['risk_model']
            sentiment_model = self.model_data['sentiment_model']
            
            trend_pred = await self._run_sync(trend_model.predict, X_scaled)
            trend_pred = trend_pred[0]
            
            risk_pred = await self._run_sync(risk_model.predict, X_scaled)
            risk_pred = risk_pred[0]
            
            sentiment_pred = await self._run_sync(sentiment_model.predict, X_scaled)
            sentiment_pred = sentiment_pred[0]
            
            # 获取预测概率
            trend_proba = await self._run_sync(trend_model.predict_proba, X_scaled)
            trend_proba = trend_proba[0].tolist()
            
            risk_proba = await self._run_sync(risk_model.predict_proba, X_scaled)
            risk_proba = risk_proba[0].tolist()
            
            sentiment_proba = await self._run_sync(sentiment_model.predict_proba, X_scaled)
            sentiment_proba = sentiment_proba[0].tolist()
            
            # 生成分析结果
            analysis = await self._run_sync(
                self._generate_analysis,
                symbol,
                historical_data,
                fundamentals,
                technical_indicators,
                trend_pred,
                risk_pred,
                sentiment_pred,
                trend_proba,
                risk_proba,
                sentiment_proba
            )
            
            return analysis
        except Exception as e:
            print(f"分析股票时出错: {str(e)}")
            return None
    
    def _prepare_features(
        self, 
        historical_data: pd.DataFrame,
        technical_indicators: Dict[str, float]
    ) -> List[float]:
        """准备模型输入特征"""
        # 获取模型所需特征
        model_features = self.model_data['features']
        
        # 准备特征值
        features = []
        for feature in model_features:
            if feature in technical_indicators:
                features.append(technical_indicators[feature])
            elif feature == 'close':
                features.append(historical_data['close'].iloc[-1])
            elif feature == 'volume':
                features.append(historical_data['volume'].iloc[-1])
            elif feature == 'sma_20':
                features.append(technical_indicators['SMA_20'])
            elif feature == 'sma_50':
                features.append(technical_indicators['SMA_50'])
            elif feature == 'rsi':
                features.append(technical_indicators['RSI'])
            elif feature == 'volatility':
                features.append(technical_indicators['Volatility'])
            elif feature == 'macd':
                features.append(technical_indicators['MACD'])
            else:
                # 如果缺少特征，使用0填充
                features.append(0)
        
        return features
    
    def _generate_analysis(
        self,
        symbol: str,
        historical_data: pd.DataFrame,
        fundamentals: Dict[str, Any],
        technical_indicators: Dict[str, float],
        trend_pred: int,
        risk_pred: int,
        sentiment_pred: int,
        trend_proba: List[float],
        risk_proba: List[float],
        sentiment_proba: List[float]
    ) -> AIAnalysis:
        """根据模型预测生成分析结果"""
        # 获取当前价格和变化
        current_price = historical_data['close'].iloc[-1]
        price_change = historical_data['close'].iloc[-1] - historical_data['close'].iloc[-2]
        price_change_percent = (price_change / historical_data['close'].iloc[-2]) * 100
        
        # 映射情绪预测
        sentiment_map = {0: "negative", 1: "neutral", 2: "positive"}
        sentiment = sentiment_map[sentiment_pred]
        
        # 映射风险预测
        risk_map = {0: "low", 1: "medium", 2: "high"}
        risk_level = risk_map[risk_pred]
        
        # 生成关键点
        key_points = []
        
        # 趋势预测关键点
        trend_confidence = max(trend_proba) * 100
        if trend_pred == 1:
            key_points.append(f"模型预测股票有{trend_confidence:.1f}%的概率上涨")
        else:
            key_points.append(f"模型预测股票有{trend_confidence:.1f}%的概率下跌")
        
        # 技术指标关键点
        if current_price > technical_indicators['SMA_50']:
            key_points.append(f"价格高于50日均线，显示上升趋势")
        else:
            key_points.append(f"价格低于50日均线，可能处于下降趋势")
        
        if technical_indicators['RSI'] > 70:
            key_points.append(f"RSI为{technical_indicators['RSI']:.2f}，表明可能超买")
        elif technical_indicators['RSI'] < 30:
            key_points.append(f"RSI为{technical_indicators['RSI']:.2f}，表明可能超卖")
        else:
            key_points.append(f"RSI为{technical_indicators['RSI']:.2f}，处于中性区间")
        
        # 风险预测关键点
        risk_confidence = risk_proba[risk_pred] * 100
        key_points.append(f"模型评估风险水平为{risk_level}，置信度{risk_confidence:.1f}%")
        
        # 生成建议
        if trend_pred == 1 and sentiment_pred == 2:
            recommendation = "模型建议考虑买入。技术指标和预测情绪都积极。"
        elif trend_pred == 0 and sentiment_pred == 0:
            recommendation = "模型建议考虑卖出。技术指标和预测情绪都消极。"
        else:
            recommendation = "模型建议持有观望。市场信号不明确。"
        
        # 生成摘要
        company_name = fundamentals.get('Name', symbol)
        summary = (
            f"机器学习模型分析：{company_name}目前交易价格为{current_price:.2f}，"
            f"较前一交易日{price_change_percent:.2f}%。"
            f"模型预测趋势为{'上涨' if trend_pred == 1 else '下跌'}，"
            f"情绪为{sentiment}，风险水平为{risk_level}。"
        )
        
        return AIAnalysis(
            summary=summary,
            sentiment=sentiment,
            keyPoints=key_points,
            recommendation=recommendation,
            riskLevel=risk_level
        )

    def predict_time_series(self, features: pd.DataFrame, days: int = 5) -> List[float]:
        """预测未来几天的股票价格
        
        Args:
            features: 包含历史价格和技术指标的DataFrame
            days: 预测未来的天数
            
        Returns:
            未来几天的预测价格列表
        """
        try:
            if self.model_data is None:
                print("模型未加载，使用简单线性预测")
                return self._simple_linear_prediction(features, days)
                
            # 尝试使用时间序列模型进行预测
            # 注意：这里假设模型已经包含了时间序列预测功能
            # 如果实际模型不支持，则回退到简单线性预测
            if 'time_series_model' in self.model_data:
                model = self.model_data['time_series_model']
                
                # 准备特征
                X = self._prepare_time_series_features(features)
                
                # 预测
                predictions = model.predict(X, n_periods=days)
                
                # 返回预测结果
                return predictions.tolist()
            else:
                # 如果没有时间序列模型，使用简单线性预测
                return self._simple_linear_prediction(features, days)
                
        except Exception as e:
            print(f"时间序列预测出错: {str(e)}")
            # 出错时使用简单线性预测
            return self._simple_linear_prediction(features, days)
            
    def _prepare_time_series_features(self, features: pd.DataFrame) -> np.ndarray:
        """准备时间序列预测的特征
        
        Args:
            features: 包含历史价格和技术指标的DataFrame
            
        Returns:
            用于时间序列预测的特征数组
        """
        # 这里根据实际模型需要准备特征
        # 简单示例：使用最近的收盘价
        if 'close' in features.columns:
            return features['close'].values
        else:
            raise ValueError("特征中缺少收盘价数据")
            
    def _simple_linear_prediction(self, features: pd.DataFrame, days: int = 5) -> List[float]:
        """使用简单线性回归预测未来价格
        
        Args:
            features: 包含历史价格的DataFrame
            days: 预测未来的天数
            
        Returns:
            未来几天的预测价格列表
        """
        if 'close' not in features.columns:
            # 如果没有收盘价，返回随机值
            last_value = 100.0
            return [last_value * (1 + np.random.normal(0, 0.01)) for _ in range(days)]
            
        # 获取最近的收盘价
        recent_prices = features['close'].tail(10).values
        
        if len(recent_prices) < 2:
            # 数据不足，返回最后一个价格的小幅波动
            last_price = recent_prices[-1]
            return [last_price * (1 + np.random.normal(0, 0.01)) for _ in range(days)]
            
        # 计算平均变化率
        changes = np.diff(recent_prices) / recent_prices[:-1]
        avg_change = np.mean(changes)
        
        # 使用平均变化率预测未来价格
        last_price = recent_prices[-1]
        predictions = []
        
        current_price = last_price
        for _ in range(days):
            # 添加一些随机波动
            change = avg_change + np.random.normal(0, abs(avg_change) * 0.5)
            current_price = current_price * (1 + change)
            predictions.append(current_price)
            
        return predictions

    async def predict_trend_probability(
        self, 
        features: pd.DataFrame,
        symbol: str = None, 
        historical_data: pd.DataFrame = None
    ) -> Dict[str, Any]:
        """预测股票趋势概率
        
        Args:
            features: 包含技术指标的DataFrame或技术指标字典
            symbol: 可选的股票代码
            historical_data: 可选的历史价格数据
            
        Returns:
            包含趋势预测概率的字典或概率值
        """
        try:
            if self.model_data is None:
                print("模型未加载，无法预测趋势概率")
                return 0.5  # 返回中性概率
            
            # 处理不同类型的输入
            if isinstance(features, pd.DataFrame):
                # 如果输入是DataFrame，直接使用
                X = features.values.astype(float)
            elif isinstance(features, dict):
                # 如果输入是技术指标字典，转换为特征列表
                if historical_data is not None:
                    X = np.array([self._prepare_features(historical_data, features)])
                else:
                    # 如果没有历史数据，直接使用字典值
                    X = np.array([[v for v in features.values()]])
            else:
                raise ValueError("不支持的特征类型")
            
            # 标准化特征
            scaler = self.model_data.get('scaler')
            if scaler:
                X_scaled = scaler.transform(X)
            else:
                X_scaled = X
            
            # 预测趋势概率
            trend_model = self.model_data['trend_model']
            trend_proba = await self._run_sync(trend_model.predict_proba, X_scaled)
            
            # 获取看涨概率
            bullish_proba = trend_proba[0][1] if len(trend_proba[0]) > 1 else 0.5
            
            # 如果是从ai_service.py的_analyze_intraday_with_ml调用，直接返回概率值
            if historical_data is None and symbol is None:
                return bullish_proba
            
            # 否则返回完整的结果字典
            return {
                "trend": "bullish" if bullish_proba > 0.5 else "bearish",
                "probability": {
                    "bearish": 1.0 - bullish_proba,
                    "bullish": bullish_proba
                }
            }
        except Exception as e:
            print(f"预测趋势概率时出错: {str(e)}")
            # 出错时返回中性概率
            if historical_data is None and symbol is None:
                return 0.5
            return {"error": str(e)} 