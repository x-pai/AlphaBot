"""
LLM Registry

统一管理后端可用的大模型客户端，实现「能力标准化」：
- 默认使用 LiteLLMService（支持通过 LLM_* 与 OPENAI_* 配置切换）
- 如有需要，可扩展为支持不同 provider / 路由策略
"""

from typing import Optional

from app.core.config import settings
from app.services.litellm_service import LiteLLMService
from app.services.openai_service import OpenAIService


class LLMRegistry:
    """
    简单的 LLM 客户端注册表。

    当前策略：
    - 当 LLM_PROVIDER=litellm 时，返回 LiteLLMService（推荐）
    - 当 LLM_PROVIDER=openai_legacy 时，返回旧的 OpenAIService
    - 默认：优先使用 LiteLLMService，兼容现有 OPENAI_* 配置
    """

    _litellm_client: Optional[LiteLLMService] = None
    _openai_client: Optional[OpenAIService] = None

    @classmethod
    def get_client(cls):
        provider = (settings.LLM_PROVIDER or "openai").lower()

        # 显式走旧版 OpenAIService（完全绕过 liteLLM）
        if provider in {"openai_legacy"}:
            if cls._openai_client is None:
                cls._openai_client = OpenAIService()
            return cls._openai_client

        # 默认 / litellm：统一通过 LiteLLMService
        if cls._litellm_client is None:
            cls._litellm_client = LiteLLMService()
        return cls._litellm_client

