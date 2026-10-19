from datetime import datetime
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
