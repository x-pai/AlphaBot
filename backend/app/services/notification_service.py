from typing import Any, Dict, Optional

import httpx
import json

from app.core.config import settings
from app.middleware.logging import logger
from app.models.alert import AlertRule, AlertTrigger


async def _send_telegram_message(chat_id: Any, text: str) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("发送 Telegram 消息跳过: TELEGRAM_BOT_TOKEN 未配置。")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                },
            )
            resp.raise_for_status()
            return True
    except Exception as e:  # noqa: BLE001
        logger.error("发送 Telegram 预警消息失败: %s", e)
        return False


async def _send_feishu_message(chat_id: str, text: str) -> bool:
    if not (settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET):
        logger.warning("发送飞书消息跳过: FEISHU_APP_ID 或 FEISHU_APP_SECRET 未配置。")
        return False
    base = settings.FEISHU_API_BASE.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 获取 tenant_access_token
            token_resp = await client.post(
                f"{base}/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": settings.FEISHU_APP_ID,
                    "app_secret": settings.FEISHU_APP_SECRET,
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            tenant_token = token_data.get("tenant_access_token")
            if not tenant_token:
                logger.error("获取飞书 tenant_access_token 失败: %s", token_data)
                return False

            # 发送消息到群
            send_resp = await client.post(
                f"{base}/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers={"Authorization": f"Bearer {tenant_token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                },
            )
            send_resp.raise_for_status()
            send_data = send_resp.json()
            if send_data.get("code") not in (0, None):
                logger.error("发送飞书消息失败: %s", send_data)
                return False
            logger.info("发送飞书消息成功: chat_id=%s", chat_id)
            return True
    except Exception as e:  # noqa: BLE001
        logger.error("发送飞书预警消息失败: %s", e)
        return False


async def notify_alert(rule: AlertRule, trigger: AlertTrigger) -> None:
    """
    根据 AlertRule 中记录的 notify_channel 信息，主动下发预警通知。
    """
    try:
        params: Dict[str, Any] = {}
        if rule.params_json:
            import json

            try:
                params = json.loads(rule.params_json)
            except Exception:  # noqa: BLE001
                params = {}

        notify_channel: Optional[Dict[str, Any]] = params.get("notify_channel")
        if not isinstance(notify_channel, dict):
            return

        ch_type = (notify_channel.get("type") or "").lower()
        chat_id = notify_channel.get("chat_id")
        if not chat_id:
            return

        text = trigger.message or f"{rule.symbol} 预警触发。"

        if ch_type == "telegram":
            await _send_telegram_message(chat_id, text)
        elif ch_type == "feishu":
            await _send_feishu_message(chat_id, text)
    except Exception as e:  # noqa: BLE001
        logger.error("notify_alert 执行失败: %s", e)


async def send_channel_message(channel: str, chat_id: Any, text: str) -> Dict[str, Any]:
    """
    显式的发送渠道消息能力，供 Skill 调用。

    默认仅支持 telegram / feishu，且由业务层控制调用场景。
    """
    ch = (channel or "").lower()
    if not text:
        return {"success": False, "error": "text 不能为空"}

    if ch == "telegram":
        success = await _send_telegram_message(chat_id, text)
        return {"success": success, "channel": "telegram", "chat_id": chat_id}

    if ch == "feishu":
        success = await _send_feishu_message(str(chat_id), text)
        return {"success": success, "channel": "feishu", "chat_id": chat_id}

    return {"success": False, "error": f"不支持的渠道类型: {channel}"}
