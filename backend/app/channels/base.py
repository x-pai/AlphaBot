from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ChannelType(str, Enum):
    """消息渠道类型。预留多种 IM / MCP 入口。"""

    WEB_CHAT = "web_chat"
    MCP = "mcp"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    EMAIL = "email"


class ChannelMessage(BaseModel):
    """统一的入口消息结构，由各 Channel 适配器生成。"""

    channel: str  # 对应 ChannelType 的值，允许未来扩展
    session_id: str
    user_id: Optional[int] = None
    content: str
    metadata: Dict[str, Any] = {}


class ChannelReply(BaseModel):
    """统一的出口消息结构，由 Gateway / AgentService 返回。"""

    channel: str
    session_id: str
    user_id: Optional[int] = None
    content: str
    tool_outputs: Optional[List[str]] = None
    metadata: Dict[str, Any] = {}

