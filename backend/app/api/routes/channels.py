import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.routes.user import get_current_user
from app.models.user import User
from app.models.channel import ChannelBinding, ChannelTarget
from app.services.channel_service import CHANNELS, bot_id, channel_status, create_code, owned_target, send_target
from app.utils.response import api_response

router = APIRouter()
class CodeRequest(BaseModel):
    channel: Literal["qq", "telegram", "feishu"]
    kind: Literal["private", "group"] = "private"
class TargetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(default="", max_length=2048)

@router.get("")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.qq_service import connection_status
    statuses = [channel_status(c) for c in CHANNELS]
    for status in statuses:
        status["connection"] = connection_status() if status["channel"] == "qq" else "按配置运行"
    bindings = db.query(ChannelBinding).filter_by(user_id=user.id, active=True).all()
    targets = db.query(ChannelTarget).filter_by(user_id=user.id).all()
    return api_response(data={"channels": statuses,
        "bindings": [{"id": b.id, "channel": b.channel, "external_user_id": b.external_user_id, "current_bot": b.bot_id == bot_id(b.channel)} for b in bindings],
        "targets": [{"id": t.id, "channel": t.channel, "kind": t.kind, "name": t.name,
                     "available": channel_status(t.channel)["available"] and t.bot_id == bot_id(t.channel),
                     "last_result": json.loads(t.last_result) if t.last_result else None} for t in targets]})

@router.post("/binding-codes")
def issue_code(body: CodeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return api_response(data=create_code(db, user.id, body.channel, body.kind))
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.delete("/bindings/{binding_id}")
def unbind(binding_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    binding = db.query(ChannelBinding).filter_by(id=binding_id, user_id=user.id).first()
    if not binding:
        raise HTTPException(404, "绑定不存在")
    # Revoke all targets on this identity's bot; tasks keep IDs and safely fail.
    db.query(ChannelTarget).filter_by(user_id=user.id, channel=binding.channel, bot_id=binding.bot_id).delete()
    from app.models.channel import ChannelBindingCode
    db.query(ChannelBindingCode).filter_by(user_id=user.id, channel=binding.channel, bot_id=binding.bot_id).delete()
    binding.active = False
    db.commit()
    return api_response(data={"unbound": True})

@router.post("/webhooks")
async def add_webhook(body: TargetRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.channel_service import add_target, ensure_available
    from app.services.webhook_security import validate_webhook_url
    try:
        ensure_available("webhook")
        await validate_webhook_url(body.url)
        target = add_target(db, user.id, "webhook", "webhook", body.url, body.name)
        db.commit()
        return api_response(data={"id": target.id})
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.patch("/targets/{target_id}")
async def edit_target(target_id: int, body: TargetRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        target = owned_target(db, user.id, target_id)
        if body.url:
            if target.channel != "webhook":
                raise ValueError("仅 Webhook 可修改地址")
            from app.services.webhook_security import validate_webhook_url
            await validate_webhook_url(body.url)
            target.external_id = body.url
        target.name = body.name
        db.commit()
        return api_response(data={"id": target.id})
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.delete("/targets/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target = db.query(ChannelTarget).filter_by(id=target_id, user_id=user.id).first()
    if not target:
        raise HTTPException(404, "目标不存在")
    db.delete(target)
    db.commit()
    return api_response(data={"deleted": True})

@router.post("/targets/{target_id}/test")
async def test_target(target_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = await send_target(db, user.id, target_id, "AlphaBot 渠道测试：连接成功。")
    return api_response(data=result)
