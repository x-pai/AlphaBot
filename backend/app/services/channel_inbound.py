from app.channels.base import ChannelMessage
from app.channels.roles import parse_role_and_content
from app.services.channel_service import resolve_user, bind_message, target_for, add_target, ensure_available, bot_id

async def process_inbound(db, channel, sender, target, kind, text):
    ensure_available(channel)
    result = bind_message(db, channel, sender, target, kind, text)
    if result is not None:
        return result
    user = resolve_user(db, channel, sender)
    if not user:
        return "请先登录 AlphaBot，在系统管理 → 消息渠道 → 个人渠道管理生成绑定码，私聊发送：绑定 <绑定码>。"
    destination = target_for(db, user.id, channel, kind, target)
    role, content = parse_role_and_content(text)
    from app.services.agent_service import AgentService
    message = ChannelMessage(channel=channel,
        session_id=f"{channel}:{bot_id(channel)}:{target}:{sender}:{user.id}",
        user_id=user.id, content=content,
        metadata={"forced_role": role, "notify_channel": {"type": channel, "target_id": destination.id} if destination else None})
    reply = await AgentService.process_channel_message(message=message, db=db, user=user, enable_web_search=False)
    return reply.content or ""
