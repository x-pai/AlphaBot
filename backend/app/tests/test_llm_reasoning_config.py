from unittest.mock import AsyncMock
import pytest
from app.services.litellm_service import LiteLLMService
from app.services.llm_registry import LLMRegistry, LLMProfileName
from app.core.config import settings


@pytest.mark.asyncio
@pytest.mark.parametrize('effort', ['none', 'high', ''])
async def test_reasoning_forwarded_without_changing_temperature(monkeypatch, effort):
    call = AsyncMock(return_value={})
    monkeypatch.setattr('app.services.litellm_service.acompletion', call)
    client = LiteLLMService(temperature=0.1, reasoning_effort=effort)
    await client.chat_completion([])
    assert call.call_args.kwargs['temperature'] == 0.1
    assert call.call_args.kwargs.get('reasoning_effort') == (effort or None)
    if not effort:
        assert 'reasoning_effort' not in call.call_args.kwargs
    async def events():
        if False:
            yield None
    call.return_value = events()
    async for _ in client.chat_completion_stream([]):
        pass
    assert call.call_args.kwargs['temperature'] == 0.1
    assert call.call_args.kwargs.get('reasoning_effort') == (effort or None)


def test_profile_override_and_fallback(monkeypatch):
    monkeypatch.setattr(settings, 'LLM_REASONING_EFFORT', 'high')
    monkeypatch.setattr(settings, 'LLM_RESEARCH_REASONING_EFFORT', 'none')
    assert LLMRegistry.get_client(LLMProfileName.RESEARCH, max_tokens_override=100).reasoning_effort == 'none'
    monkeypatch.setattr(settings, 'LLM_RESEARCH_REASONING_EFFORT', None)
    assert LLMRegistry._build_profile(LLMProfileName.RESEARCH).reasoning_effort == 'high'
