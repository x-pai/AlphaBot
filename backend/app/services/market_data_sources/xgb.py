"""xgb source: pools/universe/surge/members/quotes/index + fundflow + trending."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import settings
from app.services.market_data_sources.base import MarketDataSourceBase, get_with_retry, http_client, normalize_code, num

FLASH_BASE = settings.XGB_FLASH_API_BASE.rstrip("/")
DDC_BASE = settings.XGB_DDC_MARKET_API_BASE.rstrip("/")
TREND_BASE = settings.XGB_TREND_API_BASE.rstrip("/")
XGB_REFERER = settings.XGB_REFERER.strip()

UNIVERSE_FIELDS = "plate_id,plate_name,core_avg_pcp,fund_flow,rise_count,fall_count,stay_count,limit_up_count"
MEMBER_FIELDS = "symbol,stock_chi_name,price,change_percent,turnover_ratio,turnover_value,fund_flow"
QUOTE_FIELDS = "symbol,stock_chi_name,price,change_percent"
FUNDFLOW_FIELD_NAMES = [
    "prod_code", "date", "main_in", "main_out", "retail_in", "retail_out", "net_inflow",
    "super_big_in", "super_big_out", "net_super", "big_in", "big_out", "net_big",
    "medium_in", "medium_out", "net_medium", "small_in", "small_out", "net_small", "timestamp",
]
POOL_NAMES = {"zt": "limit_up", "zb": "limit_up_broken", "dt": "limit_down"}


def chunk(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _required_base_url(value: str, env_name: str) -> str:
    if value:
        return value
    raise RuntimeError(f"{env_name} is not configured")


def _code_to_symbol(code: str) -> str | None:
    """6 位代码 → xgb symbol；北交所等沿用旧口径跳过。"""
    code = normalize_code(code)
    if not code:
        return None
    if code.startswith("6"):
        return f"{code}.SS"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    return None


def datetime_from_ts(ts: int) -> str:
    from datetime import datetime, timezone, timedelta
    cst = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts, cst).strftime("%Y%m%d")


class XgbMarketDataSource(MarketDataSourceBase):
    SUPPORTED_DATASETS = frozenset({
        "pools", "universe", "surge", "quotes", "fundflow", "trending", "members",
        "plate_index", "payoff_strong",
    })

    async def _flash(self, path: str, params: dict[str, Any]) -> Any:
        resp = await get_with_retry(
            f"{_required_base_url(FLASH_BASE, 'XGB_FLASH_API_BASE')}{path}",
            {k: v for k, v in params.items() if v not in (None, "")},
        )
        envelope = resp.json()
        if envelope.get("code") != 20000:
            raise RuntimeError(f"flash {path} code={envelope.get('code')}")
        return envelope.get("data")

    # ── 池子（zt/zb/dt）→ TopicStock 领域对象 ──
    async def fetch_pool(self, kind: str, date_hyphen: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"pool_name": POOL_NAMES[kind]}
        if date_hyphen:
            params["date"] = date_hyphen
        data = await self._flash("/pool/detail", params)
        items = data if isinstance(data, list) else []
        out: list[dict[str, Any]] = []
        for item in items:
            code = normalize_code(str(item.get("symbol") or ""))
            if not code:
                continue
            plates = [
                (p.get("plate_name") or "").strip()
                for p in (item.get("surge_reason") or {}).get("related_plates") or []
            ]
            plates = [p for p in plates if p]
            ratio = num(item.get("buy_lock_volume_ratio"))
            capital = num(item.get("non_restricted_capital") or item.get("total_capital"))
            out.append({
                "name": item.get("stock_chi_name") or "",
                "code": code,
                "reason": plates[0] if plates else "其他",
                "concepts": plates or None,
                "lbc": int(num(item.get("limit_up_days")) or 1) if kind == "zt" else 0,
                "time": int(((num(item.get("first_limit_up")) + 8 * 3600) % 86400) // 60) if item.get("first_limit_up") else 565,
                "type": kind,
                "fund": round(ratio * capital),
                "price": num(item.get("price")),
                "turnoverRate": num(item.get("turnover_ratio")) * 100,
                "zbc": int(num(item.get("break_limit_up_times"))),
                "firstBreak": int(item["first_break_limit_up"]) if item.get("first_break_limit_up") else None,
                "lastSealTs": int(item["last_limit_up"]) if item.get("last_limit_up") else None,
            })
        return out

    # ── 板块宇宙 → PlateFlow 领域对象 ──
    async def fetch_universe(self) -> list[dict[str, Any]]:
        ids = await self._flash("/plate/rank", {"field": "core_avg_pcp", "type": 0})
        id_list = ids if isinstance(ids, list) else []
        merged: list[dict[str, Any]] = []

        async def fetch_chunk(part: list[Any]) -> None:
            data = await self._flash(
                "/plate/data",
                {"fields": UNIVERSE_FIELDS, "plates": ",".join(str(i) for i in part)},
            )
            for item in (data or {}).values():
                if not isinstance(item, dict) or item.get("plate_id") is None or not item.get("plate_name"):
                    continue
                merged.append({
                    "code": str(item["plate_id"]),
                    "name": item.get("plate_name"),
                    "change": num(item.get("core_avg_pcp")) * 100,
                    "netFlow": num(item.get("fund_flow")) / 1e8,
                    "ztCount": int(num(item.get("limit_up_count"))),
                    "upCount": int(num(item.get("rise_count"))),
                    "downCount": int(num(item.get("fall_count"))),
                    "flatCount": int(num(item.get("stay_count"))),
                })

        chunks = chunk(id_list, 300)
        if chunks:
            await asyncio.gather(*(fetch_chunk(c) for c in chunks))
        return merged

    # ── 异动池 → SurgeLimitStock 领域对象 ──
    async def fetch_surge(self) -> list[dict[str, Any]]:
        data = await self._flash("/surge_stock/stocks", {"normal": "true", "uplimit": "true"})
        items = (data or {}).get("items") if isinstance(data, dict) else None
        items = items if isinstance(items, list) else []
        out: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, list) or len(item) < 2:
                continue
            code = normalize_code(str(item[0] or ""))
            if not code:
                continue
            plates = []
            if len(item) > 8 and isinstance(item[8], list):
                plates = [str(p.get("name") or "") for p in item[8] if isinstance(p, dict) and p.get("name")]
            out.append({
                "code": code,
                "name": str(item[1] or ""),
                "plates": plates,
                "analysis": (str(item[5]).strip() if len(item) > 5 and item[5] else None),
            })
        return out

    # ── 批量行情 → Quote 领域对象（按 6 位代码键控）──
    async def fetch_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        normalized = [normalize_code(c) for c in symbols]
        xgb_symbols = list({s for c in normalized if (s := _code_to_symbol(c or ""))})
        if not xgb_symbols:
            return {}
        merged = await self.fetch_quotes_raw(xgb_symbols)
        out: dict[str, dict[str, Any]] = {}
        for code in normalized:
            datum = merged.get(_code_to_symbol(code) or "")
            if datum:
                out[code] = {
                    "name": datum.get("stock_chi_name") or "",
                    "price": datum.get("price") if isinstance(datum.get("price"), (int, float)) else None,
                    "change": num(datum.get("change_percent")) * 100,
                }
        return out

    async def _fetch_quotes_chunk(self, part: list[str], merged: dict[str, dict[str, Any]], fields: str = QUOTE_FIELDS) -> None:
        data = await self._flash(
            "/stock/data",
            {"symbols": ",".join(part), "fields": fields, "strict": "true"},
        )
        merged.update({k: v for k, v in (data or {}).items() if isinstance(v, dict)})

    # ── 个股资金流（ddc）→ 按代码键控的逐日行 ──
    async def fetch_fundflow(self, codes: list[str], days: int) -> dict[str, list[dict[str, Any]]]:
        symbols = [s for c in codes if (s := _code_to_symbol(c))]
        result: dict[str, list[dict[str, Any]]] = {}

        async def fetch_chunk(part: list[str]) -> None:
            resp = await http_client().get(
                f"{_required_base_url(DDC_BASE, 'XGB_DDC_MARKET_API_BASE')}/fundflow/batch",
                params={"prod_codes": ",".join(part), "day_count": min(days, 10)},
            )
            resp.raise_for_status()
            data = (resp.json() or {}).get("data") or {}
            fields = data.get("fields") if isinstance(data.get("fields"), list) and data["fields"] else FUNDFLOW_FIELD_NAMES
            for key, value in data.items():
                if key == "fields" or not isinstance(value, dict):
                    continue
                rows = value.get("fund_flow") if isinstance(value, dict) else None
                if not isinstance(rows, list):
                    continue
                mapped: list[dict[str, Any]] = []
                for row in rows:
                    if not isinstance(row, list):
                        continue
                    cell = dict(zip(fields, row))
                    if not cell.get("date"):
                        continue
                    mapped.append({
                        "prodCode": cell.get("prod_code") or key,
                        "date": cell.get("date"),
                        "mainIn": num(cell.get("main_in")), "mainOut": num(cell.get("main_out")),
                        "netInflow": num(cell.get("net_inflow")),
                        "superIn": num(cell.get("super_big_in")), "superOut": num(cell.get("super_big_out")),
                        "netSuper": num(cell.get("net_super")),
                        "bigIn": num(cell.get("big_in")), "bigOut": num(cell.get("big_out")),
                        "netBig": num(cell.get("net_big")),
                        "mediumIn": num(cell.get("medium_in")), "mediumOut": num(cell.get("medium_out")),
                        "netMedium": num(cell.get("net_medium")),
                        "smallIn": num(cell.get("small_in")), "smallOut": num(cell.get("small_out")),
                        "netSmall": num(cell.get("net_small")),
                    })
                result[key] = mapped

        chunks = chunk(symbols, 300)
        if chunks:
            await asyncio.gather(*(fetch_chunk(c) for c in chunks))
        return result

    # ── 趋势板块推荐（baoer）──
    async def fetch_trending(self) -> list[dict[str, Any]]:
        resp = await http_client().get(
            f"{_required_base_url(TREND_BASE, 'XGB_TREND_API_BASE')}/v2/tab/recommend",
            params={"module": "trending_plates"},
            headers={"Referer": XGB_REFERER} if XGB_REFERER else None,
        )
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        items = data.get("items") if isinstance(data, dict) else None
        items = items if isinstance(items, list) else []
        return [
            {
                "plateId": str(item.get("plate_id")) if item.get("plate_id") is not None else None,
                "name": item.get("plate_name"),
                "description": (item.get("description") or "").strip() or None,
                "stocks": item.get("stocks") or [],
            }
            for item in items
            if isinstance(item, dict) and item.get("plate_name")
        ]

    # ── 板块成员：成分集合 + 批量行情合成 ──
    async def fetch_members(self, plate_id: str) -> list[dict[str, Any]]:
        set_data = await self._flash("/plate/plate_set", {"id": plate_id})
        stocks = (set_data or {}).get("stocks") if isinstance(set_data, dict) else None
        symbols = [s.get("symbol") for s in (stocks or []) if isinstance(s, dict) and s.get("symbol")]
        if not symbols:
            return []
        quotes = await self.fetch_quotes_raw(symbols, MEMBER_FIELDS)
        members: list[dict[str, Any]] = []
        for symbol in symbols:
            datum = quotes.get(symbol)
            if not datum:
                continue
            code = normalize_code(symbol)
            if not code:
                continue
            members.append({
                "code": code,
                "name": datum.get("stock_chi_name") or "",
                "price": num(datum.get("price")),
                "change": num(datum.get("change_percent")) * 100,
                "amount": num(datum.get("turnover_value")) / 1e8,
                "netFlow": num(datum.get("fund_flow")) / 1e8,
                "turnoverRate": num(datum.get("turnover_ratio")) * 100,
            })
        return members

    async def fetch_quotes_raw(self, symbols: list[str], fields: str = QUOTE_FIELDS) -> dict[str, dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        await asyncio.gather(*(
            self._fetch_quotes_chunk(part, merged, fields) for part in chunk(symbols, 100)
        ))
        return merged

    # ── 板块指数日线 → OHLC 领域对象 ──
    async def fetch_plate_index(self, plate_id: str, count: int) -> list[dict[str, Any]]:
        data = await self._flash(
            "/plate/index_history",
            {"plate_id": plate_id, "index_type": 1, "data_count": count},
        )
        items = data if isinstance(data, list) else []
        out: list[dict[str, Any]] = []
        for bar in items:
            if not isinstance(bar, dict) or not isinstance(bar.get("date_time"), (int, float)):
                continue
            ts = int(bar["date_time"])
            out.append({
                "date": datetime_from_ts(ts),
                "open": num(bar.get("open")), "close": num(bar.get("close")),
                "high": num(bar.get("high")), "low": num(bar.get("low")),
            })
        return out

    # ── 强势股池 → 强势名单领域对象 ──
    async def fetch_payoff(self, kind: str, date_hyphen: str | None = None) -> list[dict[str, Any]]:
        if kind != "strong":
            raise ValueError(f"xgb provider unsupported payoff kind: {kind}")
        data = await self._flash("/pool/detail", {"pool_name": "super_stock"})
        items = data if isinstance(data, list) else []
        out: list[dict[str, Any]] = []
        for item in items:
            name = item.get("stock_chi_name") or ""
            if not name or "ST" in name:
                continue
            related = (item.get("surge_reason") or {}).get("related_plates") or []
            out.append({
                "name": name,
                "change": round(num(item.get("change_percent")) * 100, 2),
                "plate": (related[0].get("plate_name") or "").strip() if related else "",
                "days": int(num(item.get("m_days_n_boards_days"))),
                "boards": int(num(item.get("m_days_n_boards_boards"))),
            })
        return out
