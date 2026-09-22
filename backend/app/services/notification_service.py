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
        logger.error("发送 Telegram 消息失败: %s", type(e).__name__)
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
            if token_resp.is_error:
                logger.error(
                    "获取飞书 tenant_access_token HTTP 失败: status=%s body=%s",
                    token_resp.status_code,
                    token_resp.text[:1000],
                )
                return False
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
            if send_resp.is_error:
                logger.error(
                    "发送飞书消息 HTTP 失败: status=%s body=%s chat_id=%s",
                    send_resp.status_code,
                    send_resp.text[:1000],
                    chat_id,
                )
                return False
            send_data = send_resp.json()
            if send_data.get("code") not in (0, None):
                logger.error("发送飞书消息失败: %s", send_data)
                return False
            logger.info("发送飞书消息成功: chat_id=%s", chat_id)
            return True
    except Exception as e:  # noqa: BLE001
        logger.error("发送飞书预警消息失败: %s", e)
        return False


def _build_webhook_payload(webhook_url: str, text: str) -> Dict[str, Any]:
    _ = webhook_url
    return {
        "msgtype": "text",
        "text": {
            "content": text,
        },
    }


def _parse_response_body(resp: httpx.Response) -> Any:
    content_type = (resp.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            return resp.json()
        except Exception:  # noqa: BLE001
            return resp.text[:2000]
    return resp.text[:2000]


async def _send_webhook_message(webhook_url: str, text: str) -> Dict[str, Any]:
    if not webhook_url:
        logger.warning("发送 Webhook 消息跳过: webhook_url 为空。")
        return {"success": False, "error": "webhook_url 为空"}
    payload = _build_webhook_payload(webhook_url, text)
    try:
        from app.services.webhook_security import validate_webhook_url
        from urllib.parse import urlunsplit
        parsed, address = await validate_webhook_url(webhook_url)
        host = f"[{address}]" if ":" in address else address
        netloc = f"{host}:{parsed.port}" if parsed.port else host
        pinned_url = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))
        async with httpx.AsyncClient(timeout=10.0, trust_env=False, follow_redirects=False) as client:
            resp = await client.post(pinned_url, json=payload, headers={"Host": parsed.netloc}, extensions={"sni_hostname": parsed.hostname})
            response_body = _parse_response_body(resp)
            success = 200 <= resp.status_code < 300
            if isinstance(response_body, dict):
                if "errcode" in response_body:
                    success = success and response_body.get("errcode") in (0, "0")
                elif "code" in response_body:
                    success = success and response_body.get("code") in (0, "0", None)
            return {
                "success": success,
                "status_code": resp.status_code,
                "response_body": response_body,
                "request_body": payload,
            }
    except Exception as e:  # noqa: BLE001
        logger.error("发送 Webhook 通知失败: %s", type(e).__name__)
        return {
            "success": False,
            "error": "Webhook 发送失败，请检查公网 HTTPS 地址及服务状态",
        }


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

        from app.db.session import SessionLocal
        from app.services.channel_service import send_configured
        db = SessionLocal()
        try:
            await send_configured(db, rule.user_id, notify_channel, trigger.message or f"{rule.symbol} 预警触发。")
        finally: db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("notify_alert 执行失败: %s", e)


async def send_channel_message(channel: str, chat_id: Any, text: str) -> Dict[str, Any]:
    """
    显式的发送渠道消息能力，供 Skill 调用。

    默认支持 qq / telegram / feishu / webhook，且由业务层控制调用场景。
    """
    from app.services.channel_service import ensure_available
    ch = (channel or "").lower()
    try: ensure_available(ch)
    except ValueError as exc: return {"success": False, "error": str(exc), "channel": ch}
    if ch == "qq":
        from app.services.qq_service import send_qq_message
        return await send_qq_message(chat_id, text)
    if not text:
        return {"success": False, "error": "text 不能为空"}

    if ch == "telegram":
        success = await _send_telegram_message(chat_id, text)
        return {"success": success, "channel": "telegram", "chat_id": chat_id}

    if ch == "feishu":
        success = await _send_feishu_message(str(chat_id), text)
        return {"success": success, "channel": "feishu", "chat_id": chat_id}

    if ch == "webhook":
        result = await _send_webhook_message(str(chat_id), text)
        return {
            "channel": "webhook",
            "webhook_url": chat_id,
            **result,
        }

    return {"success": False, "error": f"不支持的渠道类型: {channel}"}
