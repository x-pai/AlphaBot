"""
LLM Registry

统一通过 LiteLLM 提供 LLM 能力，配置见 LLM_* 环境变量（.env / .env.example）。
"""

from typing import Optional

from app.core.config import settings
from app.services.litellm_service import LiteLLMService


class LLMRegistry:
    """LLM 客户端单例，始终使用 LiteLLMService（LiteLLM 统一接口）。"""

    _client: Optional[LiteLLMService] = None

    @classmethod
    def get_client(cls) -> LiteLLMService:
        if cls._client is None:
            cls._client = LiteLLMService()
        return cls._client

