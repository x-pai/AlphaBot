"""Idempotent migration; never assign ownerless tasks or shared TG history."""
import json
from app.models.channel import ChannelMigration, ChannelBinding
from app.models.user import User
from app.models.task import ScheduledTask
from app.models.alert import AlertRule
from app.services.channel_service import bot_id, add_target, identity

def migrate_channels(db):
    marker = "personal_channels_v1"
    if db.get(ChannelMigration, marker):
        return
    if bot_id("feishu"):
        for user in db.query(User).filter(User.username.like("feishu_%")).all():
            sender = user.username[len("feishu_"):]
            if sender and not identity(db, "feishu", sender):
                db.add(ChannelBinding(user_id=user.id, channel="feishu", bot_id=bot_id("feishu"), external_user_id=sender))
        db.flush()
    def migrate(user_id, config):
        if not user_id or not db.get(User, user_id) or not isinstance(config, dict) or config.get("target_id"):
            return config
        channel = config.get("type")
        raw = config.get("webhook_url") or config.get("chat_id")
        if channel not in ("feishu", "telegram", "webhook") or not raw or not bot_id(channel):
            return config
        # Explicit stored notification ownership is preserved; no chat identities inferred.
        target = add_target(db, user_id, channel, "webhook" if channel == "webhook" else "legacy", raw, "原有推送目标（请核对备注）")
        return {"type": channel, "target_id": target.id}
    for task in db.query(ScheduledTask).filter_by(task_type="skill_publish_job").all():
        params = dict(task.params or {})
        if params.get("notify_channel"):
            params["notify_channel"] = migrate(params.get("user_id"), params["notify_channel"])
            task.params = params
    for rule in db.query(AlertRule).all():
        try:
            params = json.loads(rule.params_json or "{}")
        except (ValueError, TypeError):
            continue
        if params.get("notify_channel"):
            params["notify_channel"] = migrate(rule.user_id, params["notify_channel"])
            rule.params_json = json.dumps(params, ensure_ascii=False)
    db.add(ChannelMigration(key=marker))
    db.commit()
