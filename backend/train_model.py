"""
运行模型训练脚本

免责声明：
1. 本脚本训练的模型仅供学习和研究使用，不构成任何投资建议或交易指导。
2. 股票市场受多种因素影响，任何预测模型都无法完全准确地预测市场走势。
3. 模型的预测结果基于历史数据，过去的表现不代表未来的结果。
4. 使用本模型进行投资决策需自行承担风险，开发者不对因使用本模型导致的任何
   直接或间接损失负责。
5. 在做出任何投资决策前，建议咨询专业的投资顾问，并进行充分的研究和分析。
"""

import os
import sys
import argparse

# 添加项目根目录到 Python 路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.utils.train_model import train_models

if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='训练股票分析机器学习模型')
    parser.add_argument('--data-source', type=str, default='akshare', 
                        choices=['alphavantage', 'akshare', 'tushare'],
                        help='数据源 (alphavantage, akshare, tushare)')
    parser.add_argument('--symbols', type=str, nargs='+',
                        help='股票代码列表，例如 --symbols AAPL MSFT GOOGL 或 --symbols 000001.SZ 600000.SH')
    
    args = parser.parse_args()
    
    print(f"开始训练股票分析模型，使用{args.data_source}数据源...")
    
    # 调用训练函数
    train_models(data_source=args.data_source, symbols=args.symbols)
    
    print("模型训练完成！") 