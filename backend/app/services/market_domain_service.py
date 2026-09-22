from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from app.core.config import settings
from typing import Any

from app.services import market_cache
from app.services.market_data_sources import MarketDataSourceFactory
from app.services.market_strategy_service import MarketStrategyService
from app.services.trading_calendar_service import TradingCalendarService

logger = logging.getLogger("uvicorn")


class MarketDomainService:
    POOL_KINDS = ("zt", "zb", "dt")
    QUOTES_TTL_SECONDS = 20
    FUNDFLOW_INTRADAY_TTL_SECONDS = 3 * 60
    MEMBERS_INTRADAY_TTL_SECONDS = 2 * 60
    PLATE_INDEX_INTRADAY_TTL_SECONDS = 5 * 60
    TRENDING_TTL_SECONDS = 15 * 60
    PAYOFF_SHORT_TTL_SECONDS = 2 * 60
    PAYOFF_DRAWDOWN_HISTORY_TTL_SECONDS = 7 * 24 * 60 * 60
    TURNOVER_TTL_SECONDS = 15
    POOL_FRESH_SECONDS = 20
    UNIVERSE_FRESH_SECONDS = 5 * 60
    SURGE_FRESH_SECONDS = 45
    TRADE_DAY_RETENTION_SECONDS = 7 * 24 * 60 * 60
    EMPTY_MARK_TTL_SECONDS = 60 * 60
    HOT_TTL_JITTER_RATIO = 0.1
    _freshness_locks: dict[str, asyncio.Lock] = {}
    _freshness_last_ok: dict[str, float] = {}

    @staticmethod
    def _normalize_day(value: str | None) -> str:
        return (value or "").replace("-", "").strip()

    @staticmethod
    def _is_after_close(now: datetime) -> bool:
        return now.weekday() >= 5 or (now.hour * 60 + now.minute) > 15 * 60 + 5

    @classmethod
    async def _is_closed_window(cls) -> bool:
        now = datetime.now(ZoneInfo(settings.APP_TIMEZONE))
        today = now.strftime("%Y%m%d")
        latest = await cls.latest_trading_day()
        return latest != today or cls._is_after_close(now)

    @classmethod
    async def _single_flight_freshness(cls, key: str, min_interval: float, fetch) -> None:
        now = time.time()
        if cls._freshness_last_ok.get(key, 0.0) + min_interval > now:
            return
        lock = cls._freshness_locks.setdefault(key, asyncio.Lock())
        if lock.locked():
            async with lock:
                return
        async with lock:
            if cls._freshness_last_ok.get(key, 0.0) + min_interval > time.time():
                return
            await fetch()
            cls._freshness_last_ok[key] = time.time()

    @classmethod
    def _ttl_with_jitter(cls, ttl_seconds: int, cache_key: str, enabled: bool = False) -> int:
        if not enabled or ttl_seconds <= 1:
            return ttl_seconds
        spread = max(1, int(ttl_seconds * cls.HOT_TTL_JITTER_RATIO))
        digest = hashlib.sha1(cache_key.encode("utf-8")).digest()
        offset = int.from_bytes(digest[:2], "big") % (spread * 2 + 1) - spread
        return max(1, ttl_seconds + offset)

    @staticmethod
    def _trade_day_items_from_payload(payload: Any) -> Any:
        if isinstance(payload, dict):
            return payload.get("items") or []
        if isinstance(payload, list):
            return payload
        return []

    @staticmethod
    def _trade_day_fetched_at(payload: Any) -> float:
        if isinstance(payload, dict):
            return float(payload.get("fetchedAtTs") or 0)
        return 0.0

    @classmethod
    async def latest_trading_day(cls) -> str:
        calendar = await TradingCalendarService.get_trade_calendar()
        today = datetime.now(ZoneInfo(settings.APP_TIMEZONE)).strftime("%Y-%m-%d")
        for day in reversed(calendar):
            if day.isoformat() <= today:
                return day.isoformat().replace("-", "")
        return today.replace("-", "")

    @classmethod
    async def _cache_trade_day(cls) -> str:
        return await cls.latest_trading_day()

    @classmethod
    async def _fetch_and_store_pool(cls, kind: str, day: str, source_name: str, source) -> None:
        latest = await cls.latest_trading_day()
        items = await source.fetch_pool(
            kind,
            None if day == latest else f"{day[:4]}-{day[4:6]}-{day[6:8]}",
        )
        await market_cache.set_json(
            market_cache.source_key("pools", source_name, market_cache.pool_key(kind, day)),
            {"date": day, "fetchedAtTs": time.time(), "items": items or []},
        )

    @classmethod
    async def _get_trade_day_items(
        cls,
        *,
        cache_key: str,
        trade_day: str,
        label: str,
        refresh_seconds: int,
        fetch,
        freshness_key: str | None = None,
    ) -> list[Any]:
        started_at = time.perf_counter()
        payload = await market_cache.get_json(cache_key)
        closed = await cls._is_closed_window()

        def log_hit() -> None:
            logger.info(
                "market.cache hit label=%s key=%s elapsed_ms=%.2f",
                label,
                cache_key,
                (time.perf_counter() - started_at) * 1000,
            )

        def log_refresh() -> None:
            logger.info(
                "market.cache refresh label=%s key=%s elapsed_ms=%.2f",
                label,
                cache_key,
                (time.perf_counter() - started_at) * 1000,
            )

        async def fetch_payload() -> dict[str, Any]:
            items = await fetch()
            return {"date": trade_day, "fetchedAtTs": time.time(), "items": items or []}

        if payload is not None:
            if closed:
                log_hit()
                return cls._trade_day_items_from_payload(payload)
            fetched_at = cls._trade_day_fetched_at(payload)
            if time.time() - fetched_at < refresh_seconds:
                log_hit()
                return cls._trade_day_items_from_payload(payload)

        if payload is None:
            payload = await market_cache.cached_call(
                cache_key,
                cls.TRADE_DAY_RETENTION_SECONDS,
                fetch_payload,
            )
            log_refresh()
            return cls._trade_day_items_from_payload(payload)

        await cls._single_flight_freshness(
            freshness_key or label,
            refresh_seconds,
            lambda: market_cache.overwrite_json(
                cache_key,
                fetch_payload(),
                cls.TRADE_DAY_RETENTION_SECONDS,
            ),
        )
        refreshed = await market_cache.get_json(cache_key) or payload
        log_refresh()
        return cls._trade_day_items_from_payload(refreshed)

    @classmethod
    async def _ensure_pool_fresh(cls, kind: str, source_name: str, source) -> None:
        now = datetime.now(ZoneInfo(settings.APP_TIMEZONE))
        latest = await cls.latest_trading_day()
        key = market_cache.source_key("pools", source_name, market_cache.pool_key(kind, latest))
        payload = await market_cache.get_json(key)
        if payload is not None and cls._is_after_close(now):
            return
        if payload is not None and (time.time() - payload.get("fetchedAtTs", 0)) < cls.POOL_FRESH_SECONDS:
            return
        try:
            await cls._single_flight_freshness(
                f"{source_name}:pool-{kind}",
                cls.POOL_FRESH_SECONDS,
                lambda: cls._fetch_and_store_pool(kind, latest, source_name, source),
            )
        except Exception:
            if source_name == "tdxaidata":
                raise
            logger.exception("market.pool refresh failed, serving empty payload kind=%s day=%s", kind, latest)
            await market_cache.set_json(
                key,
                {"date": latest, "fetchedAtTs": time.time(), "items": []},
                ttl=cls.EMPTY_MARK_TTL_SECONDS,
            )

    @classmethod
    async def _ensure_pool_backfill(cls, kind: str, day: str, source_name: str, source) -> None:
        if day > await cls.latest_trading_day():
            return
        key = market_cache.source_key("pools", source_name, market_cache.pool_key(kind, day))
        if await market_cache.get_json(key) is not None:
            return
        items = await source.fetch_pool(
            kind,
            f"{day[:4]}-{day[4:6]}-{day[6:8]}",
        )
        if items:
            await market_cache.set_json(key, {"date": day, "fetchedAtTs": time.time(), "items": items})
        else:
            await market_cache.set_json(key, {"date": day, "items": []}, ttl=cls.EMPTY_MARK_TTL_SECONDS)

    @classmethod
    async def _ensure_universe_fresh(cls, source_name: str, source) -> None:
        trade_day = await cls._cache_trade_day()
        key = market_cache.source_key("universe", source_name, market_cache.universe_key_for_day(trade_day))
        try:
            await cls._get_trade_day_items(
                cache_key=key,
                trade_day=trade_day,
                label="universe",
                refresh_seconds=cls.UNIVERSE_FRESH_SECONDS,
                fetch=source.fetch_universe,
                freshness_key=f"{source_name}:universe",
            )
        except Exception:
            if source_name == "tdxaidata":
                raise
            logger.exception("market.universe refresh failed, serving empty payload")
            await market_cache.set_json(
                key,
                {"date": trade_day, "fetchedAtTs": time.time(), "items": []},
                ttl=cls.EMPTY_MARK_TTL_SECONDS,
            )

    @classmethod
    async def _ensure_surge_fresh(cls, source_name: str, source) -> None:
        trade_day = await cls._cache_trade_day()
        key = market_cache.source_key("surge", source_name, market_cache.surge_key_for_day(trade_day))
        try:
            await cls._get_trade_day_items(
                cache_key=key,
                trade_day=trade_day,
                label="surge",
                refresh_seconds=cls.SURGE_FRESH_SECONDS,
                fetch=source.fetch_surge,
                freshness_key=f"{source_name}:surge",
            )
        except Exception:
            if source_name == "tdxaidata":
                raise
            logger.exception("market.surge refresh failed, serving empty payload")
            await market_cache.set_json(
                key,
                {"date": trade_day, "fetchedAtTs": time.time(), "items": []},
                ttl=cls.EMPTY_MARK_TTL_SECONDS,
            )

    @classmethod
    async def get_pool(cls, kind: str, date: str | None = None) -> dict[str, Any]:
        if kind not in cls.POOL_KINDS:
            raise ValueError(f"unknown pool kind: {kind}")

        latest = await cls.latest_trading_day()
        day = cls._normalize_day(date) or latest
        source_name, source = MarketDataSourceFactory.resolve("pools")
        if day == latest:
            await cls._ensure_pool_fresh(kind, source_name, source)
        else:
            await cls._ensure_pool_backfill(kind, day, source_name, source)

        key = market_cache.source_key("pools", source_name, market_cache.pool_key(kind, day))
        payload = await market_cache.get_json(key) or {}
        return {
            "date": str(payload.get("date") or day),
            "items": payload.get("items") or [],
        }

    @classmethod
    async def get_pools_batch(cls, dates: list[str], kinds: list[str] | None = None) -> dict[str, Any]:
        safe_kinds = kinds or list(cls.POOL_KINDS)
        unknown = [kind for kind in safe_kinds if kind not in cls.POOL_KINDS]
        if unknown:
            raise ValueError(f"unknown pool kind: {unknown[0]}")

        normalized_dates: list[str] = []
        seen_dates: set[str] = set()
        for raw in dates:
            day = cls._normalize_day(raw)
            if len(day) != 8 or day in seen_dates:
                continue
            seen_dates.add(day)
            normalized_dates.append(day)

        rows = await asyncio.gather(
            *(
                cls.get_pool(kind, day)
                for day in normalized_dates
                for kind in safe_kinds
            )
        )

        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
            kind: {}
            for kind in cls.POOL_KINDS
        }
        for index, row in enumerate(rows):
            day = normalized_dates[index // len(safe_kinds)]
            kind = safe_kinds[index % len(safe_kinds)]
            grouped[kind][day] = row.get("items") or []

        return {
            "ztByDate": grouped["zt"],
            "zbByDate": grouped["zb"],
            "dtByDate": grouped["dt"],
        }

    @classmethod
    async def get_universe(cls) -> dict[str, Any]:
        source_name, source = MarketDataSourceFactory.resolve("universe")
        await cls._ensure_universe_fresh(source_name, source)
        trade_day = await cls._cache_trade_day()
        key = market_cache.source_key("universe", source_name, market_cache.universe_key_for_day(trade_day))
        payload = await market_cache.get_json(key) or {}
        return {
            "date": payload.get("date") or trade_day,
            "items": payload.get("items") or [],
        }

    @classmethod
    async def get_surge(cls) -> dict[str, Any]:
        source_name, source = MarketDataSourceFactory.resolve("surge")
        await cls._ensure_surge_fresh(source_name, source)
        trade_day = await cls._cache_trade_day()
        key = market_cache.source_key("surge", source_name, market_cache.surge_key_for_day(trade_day))
        payload = await market_cache.get_json(key) or {}
        return {
            "date": payload.get("date") or trade_day,
            "items": payload.get("items") or [],
        }

    @classmethod
    async def get_latest_context(cls) -> dict[str, Any]:
        latest_day = await cls.latest_trading_day()
        zt_result, zb_result, dt_result, surge_result, universe_result = await asyncio.gather(
            cls.get_pool("zt", latest_day),
            cls.get_pool("zb", latest_day),
            cls.get_pool("dt", latest_day),
            cls.get_surge(),
            cls.get_universe(),
        )
        latest_zt = zt_result.get("items") or []
        concept_index: dict[str, list[str]] = {}
        for item in latest_zt:
            code = str(item.get("code") or "").strip()
            concepts = item.get("concepts") or []
            if code and isinstance(concepts, list) and concepts:
                concept_index[code] = list(dict.fromkeys(str(name).strip() for name in concepts if str(name).strip()))

        return {
            "latestDay": latest_day,
            "pools": {
                "ztByDate": {latest_day: latest_zt},
                "zbByDate": {latest_day: zb_result.get("items") or []},
                "dtByDate": {latest_day: dt_result.get("items") or []},
            },
            "latestZt": latest_zt,
            "latestZb": zb_result.get("items") or [],
            "latestDt": dt_result.get("items") or [],
            "surge": surge_result.get("items") or [],
            "conceptIndex": concept_index,
            "baseUniverse": universe_result.get("items") or [],
            "trendUniverse": universe_result.get("items") or [],
        }

    @staticmethod
    def _clean_csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _normalize_trending_items(items: Any) -> list[dict[str, Any]]:
        rows = items if isinstance(items, list) else []
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            plate_id = item.get("plateId")
            normalized.append(
                {
                    **item,
                    "plateId": str(plate_id) if plate_id is not None else None,
                }
            )
        return normalized

    @classmethod
    async def _cached(
        cls,
        cache_key: str,
        ttl_seconds: int,
        fetch,
        label: str,
        jitter: bool = False,
    ) -> Any:
        started_at = time.perf_counter()
        hit = await market_cache.get_json(cache_key)
        if hit is not None:
            logger.info(
                "market.cache hit label=%s key=%s elapsed_ms=%.2f",
                label,
                cache_key,
                (time.perf_counter() - started_at) * 1000,
            )
            return hit
        payload = await market_cache.cached_call(
            cache_key,
            cls._ttl_with_jitter(ttl_seconds, cache_key, enabled=jitter),
            fetch,
        )
        logger.info(
            "market.cache refresh label=%s key=%s elapsed_ms=%.2f",
            label,
            cache_key,
            (time.perf_counter() - started_at) * 1000,
        )
        return payload

    @classmethod
    async def get_quotes(cls, symbols: str) -> dict[str, Any]:
        codes = cls._clean_csv(symbols)
        if not codes:
            return {"items": {}}
        source_name, source = MarketDataSourceFactory.resolve("quotes")
        trade_day = await cls._cache_trade_day()
        cache_key = market_cache.source_key("quotes", source_name, market_cache.quotes_key(codes, trade_day))
        items = await cls._cached(
            cache_key,
            cls.QUOTES_TTL_SECONDS,
            lambda: source.fetch_quotes(codes),
            "quotes",
            jitter=True,
        )
        return {"items": items}

    @classmethod
    async def get_fundflow(cls, codes: str, days: int) -> dict[str, Any]:
        code_list = cls._clean_csv(codes)
        if not code_list:
            return {"items": {}}
        safe_days = max(1, min(int(days), 10))
        source_name, source = MarketDataSourceFactory.resolve("fundflow")
        trade_day = await cls._cache_trade_day()
        cache_key = market_cache.source_key(
            "fundflow", source_name, market_cache.fundflow_key(code_list, safe_days, trade_day)
        )
        items = await cls._get_trade_day_items(
            cache_key=cache_key,
            trade_day=trade_day,
            label="fundflow",
            refresh_seconds=cls.FUNDFLOW_INTRADAY_TTL_SECONDS,
            fetch=lambda: source.fetch_fundflow(code_list, safe_days),
            freshness_key=f"{source_name}:fundflow:{safe_days}",
        )
        return {"items": items}

    @classmethod
    async def get_trending(cls) -> dict[str, Any]:
        source_name, source = MarketDataSourceFactory.resolve("trending")
        trade_day = await cls._cache_trade_day()
        cache_key = market_cache.source_key("trending", source_name, market_cache.trending_key(trade_day))
        items = await cls._get_trade_day_items(
            cache_key=cache_key,
            trade_day=trade_day,
            label="trending",
            refresh_seconds=cls.TRENDING_TTL_SECONDS,
            fetch=source.fetch_trending,
            freshness_key=f"{source_name}:trending",
        )
        return {"items": cls._normalize_trending_items(items)}

    @classmethod
    async def get_plate_members(cls, plate_id: str) -> dict[str, Any]:
        source_name, source = MarketDataSourceFactory.resolve("members")
        trade_day = await cls._cache_trade_day()
        cache_key = market_cache.source_key("members", source_name, market_cache.members_key(plate_id, trade_day))
        items = await cls._get_trade_day_items(
            cache_key=cache_key,
            trade_day=trade_day,
            label="members",
            refresh_seconds=cls.MEMBERS_INTRADAY_TTL_SECONDS,
            fetch=lambda: source.fetch_members(plate_id),
            freshness_key=f"{source_name}:members:{plate_id}",
        )
        return {"items": items}

    @classmethod
    async def get_plate_index(cls, plate_id: str, count: int) -> dict[str, Any]:
        safe_count = max(1, min(int(count), 60))
        source_name, source = MarketDataSourceFactory.resolve("plate_index")
        trade_day = await cls._cache_trade_day()
        cache_key = market_cache.source_key(
            "plate_index", source_name, market_cache.plate_index_key(plate_id, safe_count, trade_day)
        )
        items = await cls._get_trade_day_items(
            cache_key=cache_key,
            trade_day=trade_day,
            label="plate_index",
            refresh_seconds=cls.PLATE_INDEX_INTRADAY_TTL_SECONDS,
            fetch=lambda: source.fetch_plate_index(plate_id, safe_count),
            freshness_key=f"{source_name}:plate_index:{plate_id}:{safe_count}",
        )
        return {"items": items}

    @classmethod
    async def get_payoff(cls, kind: str, date: str | None = None) -> dict[str, Any]:
        dataset = {
            "strong": "payoff_strong",
            "hot": "payoff_hot",
            "bigface": "payoff_drawdown",
            "drawdown": "payoff_drawdown",
        }.get(kind)
        if dataset is None:
            raise ValueError(f"unknown payoff kind: {kind}")
        source_name, source = MarketDataSourceFactory.resolve(dataset)
        if source_name == 'tdxaidata' and kind == 'hot':
            # Reject disabled scans before even reading calendar or cached ranking data.
            await source.fetch_payoff('hot', date)
        latest = await cls._cache_trade_day()
        normalized_date = cls._normalize_day(date) or latest
        cache_key = market_cache.source_key(dataset, source_name, market_cache.payoff_key(kind, normalized_date))
        if normalized_date != latest:
            async def fetch_history_payload() -> dict[str, Any]:
                items = await source.fetch_payoff(kind, normalized_date)
                return {"date": normalized_date, "fetchedAtTs": time.time(), "items": items or []}

            payload = await cls._cached(
                cache_key,
                cls.PAYOFF_DRAWDOWN_HISTORY_TTL_SECONDS,
                fetch_history_payload,
                f"payoff:{kind}",
            )
            items = cls._trade_day_items_from_payload(payload)
        else:
            items = await cls._get_trade_day_items(
                cache_key=cache_key,
                trade_day=latest,
                label=f"payoff:{kind}",
                refresh_seconds=cls.PAYOFF_SHORT_TTL_SECONDS,
                fetch=lambda: source.fetch_payoff(kind, normalized_date),
                freshness_key=f"{source_name}:payoff:{kind}",
            )
        return {"items": items}

    @classmethod
    async def get_turnover(cls) -> dict[str, Any]:
        source_name, source = MarketDataSourceFactory.resolve("turnover")
        trade_day = await cls._cache_trade_day()
        return await cls._cached(
            market_cache.source_key("turnover", source_name, market_cache.turnover_key(trade_day)),
            cls.TURNOVER_TTL_SECONDS,
            source.fetch_turnover,
            "turnover",
            jitter=True,
        )

    @classmethod
    async def get_strategy(cls) -> dict[str, Any]:
        return await MarketStrategyService.get_strategy()

    @classmethod
    async def set_strategy(cls, private_section: dict[str, Any], version: str | None = None) -> dict[str, Any]:
        return await MarketStrategyService.set_strategy(private_section, version)
