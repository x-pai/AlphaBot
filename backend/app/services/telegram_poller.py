import asyncio
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.api.routes.channel_telegram import handle_telegram_update
from app.middleware.logging import logger


async def run_telegram_poller() -> None:
    """
    长轮询 Telegram getUpdates，用于后端不暴露公网时的集成方式。

    要求：
    - TELEGRAM_BOT_TOKEN 已在环境变量中配置；
    - 后端具备访问 Telegram API 的网络出站权限。
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN 未配置，跳过 Telegram 轮询任务。")
        return

    base_url = f"https://api.telegram.org/bot{token}"
    offset: Optional[int] = None

    logger.info("启动 Telegram 轮询任务（getUpdates 模式）")

    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            try:
                params: Dict[str, Any] = {"timeout": 30}
                if offset is not None:
                    params["offset"] = offset + 1

                resp = await client.get(f"{base_url}/getUpdates", params=params)
                data = resp.json()

                if not data.get("ok"):
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    update_id = update.get("update_id")
                    if update_id is None:
                        continue
                    offset = update_id

                    db = SessionLocal()
                    try:
                        await handle_telegram_update(update, db)
                    except Exception as e:  # noqa: BLE001
                        logger.error("处理 Telegram update 出错: %s", e)
                    finally:
                        db.close()

            except Exception as e:  # noqa: BLE001
                logger.error("Telegram 轮询任务异常: %s", e)
                await asyncio.sleep(5)

