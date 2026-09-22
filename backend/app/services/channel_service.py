from __future__ import annotations
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from collections import defaultdict, deque
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.models.channel import ChannelBinding, ChannelBindingCode, ChannelTarget, ChannelEvent
from app.models.user import User

CHANNELS = ("qq", "telegram", "feishu", "webhook")
_attempts = defaultdict(deque)

def bot_id(channel):
    return {"qq": settings.QQ_BOT_APP_ID, "telegram": settings.TELEGRAM_BOT_TOKEN.split(":")[0],
            "feishu": settings.FEISHU_APP_ID, "webhook": "system"}.get(channel, "")

def channel_status(channel):
    enabled = bool(getattr(settings, {"qq": "QQ_BOT_ENABLED"}.get(channel, channel.upper() + "_ENABLED"), False))
    configured = {"qq": bool(settings.QQ_BOT_APP_ID and settings.QQ_BOT_APP_SECRET.get_secret_value()),
                  "telegram": bool(settings.TELEGRAM_BOT_TOKEN),
                  "feishu": bool(settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET), "webhook": True}.get(channel, False)
    return {"channel": channel, "enabled": enabled, "configured": configured, "available": enabled and configured}

def ensure_available(channel):
    status = channel_status(channel)
    if not status["enabled"]:
        raise ValueError("渠道已关闭，未推送")
    if not status["configured"]:
        raise ValueError("渠道凭证未配置")

def identity(db, channel, sender):
    return db.query(ChannelBinding).filter_by(channel=channel, bot_id=bot_id(channel), external_user_id=str(sender)).first()

def resolve_user(db, channel, sender):
    binding = identity(db, channel, sender)
    if binding:
        return db.get(User, binding.user_id) if binding.active else None
    return None

def target_for(db, user_id, channel, kind, external_id):
    return db.query(ChannelTarget).filter_by(user_id=user_id, channel=channel, bot_id=bot_id(channel), kind=kind, external_id=str(external_id)).first()

def add_target(db, user_id, channel, kind, external_id, name=None):
    target = target_for(db, user_id, channel, kind, external_id)
    if not target:
        target = ChannelTarget(user_id=user_id, channel=channel, bot_id=bot_id(channel), kind=kind, external_id=str(external_id), name=name or ("个人私聊" if kind == "private" else "群接收目标"))
        db.add(target)
        db.flush()
    return target

def create_code(db, user_id, channel, kind):
    if channel not in CHANNELS[:-1] or kind not in ("private", "group"):
        raise ValueError("绑定类型无效")
    ensure_available(channel)
    now = datetime.utcnow()
    recent = db.query(ChannelBindingCode).filter(ChannelBindingCode.user_id == user_id, ChannelBindingCode.expires_at > now).count()
    if recent >= 10:
        raise ValueError("绑定码生成过于频繁，请稍后重试")
    code = secrets.token_hex(6).upper()
    db.add(ChannelBindingCode(digest=hashlib.sha256(code.encode()).hexdigest(), user_id=user_id, channel=channel, bot_id=bot_id(channel), kind=kind, expires_at=now + timedelta(minutes=10)))
    db.commit()
    return {"code": code, "expires_at": (now + timedelta(minutes=10)).isoformat() + "Z"}

def bind_message(db, channel, sender, target_id, kind, text):
    if not text.strip().startswith(("绑定 ", "/bind ")):
        return None
    if len(_attempts) > 10000:
        _attempts.clear()
    key = (channel, str(sender))
    now = datetime.utcnow()
    attempts = _attempts[key]
    while attempts and (now - attempts[0]).total_seconds() > 600:
        attempts.popleft()
    if len(attempts) >= 5:
        return "尝试次数过多，请 10 分钟后重试。"
    attempts.append(now)
    code = text.strip().split(maxsplit=1)[1].strip().upper()
    record = db.query(ChannelBindingCode).filter_by(digest=hashlib.sha256(code.encode()).hexdigest(), channel=channel, bot_id=bot_id(channel), kind=kind, consumed_at=None).first()
    if not record or record.expires_at <= now:
        return "绑定码无效或已过期，请在消息渠道的个人渠道管理中重新生成。"
    user = resolve_user(db, channel, sender)
    if user and user.id != record.user_id:
        return "该渠道身份已关联其他账户，不能覆盖；原账户数据会保留，请联系管理员处理账户关联。"
    if kind == "group" and (not user or user.id != record.user_id):
        return "请先私聊机器人绑定自己的账号，再由同一账号绑定群。"
    try:
        claimed = db.query(ChannelBindingCode).filter_by(id=record.id, consumed_at=None).filter(ChannelBindingCode.expires_at > now).update({"consumed_at": now}, synchronize_session=False)
        if not claimed:
            db.rollback()
            return "绑定码已使用。"
        if not user:
            previous = identity(db, channel, sender)
            if previous:
                changed = db.query(ChannelBinding).filter_by(id=previous.id, active=False).update({"user_id": record.user_id, "active": True}, synchronize_session=False)
                if not changed:
                    db.rollback()
                    return "绑定冲突，请刷新网页查看当前绑定。"
            else:
                db.add(ChannelBinding(user_id=record.user_id, channel=channel, bot_id=bot_id(channel), external_user_id=str(sender)))
        add_target(db, record.user_id, channel, kind, target_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        return "绑定冲突，请刷新网页查看当前绑定。"
    return "绑定成功，请返回 AlphaBot 消息渠道的个人渠道管理查看接收目标。"

def owned_target(db, user_id, target_id):
    target = db.query(ChannelTarget).filter_by(id=target_id, user_id=user_id).first()
    if not target:
        raise ValueError("接收目标不存在或无权使用")
    if target.bot_id != bot_id(target.channel):
        raise ValueError("机器人已更换，请重新绑定目标")
    return target

async def send_target(db, user_id, target_id, text):
    from app.services.notification_service import send_channel_message
    try:
        target = owned_target(db, user_id, target_id)
        address = f"{target.kind}:{target.external_id}" if target.channel == "qq" else target.external_id
        result = await send_channel_message(target.channel, address, text)
        # Don't persist webhook secrets or request payloads in status.
        safe = {k: result[k] for k in ("success", "error", "code", "message_id", "http_status", "provider_message", "trace_id", "stage") if k in result}
        if not safe.get("success") and not safe.get("error"):
            safe["error"] = "平台拒绝发送或网络请求失败，请检查机器人配置和接收权限"
        target.last_result = json.dumps({**safe, "at": datetime.utcnow().isoformat() + "Z"}, ensure_ascii=False)
        db.commit()
        return safe
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

def claim_event(db, channel, event_id):
    if not event_id:
        return False
    now = datetime.utcnow()
    db.query(ChannelEvent).filter(ChannelEvent.received_at < now - timedelta(days=2)).delete()
    db.add(ChannelEvent(key=f"{channel}:{bot_id(channel)}:{event_id}", received_at=now))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def validate_notification(db, user_id, config):
    if not config:
        return None
    if not isinstance(config, dict):
        raise ValueError("通知配置必须是对象")
    if config.get("target_id"):
        target = owned_target(db, user_id, int(config["target_id"]))
    else:
        channel = config.get("type")
        raw = config.get("webhook_url") or config.get("chat_id")
        target = db.query(ChannelTarget).filter_by(user_id=user_id, channel=channel, bot_id=bot_id(channel), external_id=str(raw)).first()
        if not target:
            raise ValueError("旧推送目标待确认，请在个人渠道管理绑定后重新选择")
    return {"type": target.channel, "target_id": target.id}

async def send_configured(db, user_id, config, text):
    try:
        normalized = validate_notification(db, user_id, config)
        if not normalized:
            return {"success": False, "error": "未配置接收目标"}
        return await send_target(db, user_id, normalized["target_id"], text)
    except (ValueError, TypeError):
        return {"success": False, "error": "接收目标无效、已解绑或旧配置待确认"}
