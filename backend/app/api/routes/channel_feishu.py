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
    飞书入口当前采用固定用户占位，后续可改为 open_id → user 映射。
    """
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise RuntimeError("默认用户不存在，请创建 id=1 的用户或实现映射逻辑。")
    return user


@router.post("/webhook")
async def feishu_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    飞书事件回调入口（骨架）。

    注意：
    - 实际部署时需要增加签名校验 / token 校验；
    - 发送回复需要调用飞书开放平台的发送消息接口，这里只返回内容。
    """
    body = await request.json()

    # 1) URL 校验
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    event = body.get("event") or {}
    msg_type = event.get("msg_type")
    if msg_type != "text":
        # 暂时只处理文本
        return {"code": 0, "msg": "ignored"}

    text = event.get("text", "") or ""
    chat_id = event.get("chat_id") or event.get("open_chat_id") or ""
    sender = event.get("sender", {}) or {}
    sender_open_id = (
        sender.get("sender_id", {}) or {}
    ).get("open_id") or sender.get("open_id")

    forced_role, content = parse_role_and_content(text)

    user = _get_default_user(db)
    session_id = f"feishu:{chat_id}"

    channel_msg = ChannelMessage(
        channel="feishu",
        session_id=session_id,
        user_id=user.id,
        content=content,
        metadata={
            "raw_text": text,
            "feishu_chat_id": chat_id,
            "feishu_sender_id": sender_open_id,
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
    
    # 调用飞书开放平台发送文本消息（仅在配置了 App ID/Secret 时启用）
    if settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET and chat_id:
        try:
            base = settings.FEISHU_API_BASE.rstrip("/")
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1) 获取 tenant_access_token
                token_resp = await client.post(
                    f"{base}/open-apis/auth/v3/tenant_access_token/internal",
                    json={
                        "app_id": settings.FEISHU_APP_ID,
                        "app_secret": settings.FEISHU_APP_SECRET,
                    },
                )
                token_data = token_resp.json()
                tenant_token = token_data.get("tenant_access_token")

                if tenant_token:
                    # 2) 发送消息到群
                    await client.post(
                        f"{base}/open-apis/im/v1/messages?receive_id_type=chat_id",
                        headers={"Authorization": f"Bearer {tenant_token}"},
                        json={
                            "receive_id": chat_id,
                            "msg_type": "text",
                            "content": {"text": reply.content or ""},
                        },
                    )
        except Exception:
            # 出错时不影响主流程，只记录日志
            # 这里不直接引用 logger，避免循环依赖；生产环境可接入统一日志。
            pass

    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "session_id": reply.session_id,
            "content": reply.content,
        },
    }

