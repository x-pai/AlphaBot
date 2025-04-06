from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.db.session import Base

class Conversation(Base):
    """会话历史模型"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_message = Column(Text, nullable=True)
    assistant_response = Column(Text, nullable=True)
    tool_calls = Column(Text, nullable=True)  # JSON字符串存储工具调用
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_message": self.user_message,
            "assistant_response": self.assistant_response,
            "created_at": self.created_at.isoformat() if self.created_at else None
        } 