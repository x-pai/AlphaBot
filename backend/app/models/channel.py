"""System bots, personal identities and delivery destinations."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text, Boolean
from app.db.session import Base

class ChannelBinding(Base):
    __tablename__ = "channel_bindings"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    bot_id = Column(String(128), nullable=False)
    external_user_id = Column(String(256), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("channel", "bot_id", "external_user_id"),)

class ChannelTarget(Base):
    __tablename__ = "channel_targets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    bot_id = Column(String(128), nullable=False)
    kind = Column(String(20), nullable=False)
    external_id = Column(Text, nullable=False)
    name = Column(String(100), nullable=False)
    last_result = Column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "channel", "bot_id", "kind", "external_id"), {"sqlite_autoincrement": True})

class ChannelBindingCode(Base):
    __tablename__ = "channel_binding_codes"
    id = Column(Integer, primary_key=True)
    digest = Column(String(64), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    bot_id = Column(String(128), nullable=False)
    kind = Column(String(20), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)

class ChannelEvent(Base):
    __tablename__ = "channel_events"
    key = Column(String(512), primary_key=True)
    received_at = Column(DateTime, nullable=False)

class ChannelMigration(Base):
    __tablename__ = "channel_migrations"
    key = Column(String(100), primary_key=True)
