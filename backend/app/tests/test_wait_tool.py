import asyncio
from unittest.mock import AsyncMock
import pytest
from app.skills.registry import SkillRegistry
from app.services.agent_service import AgentService, AgentRole


@pytest.mark.asyncio
async def test_wait_through_agent_execution(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr('app.skills.registry.asyncio.sleep', sleep)
    result = await AgentService.execute_tool('wait', {'seconds': 5, 'reason': '服务繁忙'}, None, None)
    sleep.assert_awaited_once_with(5)
    assert result['waited_seconds'] == 5 and result['success']


@pytest.mark.asyncio
@pytest.mark.parametrize('seconds', [0, -1, 31, True, '5', 1.5, None])
async def test_invalid_wait_does_not_sleep(monkeypatch, seconds):
    sleep = AsyncMock()
    monkeypatch.setattr('app.skills.registry.asyncio.sleep', sleep)
    result = await SkillRegistry.get_handler('wait')({'seconds': seconds, 'reason': '限频'}, None, None)
    assert 'error' in result
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_wait_cancellation_propagates(monkeypatch):
    monkeypatch.setattr('app.skills.registry.asyncio.sleep', AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await AgentService.execute_tool('wait', {'seconds': 5, 'reason': '限频'}, None, None)


def test_wait_available_for_all_agent_roles():
    for role in AgentRole:
        assert 'wait' in {tool.name for tool in AgentService.get_available_tools(role)}
