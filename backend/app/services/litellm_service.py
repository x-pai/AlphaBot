"""
LiteLLM 统一 LLM 客户端封装

目标：
- 对外提供与 OpenAIService 兼容的 chat_completion / chat_completion_stream 接口
- 内部通过 liteLLM 适配多家模型/网关（OpenAI、代理、私有部署等）
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

from litellm import acompletion

from app.core.config import settings


class LiteLLMService:
    """基于 liteLLM 的通用 LLM 客户端"""

    def __init__(self) -> None:
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self.api_base = settings.LLM_API_BASE
        self.api_key = settings.LLM_API_KEY
        self.provider = settings.LLM_PROVIDER

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        tool_choice: Any = "auto",
    ) -> Dict[str, Any]:
        """
        使用 liteLLM 调用对话模型，返回与 OpenAI SDK 近似的响应结构（dict）。

        - messages: OpenAI 风格的 messages 列表
        - tools / tool_choice: 直接透传给 liteLLM（其会转为各家模型的工具调用格式）
        """
        params: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        # liteLLM 支持统一的 base_url / api_key，通过 config 或环境变量读取
        # 这里显式传入，便于支持自建网关
        if self.api_base:
            params["base_url"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key

        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = await acompletion(**params)

        # ModelResponse 本身就是 OpenAI 风格的数据结构，转成 dict 以与现有代码兼容
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "dict"):
            return response.dict()
        # 兜底：转成普通 dict
        try:
            return dict(response)  # type: ignore[arg-type]
        except Exception:
            return {"raw": str(response)}

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        tool_choice: Any = "auto",
    ) -> AsyncGenerator[str, None]:
        """
        使用 liteLLM 进行流式对话生成，按增量内容产出字符串片段。
        """
        params: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": True,
        }

        if self.api_base:
            params["base_url"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key

        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        stream = await acompletion(**params)
        async for event in stream:
            try:
                # 与 OpenAI 流式事件保持一致的访问方式
                delta = event.choices[0].delta.content or ""
            except Exception:
                delta = ""
            if delta:
                yield delta

