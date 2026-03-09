from typing import Optional, Tuple

ROLE_ALIASES = {
    "general": "general",
    "g": "general",
    "portfolio": "portfolio",
    "p": "portfolio",
    "alert": "alert",
    "a": "alert",
    "research": "research",
    "r": "research",
    "risk": "risk",
}


def parse_role_and_content(raw_text: str) -> Tuple[Optional[str], str]:
    """
    从消息文本中解析显式角色前缀。

    支持的形式：
    - /portfolio 内容
    - /p 内容
    - portfolio: 内容
    - alert: 内容
    若未识别到前缀，则返回 (None, 原文去首尾空格)。
    """
    text = (raw_text or "").strip()
    if not text:
        return None, ""

    # 1) 斜杠前缀：/portfolio xxx
    if text.startswith("/"):
        parts = text[1:].split(maxsplit=1)
        if parts:
            head = parts[0].lower()
            if head in ROLE_ALIASES:
                content = parts[1] if len(parts) > 1 else ""
                return ROLE_ALIASES[head], content.strip()

    # 2) 冒号前缀：portfolio: xxx
    if ":" in text:
        head, body = text.split(":", 1)
        head = head.strip().lower()
        if head in ROLE_ALIASES:
            return ROLE_ALIASES[head], body.strip()

    return None, text

