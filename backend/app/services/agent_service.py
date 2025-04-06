from typing import List, Dict, Any, Optional
import json
from pydantic import BaseModel
from fastapi import HTTPException
from sqlalchemy.orm import Session
import uuid

from app.models.user import User
from app.services.stock_service import StockService
from app.services.ai_service import AIService
from app.services.openai_service import OpenAIService
from app.services.user_service import UserService
from app.middleware.logging import logger
from app.services.search_service import search_service
from app.core.config import settings

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

你拥有以下核心能力：
1. 股票搜索与筛选：帮助用户找到符合特定条件的股票
2. 技术分析：分析价格趋势、形态和技术指标
3. 基本面分析：解读财务数据、评估公司健康状况和增长前景
4. 新闻分析：提供市场新闻摘要和相关性分析
5. AI预测：基于历史数据和市场情况提供预测

在回答用户问题时，你应该：
1. 分析用户意图，理解他们真正需要什么
2. 使用合适的工具获取必要信息
3. 基于专业知识和获取的数据提供高质量回答
4. 清晰解释你的分析过程和结论
5. 在不确定时，主动询问澄清问题

记住以下投资原则：
1. 风险管理永远是第一位的
2. 投资决策应该基于数据而非情绪
3. 分散投资是降低风险的重要策略
4. 长期投资通常优于短期投机
5. 市场有效性意味着没有"稳赚不赔"的策略

你需要明确地告知用户，所有分析都是基于历史数据和当前市场情况，不构成投资建议。投资有风险，入市需谨慎。
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
                    },
                    "data_source": {
                        "type": "string",
                        "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
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
                    },
                    "data_source": {
                        "type": "string",
                        "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
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
                    },
                    "data_source": {
                        "type": "string",
                        "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
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
                        "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
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
            ),
            AgentTool(
                name="get_stock_fundamentals",
                description="获取股票的基本面数据，包括财务数据、估值指标等",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "report_type": {
                        "type": "string",
                        "description": "报表类型，all为所有数据",
                        "enum": ["all", "balance_sheet", "income", "cash_flow", "performance", "key_metrics"]
                    },
                    "data_source": {
                        "type": "string",
                        "description": "数据源：tushare, 默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage"]
                    }
                }
            )
        ]
        
        # 如果搜索API已启用，添加网络搜索工具
        if settings.SEARCH_API_ENABLED:
            tools.append(
                AgentTool(
                    name="search_web",
                    description="在网络上搜索信息",
                    parameters={
                        "query": {
                            "type": "string",
                            "description": "要搜索的查询"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "要返回的结果数",
                            "default": 5
                        }
                    }
                )
            )
            
        return tools
    
    @classmethod
    async def execute_tool(cls, tool_name: str, params: Dict[str, Any], db: Session, user: User) -> Dict[str, Any]:
        """执行工具调用"""
        try:
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
            
            elif tool_name == "get_stock_fundamentals":
                fundamentals = await StockService.get_stock_fundamentals(
                    symbol=params.get("symbol", ""),
                    report_type=params.get("report_type", "all"),
                    data_source=params.get("data_source", "")
                )
                return {"fundamentals": fundamentals}
            
            elif tool_name == "search_web":
                # 处理Web搜索调用
                query = params.get("query", "")
                limit = params.get("limit", 5)
                
                if not settings.SEARCH_API_ENABLED:
                    return {"error": "搜索API未启用"}
                
                # 执行搜索
                search_results = await search_service.search(query, limit)
                
                # 返回搜索结果
                if search_results.get("success", False):
                    return {
                        "query": query,
                        "results": search_results.get("results", []),
                        "result_count": search_results.get("result_count", 0),
                        "engine": search_results.get("engine", "")
                    }
                else:
                    return {"error": search_results.get("error", "搜索失败")}
            
            else:
                return {"error": f"未知工具: {tool_name}"}
                
        except Exception as e:
            logger.error(f"工具执行错误 {tool_name}: {str(e)}")
            return {"error": f"工具执行错误: {str(e)}"}
    
    @classmethod
    async def _format_tool_result_for_display(cls, tool_name: str, result: Dict[str, Any]) -> str:
        """格式化工具结果显示"""
        try:
            if tool_name == "search_web":
                # 为搜索结果创建Markdown格式
                if "error" in result:
                    return f"搜索错误: {result['error']}"
                
                query = result.get("query", "")
                results = result.get("results", [])
                
                if not results:
                    return f"未找到与{query}相关的搜索结果。"
                
                # 创建Markdown格式的搜索结果
                markdown = f"### 搜索结果：{query}\n\n"
                
                for idx, item in enumerate(results[:3], 1):
                    title = item.get("title", "无标题")
                    link = item.get("link", "#")
                    snippet = item.get("snippet", "无描述")
                    
                    markdown += f"{idx}. **[{title}]({link})**\n"
                    markdown += f"   {snippet}\n\n"
                
                if len(results) > 3:
                    markdown += f"*还有 {len(results) - 3} 条相关结果未显示*\n"
                    
                return markdown
            
            # 处理其他工具的格式化逻辑
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"格式化工具结果出错: {str(e)}")
            return str(result)
            
    @classmethod
    async def process_message(cls, user_message: str, session_id: str, db: Session, user: User, enable_web_search: bool = False) -> Dict[str, Any]:
        """处理用户消息"""
        try:
            # 检查是否是特殊命令（例如 "/search 查询内容"）
            if user_message.startswith("/search "):
                # 提取搜索查询
                search_query = user_message[8:].strip()
                if not search_query:
                    return {
                        "content": "请输入要搜索的内容",
                        "session_id": session_id
                    }
                    
                # 执行搜索
                if not settings.SEARCH_API_ENABLED:
                    return {
                        "content": "搜索功能未启用",
                        "session_id": session_id
                    }
                
                search_results = await search_service.search(search_query, 5)
                # 格式化搜索结果
                formatted_result = await cls._format_tool_result_for_display("search_web", {
                    "query": search_query,
                    "results": search_results.get("results", [])
                })
                
                # 保存搜索指令和结果到会话历史
                user_msg = {"role": "user", "content": user_message}
                assistant_msg = {"role": "assistant", "content": f'我搜索了"{search_query}"'}
                messages = [user_msg, assistant_msg]
                cls._save_conversation(session_id, user.id, messages, assistant_msg["content"], db)
                
                return {
                    "content": f'我搜索了"{search_query}"',
                    "session_id": session_id,
                    "tool_outputs": [formatted_result]
                }
            
            # 1. 构建会话历史
            messages = cls._build_messages(user_message, session_id, db)
            
            # 如果启用了联网搜索，修改用户消息添加指令
            if enable_web_search:
                # 最后一条用户消息添加联网搜索指令
                last_user_message_index = next((i for i in range(len(messages)-1, -1, -1) if messages[i]["role"] == "user"), -1)
                if last_user_message_index >= 0:
                    original_content = messages[last_user_message_index]["content"]
                    messages[last_user_message_index]["content"] = f"{original_content}\n\n请使用search_web工具在网络上搜索相关信息来回答我的问题。"
            
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
                formatted_results = []
                
                # 逐个处理工具调用
                for tool_call in assistant_message.get("tool_calls", []):
                    function = tool_call.get("function", {})
                    function_name = function.get("name")
                    
                    # 解析参数
                    try:
                        arguments = json.loads(function.get("arguments", "{}"))
                    except Exception as e:
                        logger.error(f"解析工具参数出错: {str(e)}")
                        arguments = {}
                    
                    # 执行工具
                    logger.info(f"执行工具: {function_name}, 参数: {arguments}")
                    tool_result = await cls.execute_tool(function_name, arguments, db, user)
                    
                    # 格式化结果以供前端显示
                    formatted_result = await cls._format_tool_result_for_display(function_name, tool_result)
                    if formatted_result:
                        formatted_results.append(formatted_result)
                    
                    # 创建工具结果供后续处理
                    result = {
                        "tool_call_id": tool_call.get("id"),
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    }
                    tool_results.append(result)
                
                # 将所有工具结果添加到消息历史中
                all_messages = messages + [assistant_message] + tool_results
                
                # 再次调用LLM生成最终回复
                final_response = await openai_service.chat_completion(
                    messages=all_messages
                )
                
                # 提取最终回复
                final_message = final_response.get("choices", [{}])[0].get("message", {})
                content = final_message.get("content", "无法生成回复")
                
                # 保存整个对话历史到数据库
                cls._save_conversation(session_id, user.id, [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": content},
                ], content, db)
                
                # 返回结果
                return {
                    "content": content,
                    "session_id": session_id,
                    "tool_outputs": formatted_results  # 添加格式化后的工具输出
                }
            else:
                # 没有工具调用，直接返回助手的回复
                content = assistant_message.get("content", "无法生成回复")
                
                # 保存对话到数据库
                cls._save_conversation(session_id, user.id, [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": content}
                ], content, db)
                
                return {
                    "content": content,
                    "session_id": session_id
                }
        except Exception as e:
            logger.error(f"处理消息出错: {str(e)}")
            return {
                "content": f"处理消息时出错: {str(e)}",
                "session_id": session_id,
                "error": str(e)
            }
    
    @classmethod
    def _build_messages(cls, user_message: str, session_id: str, db: Session) -> List[Dict[str, Any]]:
        """构建消息历史"""
        from app.models.conversation import Conversation
        from datetime import datetime
        
        # 获取当前日期时间
        current_datetime = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        
        # 系统消息，添加当前日期时间
        system_prompt = cls.SYSTEM_PROMPT + f"\n\n当前日期时间：{current_datetime}"
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 从数据库加载历史消息
        try:
            # 获取最近的10条会话记录作为上下文
            conversations = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).order_by(Conversation.created_at.desc()).limit(10).all()
            
            # 倒序排列，最早的消息在前
            conversations.reverse()
            
            # 添加历史消息，保持对话上下文
            for conv in conversations:
                if conv.user_message:
                    messages.append({"role": "user", "content": conv.user_message})
                if conv.assistant_response:
                    messages.append({"role": "assistant", "content": conv.assistant_response})
                    
                # 如果有工具调用记录，也添加到消息历史中
                if conv.tool_calls:
                    try:
                        tool_calls_data = json.loads(conv.tool_calls)
                        for tool_call in tool_calls_data:
                            messages.append(tool_call)
                    except:
                        # 如果解析失败，忽略这条工具调用记录
                        pass
                        
        except Exception as e:
            logger.error(f"加载会话历史出错: {str(e)}")
            # 如果出错，仅使用系统提示和当前用户消息
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    @classmethod
    def _save_conversation(cls, session_id: str, user_id: int, messages: List[Dict[str, Any]], 
                         assistant_response: str, db: Session) -> None:
        """保存会话历史"""
        from app.models.conversation import Conversation
        from datetime import datetime
        
        try:
            # 提取用户消息
            user_message = next(
                (msg.get("content", "") for msg in messages if msg.get("role") == "user"),
                ""
            )
            
            # 提取工具调用
            tool_calls = [
                msg for msg in messages 
                if msg.get("role") == "tool" or msg.get("tool_calls") is not None
            ]
            
            # 创建新的会话记录
            conversation = Conversation(
                session_id=session_id,
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                tool_calls=json.dumps(tool_calls) if tool_calls else None,
                created_at=datetime.now()
            )
            
            # 保存到数据库
            db.add(conversation)
            db.commit()
            
        except Exception as e:
            logger.error(f"保存会话历史出错: {str(e)}")
            db.rollback()

    async def get_agent_tools(self):
        """获取代理可用的工具列表"""
        tools = []
        
        # 添加搜索工具（如果启用）
        if settings.SEARCH_API_ENABLED:
            search_tool = {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "在网络上搜索信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "要搜索的查询"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "要返回的结果数",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
            tools.append(search_tool)
            
        # 添加其他工具...
        
        return tools
    
    async def process_agent_tools(self, tool_calls):
        """处理代理工具调用"""
        responses = []
        
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            function_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
            
            if function_name == "search_web":
                # 处理Web搜索调用
                query = function_args.get("query")
                limit = function_args.get("limit", 5)
                
                try:
                    # 执行搜索
                    search_results = await search_service.search(query, limit)
                    
                    # 格式化结果为代理可读的格式
                    if search_results.get("success", False):
                        results_formatted = []
                        for result in search_results.get("results", []):
                            results_formatted.append({
                                "title": result.get("title", ""),
                                "link": result.get("link", ""),
                                "snippet": result.get("snippet", ""),
                                "source": result.get("source", "")
                            })
                        
                        # 返回Markdown格式的结果，便于前端解析
                        markdown_response = f"""我从网络上找到了以下与"{query}"相关的信息：
                        
```json
{json.dumps({"query": query, "results": results_formatted}, ensure_ascii=False, indent=2)}
```

以下是结果的摘要：
"""
                        
                        # 为每个结果添加简要描述
                        for idx, result in enumerate(results_formatted[:3], 1):
                            markdown_response += f"\n{idx}. **{result['title']}** - {result['snippet'][:100]}...\n"
                            
                        if len(results_formatted) > 3:
                            markdown_response += f"\n还有 {len(results_formatted) - 3} 个更多结果。"
                        
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": markdown_response
                        }
                    else:
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": f"搜索失败：{search_results.get('error', '未知错误')}"
                        }
                except Exception as e:
                    logger.error(f"处理搜索工具调用错误: {str(e)}")
                    response = {
                        "tool_call_id": tool_call.get("id"),
                        "output": f"处理搜索请求时发生错误: {str(e)}"
                    }
                
                responses.append(response)
            else:
                # 处理现有工具调用
                try:
                    # 执行工具，复用现有的execute_tool方法
                    result = await self.execute_tool(function_name, function_args, None, None)
                    
                    # 格式化结果
                    if "error" in result:
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": f"工具执行错误: {result['error']}"
                        }
                    else:
                        # 将结果转为JSON字符串
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": json.dumps(result, ensure_ascii=False)
                        }
                    
                    responses.append(response)
                except Exception as e:
                    logger.error(f"处理工具调用 {function_name} 错误: {str(e)}")
                    responses.append({
                        "tool_call_id": tool_call.get("id"),
                        "output": f"处理工具调用时发生错误: {str(e)}"
                    })
            
        return responses 