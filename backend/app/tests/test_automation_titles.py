from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import automation_service
from app.services.automation_service import AutomationService
from app.services.llm_registry import LLMRegistry


@pytest.mark.parametrize(
    ("template", "rendered"),
    [
        ("{date} · {brief}", "2026-10-19 · {brief}"),
        ("午评｜{date_compact}｜{brief}", "午评｜20261019｜{brief}"),
        ("我的市场观察", "我的市场观察"),
        ("  ", "2026-10-19 · {brief}"),
    ],
)
def test_title_rule_is_injected_into_report_prompt(template, rendered):
    prompt = AutomationService.build_report_prompt(
        "请生成 {date} 的午评", template, datetime(2026, 10, 19)
    )
    assert prompt.startswith("请生成 2026-10-19 的午评")
    assert f"标题规则：{rendered}\n" in prompt
    assert "第一个非空行必须是 Markdown 一级标题" in prompt


def test_extract_report_title_preserves_date_spacing_and_full_text():
    title = "2026-10-19 · 军工与低空经济活跃 资金回流防御方向"
    assert AutomationService.extract_report_title(f"\n# {title} ###\n\n## 正文") == title


@pytest.mark.parametrize(
    "content",
    ["", "# ", "# ###", "## 二级标题", "正文\n# 后面的标题", "```markdown\n# 代码中的标题\n```", "# {date} · {brief}"],
)
def test_missing_or_unresolved_title_is_rejected(content):
    with pytest.raises(ValueError, match="无法发布"):
        AutomationService.extract_report_title(content)


@pytest.fixture
def publish_job(monkeypatch, tmp_path):
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
    monkeypatch.setattr(automation_service, "SessionLocal", lambda: db)
    monkeypatch.setattr(AutomationService, "published_dir", classmethod(lambda cls: str(tmp_path)))
    # Publishing must never make an independent title-generation LLM call.
    monkeypatch.setattr(LLMRegistry, "get_client", Mock(side_effect=AssertionError("unexpected LLM call")))
    agent = AsyncMock()
    monkeypatch.setattr(automation_service.AgentService, "process_channel_message", agent)
    params = {
        "user_id": 1,
        "skill_name": "research",
        "trading_days_only": False,
        "prompt_template": "请生成 {date} 的市场复盘",
        "publish_title": "{date} · {brief}",
    }
    return agent, params, tmp_path, db


@pytest.mark.asyncio
async def test_report_title_is_used_for_publication_and_notification(publish_job):
    agent, params, _, db = publish_job
    captured = {}

    async def generate_report(*, message, **kwargs):
        captured["prompt"] = message.content
        rule = message.content.split("标题规则：", 1)[1].splitlines()[0]
        title = rule.replace("{brief}", "缩量震荡主线分化")
        captured["content"] = f"# {title}\n\n## 市场概况\n报告正文。"
        return SimpleNamespace(content=captured["content"], metadata={}, tool_outputs=[])

    agent.side_effect = generate_report
    result = await AutomationService.execute_skill_publish_job(task_id="title-test", params=params)
    published = AutomationService.load_published_report(result["published_slug"])

    assert "标题规则：" in captured["prompt"]
    assert published["content"] == captured["content"]
    assert published["title"] == captured["content"].splitlines()[0][2:]
    assert result["title"] == published["title"]
    assert published["title"] in result["notification_text"]
    assert published["metadata"]["publish_title_template"] == params["publish_title"]
    agent.assert_awaited_once()
    db.close.assert_called_once()


@pytest.mark.asyncio
async def test_missing_title_fails_before_writing_report(publish_job):
    agent, params, published_dir, db = publish_job
    agent.return_value = SimpleNamespace(content="只有正文，没有标题", metadata={}, tool_outputs=[])
    progress = AsyncMock()

    with pytest.raises(ValueError, match="无法发布"):
        await AutomationService.execute_skill_publish_job(
            task_id="missing-title", params=params, progress_callback=progress
        )

    assert not list(published_dir.iterdir())
    assert progress.call_args.args[0] == "failed"
    db.close.assert_called_once()


@pytest.mark.parametrize(
    ("report_day", "previous_day"),
    [("2026-11-09", "2026-11-06"), ("2026-10-09", "2026-09-30")],
)
def test_premarket_uses_previous_trading_day_across_market_closures(report_day, previous_day):
    context = AutomationService.build_premarket_context(
        datetime.fromisoformat(f"{report_day}T08:30:00+08:00"),
        [date.fromisoformat(previous_day), date.fromisoformat(report_day)],
    )
    assert context["report_date"] == report_day
    assert context["previous_trading_day"] == previous_day
    assert context["information_cutoff"] == f"{report_day}T08:30:00+08:00"
    assert context["early_edition"] is False


@pytest.mark.parametrize(
    ("run_at", "cutoff", "early"),
    [
        ("2026-11-03T23:45:00+00:00", "2026-11-04T07:45:00+08:00", True),
        ("2026-11-04T05:00:00+00:00", "2026-11-04T08:30:00+08:00", False),
    ],
)
def test_premarket_cutoff_uses_shanghai_date_and_never_future_or_post_cutoff_data(run_at, cutoff, early):
    context = AutomationService.build_premarket_context(
        datetime.fromisoformat(run_at), [date(2026, 11, 3), date(2026, 11, 4)]
    )
    assert context["report_date"] == "2026-11-04"
    assert context["information_cutoff"] == cutoff
    assert context["early_edition"] is early


def test_missing_previous_trading_day_is_not_guessed():
    context = AutomationService.build_premarket_context(
        datetime.fromisoformat("2026-11-04T08:30:00+08:00"), [date(2026, 11, 4)]
    )
    assert context["previous_trading_day"] is None


def freeze_run_time(monkeypatch, instant):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(automation_service, "datetime", FrozenDateTime)


@pytest.mark.parametrize("skill_name", sorted(AutomationService.PREMARKET_SKILLS))
@pytest.mark.asyncio
async def test_premarket_job_passes_and_persists_the_same_time_boundary(publish_job, monkeypatch, skill_name):
    agent, params, _, _ = publish_job
    freeze_run_time(monkeypatch, datetime(2026, 11, 3, 23, 45, tzinfo=timezone.utc))
    monkeypatch.setattr(
        automation_service.TradingCalendarService, "get_trade_calendar",
        AsyncMock(return_value=[date(2026, 11, 3), date(2026, 11, 4)]),
    )
    params.update(skill_name=skill_name, timezone="UTC")
    params.pop("trading_days_only")
    agent.return_value = SimpleNamespace(content="# 2026-11-04 · 盘前观察\n\n正文", metadata={}, tool_outputs=[])

    result = await AutomationService.execute_skill_publish_job(task_id="premarket", params=params)
    message = agent.call_args.kwargs["message"]
    context = message.metadata["report_context"]
    published = AutomationService.load_published_report(result["published_slug"])

    assert context["report_date"] == "2026-11-04"
    assert context["previous_trading_day"] == "2026-11-03"
    assert context["information_cutoff"] == "2026-11-04T07:45:00+08:00"
    assert '"information_cutoff": "2026-11-04T07:45:00+08:00"' in message.content
    assert "标题规则：2026-11-04 · {brief}" in message.content
    assert result["entry_slug"] == "review-20261104"
    assert published["metadata"]["report_context"] == context


@pytest.mark.parametrize("skill_name", sorted(AutomationService.PREMARKET_SKILLS))
@pytest.mark.asyncio
async def test_both_premarket_skills_skip_nontrading_days_by_default(publish_job, monkeypatch, skill_name):
    agent, params, published_dir, _ = publish_job
    freeze_run_time(monkeypatch, datetime(2026, 11, 7, 0, 30, tzinfo=timezone.utc))
    monkeypatch.setattr(
        automation_service.TradingCalendarService, "get_trade_calendar",
        AsyncMock(return_value=[date(2026, 11, 6)]),
    )
    monkeypatch.setattr(
        automation_service.TradingCalendarService, "latest_trading_day",
        AsyncMock(return_value=date(2026, 11, 6)),
    )
    params["skill_name"] = skill_name
    params.pop("trading_days_only")

    result = await AutomationService.execute_skill_publish_job(task_id="closed-market", params=params)

    assert result["status"] == "skipped"
    assert result["trade_date"] == "2026-11-07"
    agent.assert_not_awaited()
    assert not list(published_dir.iterdir())
