import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.task import ScheduledTask
from app.schemas.sentiment import SentimentSyncDateResponse
from app.services import automation_service
from app.services.agent_service import AgentRole, AgentService
from app.services.automation_service import AutomationService
from app.services.scheduler_service import SchedulerService


@pytest.fixture
def scheduler(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    ScheduledTask.__table__.create(engine)
    monkeypatch.setattr(SchedulerService, "_instance", None)
    service = SchedulerService()
    monkeypatch.setattr(service, "_db", sessionmaker(bind=engine))
    yield service
    engine.dispose()


async def run_task(scheduler, task_id, manual):
    if manual:
        return await scheduler.run_task_now(task_id)
    return await scheduler._execute_task(scheduler._tasks[task_id])


@pytest.mark.parametrize("manual", [False, True], ids=["scheduled", "manual"])
@pytest.mark.parametrize("success", [True, False], ids=["synced", "busy"])
async def test_sentiment_response_survives_database_round_trip(scheduler, manual, success):
    response = SentimentSyncDateResponse(
        trade_date="2026-10-26",
        success=success,
        synced_pools=["up_limit", "strong"] if success else [],
        metrics_ready=success,
        message="同步完成" if success else "该交易日正在同步中，请稍后重试",
    )
    task_id = await scheduler.add_task(func=AsyncMock(return_value=response))

    await run_task(scheduler, task_id, manual)

    record = scheduler._load_persisted_task_record(task_id)
    assert record.last_result == response.model_dump(mode="json")
    assert record.last_error is None
    assert (await scheduler.get_task(task_id))["result"] == record.last_result
    # 后续调度保存 next_run 时也必须能提交，不能再次触发序列化失败。
    assert await scheduler.update_task(task_id, next_run=1793052000)
    restored = scheduler._hydrate_task_from_record(
        scheduler._load_persisted_task_record(task_id), func=AsyncMock()
    )
    assert restored.last_result == record.last_result
    json.dumps(restored.to_dict())


@pytest.mark.parametrize("manual", [False, True], ids=["scheduled", "manual"])
async def test_nested_models_and_dates_are_json_compatible(scheduler, manual):
    response = SentimentSyncDateResponse(
        trade_date="2026-10-26", success=True, synced_pools=[],
        metrics_ready=True, message="同步完成",
    )
    task_id = await scheduler.add_task(func=AsyncMock(return_value={
        "results": [response], "date": date(2026, 10, 26),
        "finished_at": datetime(2026, 10, 26, 21, 10),
    }))
    await run_task(scheduler, task_id, manual)
    record = scheduler._load_persisted_task_record(task_id)
    assert record.status == "success"
    assert record.last_result == {
        "results": [response.model_dump(mode="json")],
        "date": "2026-10-26", "finished_at": "2026-10-26T21:10:00",
    }


@pytest.mark.parametrize("manual", [False, True], ids=["scheduled", "manual"])
async def test_invalid_result_does_not_poison_failure_or_next_run(scheduler, manual):
    func = AsyncMock(side_effect=[{"ok": True}, {"invalid": object()}, None])
    task_id = await scheduler.add_task(func=func)
    await run_task(scheduler, task_id, manual)
    await run_task(scheduler, task_id, manual)

    record = scheduler._load_persisted_task_record(task_id)
    assert record.status == "failed"
    assert "任务结果无法序列化为 JSON" in record.last_error
    assert record.last_result is None
    assert await scheduler.update_task(task_id, next_run=1793052000)

    await run_task(scheduler, task_id, manual)
    record = scheduler._load_persisted_task_record(task_id)
    assert record.status == "success"
    assert record.last_result is None
    assert record.last_error is None


@pytest.mark.parametrize("manual", [False, True], ids=["scheduled", "manual"])
async def test_agent_error_reaches_failed_task_without_publishing(
    scheduler, monkeypatch, tmp_path, manual,
):
    error = (
        "litellm.APIError: APIError: OpenAIException - 用户额度不足, "
        "剩余额度: ＄0.000000 (request id: quota-regression)"
    )
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
    monkeypatch.setattr(automation_service, "SessionLocal", lambda: db)
    monkeypatch.setattr(AutomationService, "published_dir", classmethod(lambda cls: str(tmp_path)))
    monkeypatch.setattr(AgentService, "_collect_extra_system_lines", AsyncMock(return_value=(AgentRole.GENERAL, [])))
    monkeypatch.setattr(AgentService, "_run_tool_loop", AsyncMock(side_effect=RuntimeError(error)))
    task_id = await scheduler.add_task(
        task_id="quota-test", func=AutomationService.execute_skill_publish_job,
        kwargs={"task_id": "quota-test", "params": {
            "user_id": 1, "skill_name": "research", "trading_days_only": False,
            "prompt_template": "请生成市场复盘",
        }},
    )

    await run_task(scheduler, task_id, manual)

    record = scheduler._load_persisted_task_record(task_id)
    assert record.status == "failed"
    assert record.last_error == error
    assert record.status_detail == error
    assert record.stage_history[-1]["stage"] == "failed"
    assert record.stage_history[-1]["detail"] == error
    assert "publishing" not in [item["stage"] for item in record.stage_history]
    assert (await scheduler.get_task(task_id))["error"] == error
    assert not list(tmp_path.iterdir())
    db.close.assert_called_once()
