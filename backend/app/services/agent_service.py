from typing import List, Dict, Any, Optional
import json
from pydantic import BaseModel
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.stock_service import StockService
from app.services.ai_service import AIService
from app.services.openai_service import OpenAIService
from app.services.user_service import UserService
from app.middleware.logging import logger

# 创建OpenAI服务实例
openai_service = OpenAIService()

class AgentTool(BaseModel):
    """智能体工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]

class AgentMessage(BaseModel):
    """智能体消息"""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

class AgentSession(BaseModel):
    """智能体会话"""
    id: str
    messages: List[AgentMessage]
    user_id: str
    created_at: str
    updated_at: str

class AgentService:
    """AlphaBot智能体服务"""
    
    # 系统提示词
    SYSTEM_PROMPT = """你是AlphaBot，一个专业的股票分析和投资顾问智能体。
你可以帮助用户分析股票，提供市场洞察，并根据用户需求执行各种金融分析任务。
在回答用户问题时，你应该：
1. 分析用户意图，理解他们真正需要什么
2. 使用合适的工具获取必要信息
3. 基于专业知识和获取的数据提供高质量回答
4. 在不确定时，主动询问澄清问题

你可以使用多种工具来帮助用户，包括股票搜索、价格查询、技术分析和AI预测。
"""
    
    @staticmethod
    def get_available_tools() -> List[AgentTool]:
        """获取可用工具列表"""
        tools = [
            AgentTool(
                name="search_stocks",
                description="搜索股票信息，通过关键词查找股票",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，可以是股票名称、代码或行业"
                    }
                }
            ),
            AgentTool(
                name="get_stock_info",
                description="获取股票的详细信息",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    }
                }
            ),
            AgentTool(
                name="get_stock_price_history",
                description="获取股票历史价格数据",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "interval": {
                        "type": "string",
                        "description": "时间间隔：daily, weekly, monthly",
                        "enum": ["daily", "weekly", "monthly"]
                    },
                    "range": {
                        "type": "string",
                        "description": "时间范围：1m, 3m, 6m, 1y, 5y",
                        "enum": ["1m", "3m", "6m", "1y", "5y"]
                    }
                }
            ),
            AgentTool(
                name="analyze_stock",
                description="使用AI分析股票并提供预测",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "analysis_mode": {
                        "type": "string",
                        "description": "分析类型：基于规则、机器学习或大语言模型",
                        "enum": ["rule", "ml", "llm"]
                    },
                    "data_source": {
                        "type": "string",
                        "description": "数据源：tushare, akshare, alphavantage, hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
                    }
                }
            ),
            AgentTool(
                name="get_market_news",
                description="获取市场新闻和公告",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "相关股票代码，可选"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回新闻条数"
                    }
                }
            )
        ]
        return tools
    
    @classmethod
    async def execute_tool(cls, tool_name: str, params: Dict[str, Any], db: Session, user: User) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            # 检查用户使用限制
            can_use = await UserService.check_user_usage(user, db)
            if not can_use:
                return {
                    "error": "已达到今日使用限制，请明天再试或升级账户"
                }
            
            # 根据工具名执行对应功能
            if tool_name == "search_stocks":
                results = await StockService.search_stocks(
                    query=params.get("query", ""),
                    data_source=params.get("data_source", ""),
                    db=db
                )
                return {"results": [stock.to_dict() for stock in results]}
            
            elif tool_name == "get_stock_info":
                stock = await StockService.get_stock_info(
                    symbol=params.get("symbol", ""),
                    data_source=params.get("data_source", "")
                )
                if not stock:
                    return {"error": f"未找到股票: {params.get('symbol')}"}
                return {"stock": stock.to_dict()}
            
            elif tool_name == "get_stock_price_history":
                history = await StockService.get_stock_price_history(
                    symbol=params.get("symbol", ""),
                    interval=params.get("interval", "daily"),
                    range=params.get("range", "1m"),
                    data_source=params.get("data_source", "")
                )
                return {"history": history}
            
            elif tool_name == "analyze_stock":
                analysis = await AIService.analyze_stock(
                    symbol=params.get("symbol", ""),
                    data_source=params.get("data_source", ""),
                    analysis_mode=params.get("analysis_mode", "llm")
                )
                # 记录用户使用
                await UserService.increment_usage(user, db)
                return {"analysis": analysis}
            
            elif tool_name == "get_market_news":
                news = await StockService.get_market_news(
                    db=db,
                    symbol=params.get("symbol"),
                    limit=params.get("limit", 5)
                )
                return {"news": news}
            
            else:
                return {"error": f"未知工具: {tool_name}"}
                
        except Exception as e:
            logger.error(f"工具执行错误 {tool_name}: {str(e)}")
            return {"error": f"工具执行错误: {str(e)}"}
    
    @classmethod
    async def process_message(cls, user_message: str, session_id: str, db: Session, user: User) -> Dict[str, Any]:
        """处理用户消息"""
        try:
            # 1. 构建会话历史
            messages = cls._build_messages(user_message, session_id, db)
            
            # 2. 调用OpenAI服务进行处理
            llm_response = await openai_service.chat_completion(
                messages=messages,
                tools=cls.get_available_tools(),
                tool_choice="auto"
            )
            
            # 3. 解析LLM响应
            assistant_message = llm_response.get("choices", [{}])[0].get("message", {})
            
            # 4. 处理工具调用
            if assistant_message.get("tool_calls"):
                tool_results = []
                for tool_call in assistant_message.get("tool_calls", []):
                    function = tool_call.get("function", {})
                    tool_name = function.get("name")
                    try:
                        arguments = json.loads(function.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    # 执行工具
                    result = await cls.execute_tool(tool_name, arguments, db, user)
                    
                    # 添加工具结果
                    tool_results.append({
                        "tool_call_id": tool_call.get("id"),
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                
                # 将工具结果添加到消息历史
                messages.extend(tool_results)
                
                # 再次调用LLM获取最终回复
                second_response = await openai_service.chat_completion(
                    messages=messages,
                    tools=cls.get_available_tools(),
                    tool_choice="none"  # 禁止再次调用工具
                )
                
                final_message = second_response.get("choices", [{}])[0].get("message", {})
                content = final_message.get("content", "")
            else:
                # 直接使用LLM回复
                content = assistant_message.get("content", "")
            
            # 5. 保存会话历史
            cls._save_conversation(session_id, user.id, messages, content, db)
            
            return {
                "content": content,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"处理消息错误: {str(e)}")
            return {
                "content": f"处理您的请求时出错: {str(e)}",
                "session_id": session_id,
                "error": str(e)
            }
    
    @classmethod
    def _build_messages(cls, user_message: str, session_id: str, db: Session) -> List[Dict[str, Any]]:
        """构建消息历史"""
        # 系统消息
        messages = [
            {"role": "system", "content": cls.SYSTEM_PROMPT}
        ]
        
        # TODO: 从数据库加载历史消息
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    @classmethod
    def _save_conversation(cls, session_id: str, user_id: int, messages: List[Dict[str, Any]], 
                         assistant_response: str, db: Session) -> None:
        """保存会话历史"""
        # TODO: 实现会话保存到数据库
        pass 