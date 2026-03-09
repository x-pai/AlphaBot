from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.channels.base import ChannelMessage
from app.channels.roles import parse_role_and_content
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.agent_service import AgentService

router = APIRouter()


def _get_default_user(db: Session) -> User:
    """
    Telegram 入口当前采用固定用户占位，后续可改为 tg_user_id → user 映射。
    """
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise RuntimeError("默认用户不存在，请创建 id=1 的用户或实现映射逻辑。")
    return user


async def handle_telegram_update(update: Dict[str, Any], db: Session) -> None:
    """
    统一处理 Telegram update，既供 Webhook 使用，也供长轮询使用。
    """
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    user_text = message.get("text") or ""
    if not user_text or chat_id is None:
        return

    forced_role, content = parse_role_and_content(user_text)

    user = _get_default_user(db)
    session_id = f"telegram:{chat_id}"

    channel_msg = ChannelMessage(
        channel="telegram",
        session_id=session_id,
        user_id=user.id,
        content=content,
        metadata={
            "raw_text": user_text,
            "tg_chat_id": chat_id,
            "tg_user_id": from_user.get("id"),
            "forced_role": forced_role,
        },
    )

    reply = await AgentService.process_channel_message(
        message=channel_msg,
        db=db,
        user=user,
        enable_web_search=False,
        model=None,
    )

    # 调用 Telegram sendMessage API 把回复发回群/私聊（仅在配置了 Bot Token 时启用）
    if settings.TELEGRAM_BOT_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": reply.content or "",
                    },
                )
        except Exception:
            # 出错时不影响主流程
            pass


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Telegram Bot Webhook 入口（可选）。

    若后端不暴露公网，可不配置 Webhook，而使用长轮询方式获取更新。
    """
    update = await request.json()
    await handle_telegram_update(update, db)
    return {"ok": True}


