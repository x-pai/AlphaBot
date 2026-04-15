from typing import Any, Dict
import base64
import hashlib
import json
import time

from fastapi import APIRouter, Depends, Request
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy.orm import Session

from app.channels.base import ChannelMessage
from app.channels.roles import parse_role_and_content
from app.core.config import settings
from app.db.session import get_db
from app.middleware.logging import logger
from app.models.user import User
from app.services.agent_service import AgentService
from app.services.notification_service import send_channel_message
from app.services.user_service import UserService

router = APIRouter()


def _verify_feishu_signature(request: Request, raw_body: bytes) -> bool:
    encrypt_key = (settings.FEISHU_ENCRYPT_KEY or "").strip()
    if not encrypt_key:
        # 未配置加密 Key 时，不启用头部签名校验
        return True

    timestamp = request.headers.get("X-Lark-Request-Timestamp", "").strip()
    nonce = request.headers.get("X-Lark-Request-Nonce", "").strip()
    signature = request.headers.get("X-Lark-Signature", "").strip().lower()
    if not timestamp or not nonce or not signature:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    # 飞书要求时间戳有效，避免重放。这里使用 1 小时窗口。
    if abs(int(time.time()) - ts) > 3600:
        return False

    digest = hashlib.sha256(
        timestamp.encode("utf-8") + nonce.encode("utf-8") + encrypt_key.encode("utf-8") + raw_body
    ).hexdigest().lower()
    return digest == signature


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("empty plaintext")

    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("invalid padding")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("invalid padding")
    return data[:-pad_len]


def _parse_feishu_body(raw_body: bytes) -> Dict[str, Any]:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid json") from exc

    encrypt_key = (settings.FEISHU_ENCRYPT_KEY or "").strip()
    encrypted = body.get("encrypt")
    if not encrypt_key or not encrypted:
        return body

    try:
        cipher_bytes = base64.b64decode(encrypted)
    except Exception as exc:
        raise ValueError("invalid encrypted payload") from exc

    if len(cipher_bytes) < 16:
        raise ValueError("invalid encrypted payload")

    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    iv = cipher_bytes[:16]
    ciphertext = cipher_bytes[16:]
    if not ciphertext or len(ciphertext) % 16 != 0:
        raise ValueError("invalid encrypted payload")

    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    try:
        decrypted = _pkcs7_unpad(plaintext).decode("utf-8")
        return json.loads(decrypted)
    except Exception as exc:
        raise ValueError("invalid decrypted event") from exc


def _extract_text_content(event: Dict[str, Any]) -> str:
    text = event.get("text", "") or ""
    if text:
        return text

    message = event.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        import json

        try:
            parsed = json.loads(content)
            return parsed.get("text", "") or ""
        except Exception:
            return content
    if isinstance(content, dict):
        return content.get("text", "") or ""
    return ""


def _extract_chat_id(event: Dict[str, Any]) -> str:
    message = event.get("message") or {}
    return (
        event.get("chat_id")
        or event.get("open_chat_id")
        or message.get("chat_id")
        or ""
    )


def _extract_sender_open_id(event: Dict[str, Any]) -> str:
    sender = event.get("sender") or {}
    sender_id = sender.get("sender_id") or {}
    return (
        sender_id.get("open_id")
        or sender.get("open_id")
        or ""
    )


def _get_or_create_feishu_user(db: Session, open_id: str) -> User:
    if not open_id:
        raise RuntimeError("缺少飞书 open_id，无法建立用户映射。")

    username = f"feishu_{open_id}"
    email = f"{username}@channel.local"

    user = db.query(User).filter(User.username == username).first()
    if user:
        return user

    user = User(
        username=username,
        email=email,
        hashed_password=UserService.get_password_hash(open_id),
        points=120,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/webhook")
async def feishu_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    飞书事件回调入口（骨架）。

    注意：
    - 当前实现支持 URL 校验、token 校验、文本消息处理；
    - 发送回复复用统一通知服务。
    """
    raw_body = await request.body()
    if not _verify_feishu_signature(request, raw_body):
        logger.warning("飞书 webhook 签名校验失败。")
        return {"code": 403, "msg": "invalid signature"}

    try:
        body = _parse_feishu_body(raw_body)
    except ValueError as exc:
        logger.warning("飞书 webhook 请求体解析失败: %s", exc)
        return {"code": 400, "msg": str(exc)}

    verification_token = (settings.FEISHU_VERIFICATION_TOKEN or "").strip()
    header = body.get("header") or {}
    request_token = body.get("token") or header.get("token")
    if verification_token and request_token != verification_token:
        logger.warning(
            "飞书 webhook token 校验失败: has_request_token=%s schema=%s",
            bool(request_token),
            body.get("schema"),
        )
        return {"code": 403, "msg": "invalid token"}

    # 1) URL 校验
    if body.get("type") == "url_verification":
        logger.info("飞书 webhook URL 校验通过。")
        return {"challenge": body.get("challenge")}

    event = body.get("event") or {}
    message = event.get("message") or {}
    msg_type = event.get("msg_type") or message.get("message_type")
    if msg_type != "text":
        # 暂时只处理文本
        logger.info("飞书 webhook 忽略非文本消息: msg_type=%s", msg_type)
        return {"code": 0, "msg": "ignored"}

    text = _extract_text_content(event)
    chat_id = _extract_chat_id(event)
    sender_open_id = _extract_sender_open_id(event)
    if not text or not chat_id or not sender_open_id:
        logger.warning(
            "飞书 webhook 缺少必要字段: has_text=%s chat_id=%s sender_open_id=%s",
            bool(text),
            bool(chat_id),
            bool(sender_open_id),
        )
        return {"code": 0, "msg": "ignored"}

    forced_role, content = parse_role_and_content(text)

    user = _get_or_create_feishu_user(db, sender_open_id)
    session_id = f"feishu:{chat_id}:{sender_open_id}"
    logger.info(
        "飞书 webhook 收到文本消息: chat_id=%s sender_open_id=%s session_id=%s text=%s",
        chat_id,
        sender_open_id,
        session_id,
        text[:200],
    )

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

    logger.info(
        "飞书 webhook Agent 回复完成: session_id=%s has_content=%s content=%s",
        reply.session_id,
        bool(reply.content),
        (reply.content or "")[:200],
    )

    if settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET and chat_id and reply.content:
        send_result = await send_channel_message("feishu", chat_id, reply.content)
        logger.info("飞书 webhook 回发结果: %s", send_result)
    elif not reply.content:
        logger.warning("飞书 webhook 未回发: Agent 回复为空。")
    else:
        logger.warning("飞书 webhook 未回发: 飞书渠道配置不完整或 chat_id 缺失。")

    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "session_id": reply.session_id,
            "content": reply.content,
        },
    }
