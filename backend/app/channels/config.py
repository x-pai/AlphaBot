from dataclasses import dataclass
from typing import List, Optional

from app.channels.base import ChannelType


@dataclass
class ChannelConfig:
    """
    每个渠道的基础配置与策略。

    后续可扩展：
    - per-channel 模型 / 温度
    - 允许 / 禁用的 Skill 列表
    - 不同角色在群聊 / 私聊下的默认行为
    """

    channel: ChannelType
    allow_tools: Optional[List[str]] = None
    default_role: Optional[str] = None
    allow_web_search: bool = False


def get_channel_config(channel: str) -> ChannelConfig:
    """
    获取指定渠道的配置。

    目前提供几种简单默认：
    - web_chat：允许全部工具，默认 general，允许联网搜索（由前端控制）。
    - feishu / telegram：默认 general，关闭联网搜索。
    """
    ch = ChannelType(channel)

    if ch == ChannelType.WEB_CHAT:
        return ChannelConfig(
            channel=ch,
            allow_tools=None,  # None 表示使用角色配置决定
            default_role="general",
            allow_web_search=True,
        )

    if ch in (ChannelType.FEISHU, ChannelType.TELEGRAM):
        return ChannelConfig(
            channel=ch,
            allow_tools=None,
            default_role="general",
            allow_web_search=False,
        )

    # 其它渠道采用保守默认
    return ChannelConfig(
        channel=ch,
        allow_tools=None,
        default_role="general",
        allow_web_search=False,
    )

