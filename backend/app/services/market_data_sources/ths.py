"""同花顺实现：成交额分钟数据 + 热榜 + 大面（曾涨停最大回撤）。"""

from __future__ import annotations

from typing import Any

from app.services.market_data_sources.base import MarketDataSourceBase, http_client, num

DQ_BASE = "https://dq.10jqka.com.cn/fuyao"
DATA_BASE = "https://data.10jqka.com.cn"


def _ths_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status_code") != 0:
        raise RuntimeError(f"ths status_code={payload.get('status_code')}")
    return payload.get("data") or {}


class ThsMarketDataSource(MarketDataSourceBase):
    SUPPORTED_DATASETS = frozenset({"turnover", "payoff_hot", "payoff_drawdown"})

    async def fetch_turnover(self) -> dict[str, Any]:
        resp = await http_client().get(
            f"{DQ_BASE}/market_analysis_api/chart/v1/get_chart_data",
            params={"chart_key": "turnover_minute"},
        )
        resp.raise_for_status()
        envelope = resp.json()
        if envelope.get("status_code") != 0:
            raise RuntimeError(f"ths turnover status_code={envelope.get('status_code')}")
        data = envelope.get("data") or {}
        charts = data.get("charts") or data
        point_list = charts.get("point_list") or []
        labels = charts.get("x_label_list") or []
        predict = 0.0
        for header in charts.get("header") or []:
            if header.get("key") == "predict_turnover":
                predict = num(header.get("val"))
        points = [
            {"time": labels[index] or "", "today": num(p[1]) if len(p) > 1 and p[1] is not None else None,
             "yesterday": num(p[2]) if len(p) > 2 and p[2] is not None else None}
            for index, p in enumerate(point_list)
            if isinstance(p, list) and len(p) > 1 and p[1] is not None
        ]
        current = points[-1]["today"] if points else None
        previous = points[-1]["yesterday"] if points else None
        change = current - previous if (current is not None and previous is not None) else None
        return {
            "current": current, "predict": predict, "previous": previous, "change": change,
            "points": [{"time": p["time"], "today": p["today"], "yesterday": p["yesterday"]} for p in points],
        }

    async def fetch_payoff(self, kind: str, date_hyphen: str | None = None) -> list[dict[str, Any]]:
        if kind == "hot":
            resp = await http_client().get(
                f"{DQ_BASE}/hot_list_data/out/hot_list/v1/stock",
                params={"stock_type": "a", "type": "hour", "list_type": "normal"},
            )
            resp.raise_for_status()
            envelope = resp.json()
            if envelope.get("status_code") != 0:
                raise RuntimeError(f"ths hot status_code={envelope.get('status_code')}")
            stock_list = (envelope.get("data") or {}).get("stock_list") or []
            out: list[dict[str, Any]] = []
            for item in stock_list:
                rate = num(item.get("rate")) / 10000
                tag = ""
                tag_info = item.get("tag") or {}
                tag = tag_info.get("popularity_tag") or (tag_info.get("concept_tag") or [""])[0] or item.get("analyse_title") or ""
                out.append({
                    "name": item.get("name") or "",
                    "change": num(item.get("rise_and_fall")),
                    "heat": round(rate, 1),
                    "tag": tag,
                })
            return out
        if kind == "drawdown":
            params: dict[str, Any] = {
                "cate": "limit_up", "sort_field": "max_drawdown", "sort_dir": "asc", "page": 1, "size": 200,
            }
            if date_hyphen:
                params["date"] = date_hyphen
            resp = await http_client().get(
                f"{DATA_BASE}/mobileapi/hotspot_focus/stock_pool/v1/get_drawdown_stocks", params=params
            )
            resp.raise_for_status()
            envelope = resp.json()
            stock_list = ((envelope.get("data") or {}).get("stock_list")) or []
            return [
                {
                    "name": item.get("stock_name") or "",
                    "change": num(item.get("change")),
                    "maxDrawdown": round(num(item.get("max_drawdown")), 2),
                    "industryBlock": item.get("industry_block") or "",
                }
                for item in stock_list
                if not item.get("is_st")
            ]
        raise ValueError(f"ths provider unsupported payoff kind: {kind}")
