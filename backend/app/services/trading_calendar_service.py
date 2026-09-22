from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from app.core.config import settings

logger = logging.getLogger("uvicorn")


class TradingCalendarService:
    _trade_calendar_cache: list[date] | None = None
    _trade_calendar_source: str | None = None
    _trade_calendar_loaded_at: datetime | None = None

    @staticmethod
    async def _run_sync(func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    @classmethod
    async def get_trade_calendar(cls) -> list[date]:
        from app.core.config import settings
        from app.services.market_data_sources.factory import MarketDataSourceFactory
        source_name = "tdxaidata" if settings.DEFAULT_MARKET_DATA_SOURCE.strip().lower() == "tdxaidata" else "sina"
        now = datetime.utcnow()
        if (
            cls._trade_calendar_source == source_name
            and cls._trade_calendar_cache is not None
            and cls._trade_calendar_loaded_at is not None
            and (now - cls._trade_calendar_loaded_at) < timedelta(hours=6)
        ):
            return cls._trade_calendar_cache

        def _load_calendar() -> list[date]:
            try:
                import akshare as ak  # type: ignore
            except ModuleNotFoundError as exc:
                raise RuntimeError("akshare 未安装，无法加载交易日历") from exc

            calendar_df = ak.tool_trade_date_hist_sina()
            column = "trade_date" if "trade_date" in calendar_df.columns else calendar_df.columns[0]
            return [
                value.date() if hasattr(value, "date") else datetime.strptime(str(value), "%Y-%m-%d").date()
                for value in calendar_df[column].tolist()
            ]

        if source_name == "tdxaidata":
            _, source = MarketDataSourceFactory.resolve("quotes")
            cls._trade_calendar_cache = [datetime.strptime(d, "%Y%m%d").date() for d in await source.fetch_trading_dates()]
        else:
            cls._trade_calendar_cache = await cls._run_sync(_load_calendar)
        cls._trade_calendar_source = source_name
        cls._trade_calendar_loaded_at = now
        return cls._trade_calendar_cache

    @classmethod
    async def recent_trading_days(cls, limit: int, end_date: date | None = None) -> list[date]:
        calendar = await cls.get_trade_calendar()
        if limit <= 0:
            return []
        if end_date is None:
            end_date = datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
        values = [day for day in calendar if day <= end_date]
        return values[-limit:]

    @classmethod
    async def latest_trading_day(cls, ref_date: date | None = None) -> date | None:
        days = await cls.recent_trading_days(1, ref_date)
        return days[-1] if days else None
