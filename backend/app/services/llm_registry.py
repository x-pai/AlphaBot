"""
LLM Registry

统一通过 LiteLLM 提供 LLM 能力。

支持多 profile（DEFAULT / RESEARCH / RISK），每个 profile 可在 .env 中配置独立的
模型、base_url、api_key、max_tokens、temperature；未配置时回退到全局 LLM_*。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from app.core.config import settings
from app.services.litellm_service import LiteLLMService


class LLMProfileName(str, Enum):
    DEFAULT = "default"
    RESEARCH = "research"
    RISK = "risk"


@dataclass
class LLMProfile:
    model: str
    api_base: str
    api_key: str
    max_tokens: int
    temperature: float


class LLMRegistry:
    """LLM 客户端注册表：按 profile 复用 LiteLLMService 实例。"""

    _clients: Dict[LLMProfileName, LiteLLMService] = {}

    @classmethod
    def _build_profile(cls, profile: LLMProfileName) -> LLMProfile:
        s = settings
        # DEFAULT：优先用 LLM_DEFAULT_*，否则回退到 LLM_*
        if profile == LLMProfileName.DEFAULT:
            model = s.LLM_DEFAULT_MODEL or s.LLM_MODEL
            api_base = s.LLM_DEFAULT_API_BASE or s.LLM_API_BASE
            api_key = s.LLM_DEFAULT_API_KEY or s.LLM_API_KEY
            max_tokens = s.LLM_DEFAULT_MAX_TOKENS or s.LLM_MAX_TOKENS
            temperature = s.LLM_DEFAULT_TEMPERATURE or s.LLM_TEMPERATURE
        elif profile == LLMProfileName.RESEARCH:
            model = s.LLM_RESEARCH_MODEL or s.LLM_MODEL
            api_base = s.LLM_RESEARCH_API_BASE or s.LLM_API_BASE
            api_key = s.LLM_RESEARCH_API_KEY or s.LLM_API_KEY
            max_tokens = s.LLM_RESEARCH_MAX_TOKENS or s.LLM_MAX_TOKENS
            temperature = s.LLM_RESEARCH_TEMPERATURE or s.LLM_TEMPERATURE
        elif profile == LLMProfileName.RISK:
            model = s.LLM_RISK_MODEL or s.LLM_MODEL
            api_base = s.LLM_RISK_API_BASE or s.LLM_API_BASE
            api_key = s.LLM_RISK_API_KEY or s.LLM_API_KEY
            max_tokens = s.LLM_RISK_MAX_TOKENS or s.LLM_MAX_TOKENS
            temperature = s.LLM_RISK_TEMPERATURE or s.LLM_TEMPERATURE
        else:
            model = s.LLM_MODEL
            api_base = s.LLM_API_BASE
            api_key = s.LLM_API_KEY
            max_tokens = s.LLM_MAX_TOKENS
            temperature = s.LLM_TEMPERATURE
        return LLMProfile(
            model=model,
            api_base=api_base,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @classmethod
    def get_client(cls, profile: LLMProfileName = LLMProfileName.DEFAULT) -> LiteLLMService:
        """按 profile 获取 LiteLLMService 实例，未传时使用 DEFAULT。"""
        if profile not in cls._clients:
            cfg = cls._build_profile(profile)
            cls._clients[profile] = LiteLLMService(
                model=cfg.model,
                api_base=cfg.api_base,
                api_key=cfg.api_key,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
            )
        return cls._clients[profile]
