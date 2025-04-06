from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import uuid

from app.db.session import get_db
from app.services.agent_service import AgentService
from app.api.routes.user import get_current_user
from app.models.user import User
from app.utils.response import api_response

router = APIRouter()

class AgentMessageRequest(BaseModel):
    """智能体消息请求"""
    content: str
    session_id: Optional[str] = None

class AgentMessageResponse(BaseModel):
    """智能体消息响应"""
    content: str
    session_id: str
    error: Optional[str] = None

@router.post("/chat", response_model=Dict[str, Any])
async def agent_chat(
    request: AgentMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """与智能体对话"""
    try:
        # 如果没有提供会话ID，生成一个新的
        session_id = request.session_id or str(uuid.uuid4())
        
        # 处理消息
        response = await AgentService.process_message(
            user_message=request.content,
            session_id=session_id,
            db=db,
            user=current_user
        )
        
        return api_response(data=response)
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        )

@router.get("/tools", response_model=Dict[str, Any])
async def get_agent_tools(
    current_user: User = Depends(get_current_user)
):
    """获取智能体可用工具列表"""
    try:
        tools = AgentService.get_available_tools()
        return api_response(data={
            "tools": [tool.model_dump() for tool in tools]
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