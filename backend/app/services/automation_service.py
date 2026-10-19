from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Awaitable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.channels.base import ChannelMessage
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.services.agent_service import AgentService
from app.services.notification_service import send_channel_message
from app.services.trading_calendar_service import TradingCalendarService


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-").lower()
    return normalized or f"report-{uuid.uuid4().hex[:8]}"


def _render_template(value: str, now: datetime) -> str:
    return value.format(
        date=now.strftime("%Y-%m-%d"),
        date_compact=now.strftime("%Y%m%d"),
        datetime=now.strftime("%Y-%m-%d %H:%M:%S"),
        datetime_compact=now.strftime("%Y%m%d-%H%M%S"),
        brief="{brief}",
    )


class AutomationService:
    """自动化 Skill 任务与发布服务。"""

    DEFAULT_COLLECTION_SLUG = "daily-market-brief"

    @classmethod
    def published_dir(cls) -> str:
        from app.core.config import settings

        path = os.path.join(settings.BASE_DIR, "data", "published_reports")
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def write_published_report(
        cls,
        *,
        slug: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "slug": slug,
            "title": title,
            "content": content,
            "metadata": metadata or {},
            "published_at": datetime.now().isoformat(),
        }
        path = os.path.join(cls.published_dir(), f"{slug}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return payload

    @classmethod
    def load_published_report(cls, slug: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(cls.published_dir(), f"{slug}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def build_collection_slug(cls, value: Optional[str]) -> str:
        normalized = _slugify(str(value or "").strip()) if value else ""
        return normalized or cls.DEFAULT_COLLECTION_SLUG

    @classmethod
    def build_entry_slug(cls, template: str, now: datetime) -> str:
        normalized = (template or "").strip()
        if normalized:
            if "{" in normalized and "}" in normalized:
                return _slugify(_render_template(normalized, now))
            return _slugify(f"{normalized}-{now.strftime('%Y%m%d')}")
        return _slugify(f"review-{now.strftime('%Y%m%d')}")

    @classmethod
    def build_storage_slug(cls, collection_slug: str, entry_slug: str) -> str:
        return _slugify(f"{collection_slug}--{entry_slug}")

    @classmethod
    def build_public_report_path(cls, collection_slug: str, entry_slug: str) -> str:
        return f"/published/{collection_slug}/{entry_slug}"

    @classmethod
    def build_public_report_url(cls, collection_slug: str, entry_slug: str) -> str:
        path = cls.build_public_report_path(collection_slug, entry_slug)
        base_url = settings.APP_PUBLIC_BASE_URL.strip().rstrip("/")
        return f"{base_url}{path}" if base_url else path

    @classmethod
    def ensure_unique_entry_slug(cls, collection_slug: str, entry_slug: str, now: datetime) -> str:
        candidate = entry_slug
        path = os.path.join(cls.published_dir(), f"{cls.build_storage_slug(collection_slug, candidate)}.json")
        if not os.path.exists(path):
            return candidate
        return _slugify(f"{entry_slug}-{now.strftime('%H%M%S')}")

    @classmethod
    def load_collection_entry(cls, collection_slug: str, entry_slug: str) -> Optional[Dict[str, Any]]:
        return cls.load_published_report(cls.build_storage_slug(collection_slug, entry_slug))

    @classmethod
    def list_collection_entries(cls, collection_slug: str) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        if not os.path.exists(cls.published_dir()):
            return items
        cutoff = datetime.now() - timedelta(days=30)

        for filename in os.listdir(cls.published_dir()):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(cls.published_dir(), filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                continue

            metadata = payload.get("metadata") or {}
            if (metadata.get("collection_slug") or "") != collection_slug:
                continue
            published_at = payload.get("published_at")
            try:
                published_dt = datetime.fromisoformat(str(published_at))
            except Exception:
                continue
            if published_dt < cutoff:
                continue

            entry_slug = str(metadata.get("entry_slug") or "").strip()
            if not entry_slug:
                continue

            items.append(
                {
                    "entry_slug": entry_slug,
                    "title": payload.get("title"),
                    "published_at": published_at,
                    "url": cls.build_public_report_path(collection_slug, entry_slug),
                }
            )

        items.sort(key=lambda item: item.get("published_at") or "", reverse=True)
        return items

    @classmethod
    def build_report_prompt(cls, prompt_template: str, title_template: str, now: datetime) -> str:
        user_prompt = _render_template(prompt_template, now)
        title_rule = _render_template(title_template.strip() or "{date} · {brief}", now)
        return (
            f"{user_prompt}\n\n"
            "【报告标题与发布要求】\n"
            f"标题规则：{title_rule}\n"
            "最终报告的第一个非空行必须是 Markdown 一级标题，格式为 `# 最终标题`。\n"
            "严格按上述标题规则生成最终标题，保留规则中的固定文字、日期和分隔符。"
            "若规则含 {brief}，将其替换为根据本次报告提炼的核心结论短语，不超过24个汉字，"
            "不含日期、标点或泛化的报告名称；不得保留变量占位符。"
            "若规则不含 {brief}，直接使用规则中的完整标题。\n"
            "此规则优先于 Skill 或报告模板中的示例标题；不要另加日期或报告名称。"
            "标题使用纯文本，不加粗、不加链接，不要用代码围栏包裹报告。"
            "正文从二级标题开始，页面发布标题将直接使用报告的一级标题。"
        )

    @classmethod
    def extract_report_title(cls, content: str) -> str:
        first_line = next((line.strip() for line in str(content or "").splitlines() if line.strip()), "")
        match = re.fullmatch(r"#\s+(.+)", first_line)
        if not match:
            raise ValueError("报告缺少首行 Markdown 一级标题，无法发布；请按配置的标题规则生成报告")
        title = re.sub(r"\s+#+$", "", match.group(1)).strip()
        if not title.strip("# ") or re.search(r"\{(?:date|date_compact|datetime|datetime_compact|brief)\}", title):
            raise ValueError("报告标题为空或含未替换的变量，无法发布")
        return title

    @classmethod
    def build_publish_slug(cls, template: str, title: str, now: datetime) -> str:
        normalized = (template or "").strip()
        if normalized:
            if "{" in normalized and "}" in normalized:
                return _slugify(_render_template(normalized, now))
            return _slugify(f"{normalized}-{now.strftime('%Y%m%d')}")
        return _slugify(title)

    @classmethod
    def ensure_unique_slug(cls, slug: str, now: datetime) -> str:
        candidate = slug
        path = os.path.join(cls.published_dir(), f"{candidate}.json")
        if not os.path.exists(path):
            return candidate
        return _slugify(f"{slug}-{now.strftime('%H%M%S')}")

    @classmethod
    async def execute_skill_publish_job(
        cls,
        *,
        task_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, Optional[str], Optional[Dict[str, Any]]], Awaitable[None] | None]] = None,
    ) -> Dict[str, Any]:
        return await cls._execute_skill_publish_job(task_id=task_id, params=params, progress_callback=progress_callback)

    @classmethod
    async def _emit_progress(
        cls,
        progress_callback: Optional[Callable[[str, Optional[str], Optional[Dict[str, Any]]], Awaitable[None] | None]],
        stage: str,
        detail: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not progress_callback:
            return
        result = progress_callback(stage, detail, payload)
        if result is not None and hasattr(result, "__await__"):
            await result

    @classmethod
    async def _execute_skill_publish_job(
        cls,
        *,
        task_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, Optional[str], Optional[Dict[str, Any]]], Awaitable[None] | None]] = None,
    ) -> Dict[str, Any]:
        db: Session = SessionLocal()
        try:
            await cls._emit_progress(progress_callback, "initializing", "正在准备自动化任务配置。", {"task_id": task_id})
            user_id = params.get("user_id")
            if not user_id:
                raise ValueError("缺少 user_id，无法执行自动化任务")

            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                raise ValueError(f"用户不存在: {user_id}")

            skill_name = (params.get("skill_name") or "research").strip()
            if params.get("trading_days_only", skill_name == "ashare-daily-review"):
                timezone_name = str(params.get("timezone") or settings.APP_TIMEZONE)
                try:
                    now = datetime.now(ZoneInfo(timezone_name))
                except Exception:
                    timezone_name = settings.APP_TIMEZONE
                    now = datetime.now(ZoneInfo(timezone_name))

                trade_date = now.date()
                calendar = await TradingCalendarService.get_trade_calendar()
                if trade_date not in calendar:
                    latest_trading_day = await TradingCalendarService.latest_trading_day(trade_date)
                    detail = f"今日 {trade_date.isoformat()} 非 A 股交易日，已跳过自动复盘。"
                    if latest_trading_day:
                        detail += f" 最近交易日为 {latest_trading_day.isoformat()}。"
                    result = {
                        "task_id": task_id,
                        "status": "skipped",
                        "reason": "non_trading_day",
                        "trade_date": trade_date.isoformat(),
                        "timezone": timezone_name,
                        "latest_trading_day": latest_trading_day.isoformat() if latest_trading_day else None,
                    }
                    await cls._emit_progress(progress_callback, "skipped", detail, result)
                    return result

            prompt_template = (params.get("prompt_template") or "").strip()
            if not prompt_template:
                raise ValueError("缺少 prompt_template，无法执行自动化任务")

            now = datetime.now()
            await cls._emit_progress(progress_callback, "planning", "正在渲染任务参数与发布路径。")
            collection_slug = cls.build_collection_slug(params.get("publish_collection_slug"))
            entry_slug = cls.ensure_unique_entry_slug(
                collection_slug,
                cls.build_entry_slug(str(params.get("publish_slug") or ""), now),
                now,
            )
            publish_slug = cls.build_storage_slug(collection_slug, entry_slug)
            publish_title_template = str(params.get("publish_title") or "{date} · {brief}")
            enable_web_search = bool(params.get("enable_web_search"))
            mcp_servers = params.get("mcp_servers") if isinstance(params.get("mcp_servers"), list) else []
            notify_channel = params.get("notify_channel") if isinstance(params.get("notify_channel"), dict) else None

            account_context = None
            account_id = params.get("account_id")
            account_provider = params.get("account_provider")
            if account_id is not None and account_provider:
                account_context = {
                    "account_id": account_id,
                    "provider": account_provider,
                    "name": params.get("account_name"),
                }

            user_prompt = cls.build_report_prompt(prompt_template, publish_title_template, now)

            automation_session_id = f"automation-{task_id}-{now.strftime('%Y%m%d')}"

            message = ChannelMessage(
                channel="web_chat",
                session_id=automation_session_id,
                user_id=user.id,
                content=user_prompt,
                metadata={
                    "forced_role": skill_name,
                    "staged_response": True,
                    "account_context": account_context,
                    "automation": {
                        "task_id": task_id,
                        "mcp_servers": mcp_servers,
                        "publish_title_template": publish_title_template,
                    },
                },
            )

            await cls._emit_progress(progress_callback, "gathering", "正在调用 agent 执行工具采集与分析。", {"session_id": automation_session_id})
            reply = await AgentService.process_channel_message(
                message=message,
                db=db,
                user=user,
                enable_web_search=enable_web_search,
                model=params.get("model"),
            )

            agent_metadata = reply.metadata or {}
            if agent_metadata.get("staged_response_used"):
                await cls._emit_progress(
                    progress_callback,
                    "composing",
                    "已完成资料采集，正在生成最终成稿。",
                    {
                        "completion_reason": agent_metadata.get("completion_reason"),
                        "tool_loop_count": agent_metadata.get("tool_loop_count"),
                    },
                )

            publish_title = cls.extract_report_title(reply.content)

            await cls._emit_progress(progress_callback, "publishing", "正在写入已发布内容。", {"entry_slug": entry_slug})
            published = cls.write_published_report(
                slug=publish_slug,
                title=publish_title,
                content=reply.content,
                metadata={
                    "task_id": task_id,
                    "skill_name": skill_name,
                    "mcp_servers": mcp_servers,
                    "tool_outputs": reply.tool_outputs or [],
                    "agent_metadata": agent_metadata,
                    "user_id": user.id,
                    "collection_slug": collection_slug,
                    "entry_slug": entry_slug,
                    "publish_title_template": params.get("publish_title"),
                    "publish_collection_slug": params.get("publish_collection_slug"),
                    "publish_slug_template": params.get("publish_slug"),
                },
            )

            await cls._emit_progress(
                progress_callback,
                "completed",
                "自动化任务已完成并发布。",
                {
                    "published_path": cls.build_public_report_path(collection_slug, entry_slug),
                    "published_url": cls.build_public_report_url(collection_slug, entry_slug),
                },
            )

            notification_result = None
            notify_text = (
                f"AlphaBot 市场日报｜{published['title']}\n"
                f"已发布：{cls.build_public_report_url(collection_slug, entry_slug)}"
            )
            if notify_channel:
                from app.services.channel_service import send_configured
                await cls._emit_progress(progress_callback, "notifying", "正在发送推送通知。")
                notification_result = await send_configured(db, user.id, notify_channel, notify_text)
                await cls._emit_progress(progress_callback, "notified" if notification_result.get("success") else "notify_failed",
                    "推送通知已发送。" if notification_result.get("success") else "报告已生成，推送失败。", notification_result)

            return {
                "task_id": task_id,
                "session_id": automation_session_id,
                "status": "success",
                "skill_name": skill_name,
                "collection_slug": collection_slug,
                "entry_slug": entry_slug,
                "published_slug": publish_slug,
                "published_path": cls.build_public_report_path(collection_slug, entry_slug),
                "published_url": cls.build_public_report_url(collection_slug, entry_slug),
                "report_api_url": f"/api/v1/reports/collections/{collection_slug}/{entry_slug}",
                "title": published["title"],
                "content_preview": reply.content[:500],
                "tool_outputs": reply.tool_outputs or [],
                "agent_metadata": agent_metadata,
                "notification_result": notification_result,
                "notification_text": notify_text,
                "published_at": published["published_at"],
            }
        except Exception as exc:
            await cls._emit_progress(progress_callback, "failed", str(exc))
            raise
        finally:
            db.close()
