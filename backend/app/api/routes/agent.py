from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional, AsyncGenerator
from pydantic import BaseModel
import uuid
import json
import asyncio
import time
from fastapi import BackgroundTasks

from app.db.session import get_db
from app.services.agent_service import AgentService
from app.api.routes.user import get_current_user
from app.models.user import User
from app.utils.response import api_response
from app.services.search_service import search_service
from app.api.dependencies import check_web_search_limit, check_usage_limit
from app.core.config import settings

router = APIRouter()

class AgentMessageRequest(BaseModel):
    """智能体消息请求"""
    content: str
    session_id: Optional[str] = None
    enable_web_search: Optional[bool] = False
    stream: Optional[bool] = False
    model: Optional[str] = None

class AgentMessageResponse(BaseModel):
    """智能体消息响应"""
    content: str
    session_id: str
    error: Optional[str] = None

class AgentToolRequest(BaseModel):
    """智能体工具调用请求"""
    tool_calls: List[Dict[str, Any]]

@router.post("/chat")
async def agent_chat(
    request: AgentMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """与智能体对话"""
    try:
        # 如果没有提供会话ID，生成一个新的
        session_id = request.session_id or str(uuid.uuid4())
        
        # 检查是否需要联网搜索
        enable_web_search = request.enable_web_search
        
        # 如果需要联网搜索，检查用户权限
        if enable_web_search:
            await check_web_search_limit(current_user)
        
        # 如果启用流式传输
        if request.stream:
            return StreamingResponse(
                stream_agent_response(
                    user_message=request.content,
                    session_id=session_id,
                    db=db,
                    user=current_user,
                    enable_web_search=enable_web_search,
                    model=request.model
                ),
                media_type="application/x-ndjson"
            )
        
        # 非流式传输的原有逻辑
        response = await AgentService.process_message(
            user_message=request.content,
            session_id=session_id,
            db=db,
            user=current_user,
            enable_web_search=enable_web_search,
            model=request.model
        )
        
        return api_response(data=response)
    except HTTPException as he:
        return api_response(
            success=False,
            error=he.detail
        )
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        )

@router.get("/models", response_model=Dict[str, Any])
async def get_available_models(
    current_user: User = Depends(get_current_user)
):
    """获取后端配置的可用模型列表"""
    try:
        raw = settings.OPENAI_AVAILABLE_MODELS or ""
        models = [m.strip() for m in raw.split(",") if m.strip()] or [settings.OPENAI_MODEL]
        default_model = settings.OPENAI_MODEL
        return api_response(data={
            "models": models,
            "default": default_model
        })
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        )

async def stream_agent_response(
    user_message: str,
    session_id: str,
    db: Session,
    user: User,
    enable_web_search: bool = False,
    model: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """流式响应智能体消息"""
    try:
        # 发送开始信号
        yield json.dumps({
            "type": "start",
            "session_id": session_id,
            "timestamp": int(time.time() * 1000)
        }) + "\n"
        
        # 构建消息历史
        messages = AgentService._build_messages(user_message, session_id, db)
        
        # 可选：在最后一条用户消息中注入联网搜索提示
        if enable_web_search:
            last_user_message_index = next((i for i in range(len(messages) - 1, -1, -1) if messages[i]["role"] == "user"), -1)
            if last_user_message_index >= 0:
                original_content = messages[last_user_message_index]["content"]
                messages[last_user_message_index]["content"] = (
                    f"{original_content}\n\n请优先考虑使用 search_web 工具在网络上搜索必要信息后再作答。"
                )
        
        # 发送思考状态
        yield json.dumps({
            "type": "thinking",
            "content": "正在分析数据...",
            "timestamp": int(time.time() * 1000)
        }) + "\n"
        
        # 迭代式工具调用与回复生成循环
        formatted_results: List[str] = []
        while True:
            # 获取LLM响应（先探测是否有工具调用）
            from app.services.openai_service import OpenAIService
            openai_service = OpenAIService()
            probe = await openai_service.chat_completion(
                messages=messages,
                model=model,
                tools=AgentService.get_available_tools(),
                tool_choice="auto"
            )
            assistant_message = probe.get("choices", [{}])[0].get("message", {})
            tool_calls = assistant_message.get("tool_calls") or []
            
            # 如果没有工具调用，则认为是最终回复
            if not tool_calls:
                # 直接消费 OpenAI 流，周期性输出 delta
                aggregated = ""
                async for delta in openai_service.chat_completion_stream(
                    messages=messages,
                    model=model,
                    tools=AgentService.get_available_tools(),
                    tool_choice="auto"
                ):
                    aggregated += delta
                    yield json.dumps({
                        "type": "delta",
                        "content": delta,
                        "session_id": session_id,
                        "timestamp": int(time.time() * 1000)
                    }) + "\n"

                # 发送最终回复
                final_content = aggregated or "无法生成回复"
                yield json.dumps({
                    "type": "content",
                    "content": final_content,
                    "session_id": session_id,
                    "tool_outputs": formatted_results if formatted_results else None,
                    "timestamp": int(time.time() * 1000)
                }) + "\n"
                
                # 保存会话历史
                AgentService._save_conversation(
                    session_id,
                    user.id,
                    messages,
                    final_content,
                    db,
                )
                
                # 发送结束信号
                yield json.dumps({
                    "type": "end",
                    "session_id": session_id,
                    "timestamp": int(time.time() * 1000)
                }) + "\n"
                break
            
            # 有工具调用：先把包含 tool_calls 的assistant消息加入历史
            messages.append(assistant_message)
            # messages.append({
            #     "role": "assistant",
            #     "content": assistant_message.get("content") or "",
            # })
            
            # 发送工具调用开始信号
            yield json.dumps({
                "type": "tool_calls",
                "tool_calls": tool_calls,
                "timestamp": int(time.time() * 1000)
            }) + "\n"
            
            # 依次执行工具并把结果追加为tool消息
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                function_name = function.get("name")
                
                try:
                    arguments = json.loads(function.get("arguments", "{}"))
                except Exception as e:
                    arguments = {}
                
                # 发送工具执行开始信号
                yield json.dumps({
                    "type": "tool_start",
                    "tool_name": function_name,
                    "timestamp": int(time.time() * 1000)
                }) + "\n"
                
                # 执行工具
                tool_result = await AgentService.execute_tool(function_name, arguments, db, user)
                
                # 供前端展示的格式化输出
                formatted_result = await AgentService._format_tool_result_for_display(function_name, tool_result)
                if formatted_result:
                    if function_name == "get_stock_price_history":
                        formatted_results.append(formatted_result[:100])
                    else:
                        formatted_results.append(formatted_result)
                
                # 发送工具执行结果
                yield json.dumps({
                    "type": "tool_result",
                    "tool_name": function_name,
                    "formatted_result": formatted_result,
                    "timestamp": int(time.time() * 1000)
                }) + "\n"
                
                # 把工具原始结果以tool消息形式追加，供LLM继续推理
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "name": function_name,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })
                
    except Exception as e:
        # 发送错误信号
        yield json.dumps({
            "type": "error",
            "error": str(e),
            "timestamp": int(time.time() * 1000)
        }) + "\n"

@router.get("/tools", response_model=Dict[str, Any])
async def get_agent_tools(
    current_user: User = Depends(get_current_user)
):
    """获取智能体可用工具列表"""
    try:
        # 创建agent服务实例
        agent_service = AgentService()
        
        # 获取静态工具列表
        static_tools = AgentService.get_available_tools()
        
        # 获取动态工具列表（包括搜索工具）
        dynamic_tools = await agent_service.get_agent_tools()
        
        # 合并工具列表
        all_tools = [tool.model_dump() for tool in static_tools]
        for tool in dynamic_tools:
            all_tools.append(tool)
            
        return api_response(data={
            "tools": all_tools
        })
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        )

@router.get("/sessions", response_model=Dict[str, Any])
async def get_agent_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的智能体会话列表"""
    try:
        from app.models.conversation import Conversation
        from sqlalchemy import func, desc
        
        # 查询用户的所有会话ID，并按最后一条消息的时间分组
        query = db.query(
            Conversation.session_id,
            func.max(Conversation.created_at).label("last_updated"),
            func.count(Conversation.id).label("message_count")
        ).filter(
            Conversation.user_id == current_user.id
        ).group_by(
            Conversation.session_id
        ).order_by(
            desc("last_updated")
        ).all()
        
        # 获取每个会话的第一条消息作为标题
        sessions = []
        for session_id, last_updated, message_count in query:
            # 获取该会话的第一条用户消息
            first_message = db.query(Conversation).filter(
                Conversation.session_id == session_id,
                Conversation.user_id == current_user.id,
                Conversation.user_message != None
            ).order_by(Conversation.created_at).first()
            
            title = first_message.user_message if first_message else "新会话"
            if len(title) > 30:
                title = title[:30] + "..."
                
            sessions.append({
                "id": session_id,
                "title": title,
                "last_updated": last_updated.isoformat() if last_updated else None,
                "message_count": message_count
            })
            
        return api_response(data={
            "sessions": sessions
        })
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        )

@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_agent_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定会话的历史消息"""
    try:
        from app.models.conversation import Conversation
        
        # 验证会话存在且属于当前用户
        count = db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id
        ).count()
        
        if count == 0:
            return api_response(
                success=False,
                error="未找到指定会话或无权访问"
            )
        
        # 获取会话历史消息
        conversations = db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id
        ).order_by(Conversation.created_at).all()
        
        messages = []
        for conv in conversations:
            if conv.user_message:
                messages.append({
                    "id": f"user_{conv.id}",
                    "role": "user",
                    "content": conv.user_message,
                    "timestamp": conv.created_at.isoformat() if conv.created_at else None
                })
            if conv.assistant_response:
                messages.append({
                    "id": f"assistant_{conv.id}",
                    "role": "assistant",
                    "content": conv.assistant_response,
                    "timestamp": conv.created_at.isoformat() if conv.created_at else None
                })
        
        return api_response(data={
            "session_id": session_id,
            "messages": messages
        })
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        )

@router.delete("/sessions/{session_id}", response_model=Dict[str, Any])
async def delete_agent_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除指定会话"""
    try:
        from app.models.conversation import Conversation
        
        # 验证会话存在且属于当前用户
        count = db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id
        ).count()
        
        if count == 0:
            return api_response(
                success=False,
                error="未找到指定会话或无权访问"
            )
        
        # 删除会话
        deleted_count = db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id
        ).delete()
        
        db.commit()
        
        return api_response(data={
            "session_id": session_id,
            "deleted_count": deleted_count,
            "message": "会话已成功删除"
        })
    except Exception as e:
        db.rollback()
        return api_response(
            success=False,
            error=str(e)
        )

@router.post("/agent-tool", response_model=Dict[str, Any])
async def execute_agent_tool(
    request: AgentToolRequest,
    current_user: User = Depends(get_current_user),
    _: None = Depends(check_usage_limit)
):
    """单独执行智能体工具调用"""
    try:
        # 创建agent服务实例
        agent_service = AgentService()
        
        # 处理工具调用
        responses = await agent_service.process_agent_tools(request.tool_calls)
        
        return api_response(data={
            "responses": responses
        })
    except HTTPException as he:
        return api_response(
            success=False,
            error=he.detail
        )
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        ) 