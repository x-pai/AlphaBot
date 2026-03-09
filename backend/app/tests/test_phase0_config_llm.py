"""
Phase 0 能力标准化基础 测试

ROADMAP: T0.4 依赖与配置 | T0.1 LiteLLM 集成 | T0.2 LLM 注册表 | T0.3 替换调用点
验收：LLM_MODEL 生效；LLMRegistry.get() 按配置返回；chat_completion/stream 与 OpenAIService 兼容
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.config import settings
from app.services.llm_registry import LLMRegistry
from app.services.litellm_service import LiteLLMService
from app.services.openai_service import OpenAIService


class TestConfigLLM:
    """T0.4 依赖与配置：LLM_* 与 OPENAI_* 可生效"""

    def test_llm_model_from_env(self):
        """LLM_MODEL 可从环境读取，或回落到 OPENAI_MODEL"""
        assert hasattr(settings, "LLM_MODEL")
        assert isinstance(settings.LLM_MODEL, str)
        assert len(settings.LLM_MODEL) > 0

    def test_llm_provider_default(self):
        """LLM_PROVIDER 默认存在"""
        assert hasattr(settings, "LLM_PROVIDER")
        assert settings.LLM_PROVIDER in ("openai", "litellm", "openai_legacy") or isinstance(
            settings.LLM_PROVIDER, str
        )


class TestLLMRegistry:
    """T0.2 LLM 注册表：按配置返回对应客户端"""

    def test_get_client_returns_litellm_by_default(self):
        """默认或 litellm 时返回 LiteLLMService 实例"""
        LLMRegistry._litellm_client = None
        LLMRegistry._openai_client = None
        with patch.object(settings, "LLM_PROVIDER", "openai"):
            client = LLMRegistry.get_client()
            assert client is not None
            assert isinstance(client, LiteLLMService)

    def test_get_client_returns_openai_legacy_when_configured(self):
        """LLM_PROVIDER=openai_legacy 时返回 OpenAIService"""
        with patch.object(settings, "LLM_PROVIDER", "openai_legacy"):
            LLMRegistry._litellm_client = None
            LLMRegistry._openai_client = None
            client = LLMRegistry.get_client()
            assert client is not None
            assert isinstance(client, OpenAIService)


@pytest.mark.asyncio
class TestLiteLLMService:
    """T0.1 LiteLLM 集成：chat_completion / stream 接口与 OpenAIService 兼容"""

    async def test_chat_completion_returns_dict_with_choices(self):
        """chat_completion 返回 dict，含 choices[].message"""
        with patch("app.services.litellm_service.acompletion", new_callable=AsyncMock) as m:
            m.return_value = MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "choices": [{"message": {"content": "hello", "role": "assistant"}}],
                        "usage": {},
                    }
                )
            )
            svc = LiteLLMService()
            out = await svc.chat_completion(messages=[{"role": "user", "content": "hi"}])
            assert isinstance(out, dict)
            assert "choices" in out
            assert len(out["choices"]) >= 1
            assert out["choices"][0].get("message", {}).get("content") == "hello"

    async def test_chat_completion_stream_yields_strings(self):
        """chat_completion_stream 为异步生成器，产出字符串片段"""
        async def fake_stream():
            for ch in ["h", "i"]:
                yield MagicMock(choices=[MagicMock(delta=MagicMock(content=ch))])

        with patch("app.services.litellm_service.acompletion", return_value=fake_stream()):
            svc = LiteLLMService()
            chunks = []
            async for delta in svc.chat_completion_stream(
                messages=[{"role": "user", "content": "hi"}]
            ):
                chunks.append(delta)
            assert chunks == ["h", "i"]
