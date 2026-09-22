import secrets
from typing import Any, Dict
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.services.channel_service import channel_status, claim_event
from app.services.channel_inbound import process_inbound
from app.services.notification_service import send_channel_message

router = APIRouter()
async def handle_telegram_update(update: Dict[str, Any], db: Session) -> None:
    if not channel_status("telegram")["available"]:
        return
    message = update.get("message") or {}
    sender = message.get("from") or {}
    chat = message.get("chat") or {}
    text = message.get("text") or ""
    if not text or not sender.get("id") or sender.get("is_bot") or chat.get("id") is None:
        return
    if not claim_event(db, "telegram", str(update.get("update_id", ""))):
        return
    reply = await process_inbound(db, "telegram", str(sender["id"]), str(chat["id"]), "private" if chat.get("type") == "private" else "group", text)
    if reply:
        await send_channel_message("telegram", chat["id"], reply)

@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    # Polling is the default. Public webhook requires Telegram secret_token.
    if not channel_status("telegram")["available"]:
        return {"ok": True}
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not secret or not secrets.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), secret):
        raise HTTPException(403, "invalid webhook secret")
    await handle_telegram_update(await request.json(), db)
    return {"ok": True}
