import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

async def validate_webhook_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Webhook 必须使用不含用户名密码的公网 HTTPS 地址")
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except (OSError, ValueError):
        raise ValueError("Webhook 地址无法解析") from None
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Webhook 不允许访问内网或本机地址")
    return parsed, addresses[0][4][0]
