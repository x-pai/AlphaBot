"""
Phase 0 能力标准化基础 测试

ROADMAP: T0.4 依赖与配置 | T0.1 LiteLLM 集成 | T0.2 LLM 注册表 | T0.3 替换调用点
验收：LLM_* 配置生效；LLMRegistry.get_client() 返回 LiteLLMService；chat_completion/stream 可用
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.core.config import settings
from app.services.llm_registry import LLMRegistry
from app.services.litellm_service import LiteLLMService


class TestConfigLLM:
    """T0.4 依赖与配置：仅 LLM_* 配置"""

    def test_llm_model_from_settings(self):
        """LLM_MODEL 存在且为非空字符串"""
        assert hasattr(settings, "LLM_MODEL")
        assert isinstance(settings.LLM_MODEL, str)
        assert len(settings.LLM_MODEL) > 0

    def test_llm_available_models_optional(self):
        """LLM_AVAILABLE_MODELS 可选，为字符串"""
        assert hasattr(settings, "LLM_AVAILABLE_MODELS")
        assert isinstance(settings.LLM_AVAILABLE_MODELS, str)


class TestLLMRegistry:
    """T0.2 LLM 注册表：始终返回 LiteLLMService"""

    def test_get_client_returns_litellm(self):
        """get_client() 返回 LiteLLMService 单例"""
        LLMRegistry._client = None
        client = LLMRegistry.get_client()
        assert client is not None
        assert isinstance(client, LiteLLMService)
        assert LLMRegistry.get_client() is client


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
