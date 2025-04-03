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
        # TODO: 实现从数据库获取会话列表
        sessions = []
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
        # TODO: 实现从数据库获取会话历史
        messages = []
        return api_response(data={
            "session_id": session_id,
            "messages": messages
        })
    except Exception as e:
        return api_response(
            success=False,
            error=str(e)
        ) 