#!/usr/bin/env python
"""
分析模式示例脚本

这个脚本展示了如何使用AlphaBot的三种不同分析模式。
"""

import asyncio
import os
import sys
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_service import AIService
from app.core.config import settings

async def analyze_with_all_modes(symbol: str, data_source: str = None):
    """使用所有分析模式分析股票"""
    print(f"\n{'='*80}")
    print(f"分析股票: {symbol} (数据源: {data_source or settings.DEFAULT_DATA_SOURCE})")
    print(f"{'='*80}")
    
    # 使用三种不同的分析模式
    modes = [ "rule"]
    
    for mode in modes:
        print(f"\n{'-'*40}")
        print(f"分析模式: {mode}")
        print(f"{'-'*40}")
        
        start_time = datetime.now()
        analysis = await AIService.analyze_stock(symbol, data_source, mode)
        end_time = datetime.now()
        
        if analysis:
            print(f"分析完成! 耗时: {(end_time - start_time).total_seconds():.2f} 秒")
            print(f"\n摘要: {analysis.summary}")
            print(f"情绪: {analysis.sentiment}")
            print(f"风险等级: {analysis.riskLevel}")
            print("\n关键点:")
            for point in analysis.keyPoints:
                print(f"- {point}")
            print(f"\n建议: {analysis.recommendation}")
        else:
            print(f"分析失败!")

async def main():
    """主函数"""
    # 美股示例
    # await analyze_with_all_modes("AAPL", "alphavantage")
    
    # A股示例
    await analyze_with_all_modes("000001.SZ", "akshare")
    
    # 港股示例
    # await analyze_with_all_modes("000001.SZ", "akshare")

if __name__ == "__main__":
    # 检查是否配置了必要的API密钥
    if settings.OPENAI_API_KEY == "":
        print("警告: 未设置OPENAI_API_KEY，LLM分析模式可能无法正常工作")
    
    # 检查是否已训练模型
    import os.path
    if not os.path.exists(settings.AI_MODEL_PATH):
        print(f"警告: 未找到模型文件 {settings.AI_MODEL_PATH}，ML分析模式可能无法正常工作")
        print("请先运行 'python train_model.py' 训练模型")
    
    # 运行主函数
    asyncio.run(main()) 