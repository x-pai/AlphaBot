from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Awaitable, Callable

import httpx


class MarketEmotionService:
    BASE_URL = "http://hot.icfqs.com:7615"
    TIMEOUT = 10.0
    INTRADAY_TTL = 15.0
    SHORT_TTL = 120.0
    _cache: dict[str, tuple[float, dict[str, Any]]] = {}
    _inflight: dict[str, asyncio.Task[dict[str, Any]]] = {}
    _cache_lock = asyncio.Lock()

    @classmethod
    async def _call_tqlex(cls, entry: str, payload: Any) -> dict[str, Any]:
        url = f"{cls.BASE_URL}/TQLEX?Entry={entry}&RI="
        async with httpx.AsyncClient(timeout=cls.TIMEOUT) as client:
            response = await client.post(
                url,
                content=json.dumps(payload, ensure_ascii=False),
                headers={"Content-Type": "text/plain"},
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _rows(result: dict[str, Any], index: int) -> list[dict[str, Any]]:
        result_sets = result.get("ResultSets") or []
        if index >= len(result_sets):
            return []
        cols = [
            item.get("Name") if isinstance(item, dict) else item
            for item in (result_sets[index].get("ColDes") or [])
        ]
        return [
            {
                str(cols[col_index] or f"col_{col_index}"): value
                for col_index, value in enumerate(row or [])
            }
            for row in (result_sets[index].get("Content") or [])
        ]

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value in (None, "", "null", "-"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value in (None, "", "null", "-"):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_minute(value: str) -> str:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        if len(digits) < 4:
            return ""
        digits = digits.zfill(6)
        return f"{digits[:2]}:{digits[2:4]}"

    @staticmethod
    def _emotion_zone(value: float | None) -> str:
        if value is None:
            return "--"
        if value >= 1:
            return "活跃"
        if value >= -2:
            return "震荡"
        if value >= -4:
            return "低迷"
        return "冰点"

    @staticmethod
    def _trading_minute(index: int) -> str:
        if index < 120:
            total = 9 * 60 + 30 + index
        else:
            total = 13 * 60 + (index - 120)
        hour = total // 60
        minute = total % 60
        return f"{hour:02d}:{minute:02d}"

    @classmethod
    async def _remember(
        cls,
        key: str,
        ttl_seconds: float,
        loader: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        now = asyncio.get_running_loop().time()
        async with cls._cache_lock:
            cached = cls._cache.get(key)
            if cached and cached[0] > now:
                return cached[1]
            inflight = cls._inflight.get(key)
            if inflight is None:
                inflight = asyncio.create_task(loader())
                cls._inflight[key] = inflight

        try:
            data = await inflight
        except Exception:
            async with cls._cache_lock:
                if cls._inflight.get(key) is inflight:
                    cls._inflight.pop(key, None)
            raise

        async with cls._cache_lock:
            cls._cache[key] = (asyncio.get_running_loop().time() + ttl_seconds, data)
            if cls._inflight.get(key) is inflight:
                cls._inflight.pop(key, None)
        return data

    @classmethod
    async def _load_intraday_emotion(cls) -> dict[str, Any]:
        result = await cls._call_tqlex(
            "HQServ.hq_nlp_dxqx",
            [{"ReqId": "200260", "modname": "mod_dxqx.dll"}],
        )
        rows = cls._rows(result, 0)
        points = [
            {
                "time": cls._format_minute(row.get("time", "")),
                "positive": cls._as_float(row.get("newhigh")),
                "negative": cls._as_float(row.get("newlow")),
                "index": cls._as_float(row.get("sh")),
            }
            for row in rows
        ]
        points = [point for point in points if point["time"]]
        last = points[-1] if points else {}
        return {
            "positive_current": last.get("positive"),
            "negative_current": last.get("negative"),
            "index_current": last.get("index"),
            "points": points,
        }

    @classmethod
    async def get_intraday_emotion(cls) -> dict[str, Any]:
        from app.core.config import settings
        if settings.DEFAULT_MARKET_DATA_SOURCE.strip().lower() == "tdxaidata":
            return {"positive_current": None, "negative_current": None, "index_current": None,
                    "points": [], "unavailableReason": "通达信 SDK 未提供原分时情绪指标"}
        return await cls._remember("intraday", cls.INTRADAY_TTL, cls._load_intraday_emotion)

    @classmethod
    async def _load_short_emotion(cls, trade_days: int = 5) -> dict[str, Any]:
        safe_days = max(1, min(int(trade_days or 5), 20))
        end_date = datetime.now().strftime("%Y%m%d")
        page_size = 5
        page = 0
        total = safe_days
        rows: list[dict[str, Any]] = []

        while len(rows) < total:
            result = await cls._call_tqlex(
                "HQServ.hq_nlp_dxqx",
                [
                    {
                        "ReqId": "200200",
                        "Code": "DXQX_AG",
                        "IndexCode": "",
                        "BeginDate": "",
                        "EndDate": end_date,
                        "TradeDays": str(safe_days),
                        "Page": str(page),
                        "PageSize": str(page_size),
                        "modname": "mod_dxqx.dll",
                    }
                ],
            )
            page_rows = cls._rows(result, 1)
            if page == 0:
                meta_rows = cls._rows(result, 0)
                total = min(
                    safe_days,
                    cls._as_int((meta_rows[0] if meta_rows else {}).get("toatlnum")) or safe_days,
                )
            if not page_rows:
                break
            rows.extend(page_rows)
            if len(page_rows) < page_size:
                break
            page += 1

        rows = rows[:safe_days]
        days: list[dict[str, Any]] = []
        latest_value: float | None = None
        latest_turnover: float | None = None

        for row in rows:
            preclose = cls._as_float(row.get("preclsoe")) or 0
            amount_scale = cls._as_float(row.get("amo_fac")) or 1
            raw_values = str(row.get("min") or "").split(",")
            raw_amounts = str(row.get("amount") or "").split(",")
            points = []
            for idx, value in enumerate(raw_values):
                if value in ("", "null"):
                    continue
                minute_value = cls._as_float(value)
                if minute_value is None or preclose == 0:
                    continue
                turnover = cls._as_float(raw_amounts[idx]) if idx < len(raw_amounts) else None
                points.append(
                    {
                        "time": cls._trading_minute(idx),
                        "value": round((minute_value / preclose) * 100, 2),
                        "turnover": None if turnover is None else round(turnover * amount_scale, 2),
                    }
                )
            if not points:
                continue
            latest_value = points[-1]["value"]
            latest_turnover = points[-1]["turnover"]
            days.append(
                {
                    "date": str(row.get("date") or ""),
                    "points": points,
                }
            )

        return {
            "days": days,
            "latest_value": latest_value,
            "latest_turnover": latest_turnover,
            "zone": cls._emotion_zone(latest_value),
        }

    @classmethod
    async def get_short_emotion(cls, trade_days: int = 5) -> dict[str, Any]:
        from app.core.config import settings
        if settings.DEFAULT_MARKET_DATA_SOURCE.strip().lower() == "tdxaidata":
            return {"days": [], "latest_value": None, "latest_turnover": None, "zone": "--",
                    "unavailableReason": "通达信 SDK 未提供原短线情绪指数"}
        safe_days = max(1, min(int(trade_days or 5), 20))
        return await cls._remember(
            f"short:{safe_days}",
            cls.SHORT_TTL,
            lambda: cls._load_short_emotion(safe_days),
        )
