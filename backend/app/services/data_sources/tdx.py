import httpx
import pandas as pd
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.stock import StockInfo, StockPriceHistory
from app.services.data_sources.akshare import AKShareDataSource
from app.services.data_sources.base import DataSourceBase


class TDXDataSource(DataSourceBase):
    """TDX 数据源实现，缺失能力由 AKShare 补全。"""

    def __init__(self):
        self.base_url = settings.TDX_API_BASE_URL.rstrip("/")
        if not self.base_url:
            raise ValueError("数据源 tdx 未配置 TDX_API_BASE_URL")
        self.timeout = settings.TDX_TIMEOUT
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.fallback = AKShareDataSource()

    async def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        response = await self.client.get(f"{self.base_url}{path}", params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise ValueError(payload.get("message", "TDX request failed"))
        return payload.get("data")

    def _infer_exchange(self, code: str) -> str:
        if code.startswith(("5", "6", "9")):
            return "上海证券交易所"
        if code.startswith(("4", "8")):
            return "北京证券交易所"
        return "深圳证券交易所"

    def _to_symbol(self, code: str) -> str:
        if code.startswith(("5", "6", "9")):
            return f"{code}.SH"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
        return f"{code}.SZ"

    def _to_code(self, symbol: str) -> str:
        return symbol.split(".")[0].strip().upper()

    def _range_to_limit(self, interval: str, range_value: str) -> int:
        mapping = {
            "daily": {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "5y": 1250},
            "weekly": {"1m": 8, "3m": 16, "6m": 32, "1y": 64, "5y": 320},
            "monthly": {"1m": 3, "3m": 4, "6m": 7, "1y": 13, "5y": 61},
        }
        return mapping.get(interval, mapping["daily"]).get(range_value, 365)

    def _interval_to_tdx_type(self, interval: str) -> str:
        return {
            "daily": "day",
            "weekly": "week",
            "monthly": "month",
        }.get(interval, "day")

    def _normalize_kline_df(self, rows: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
        if not rows:
            return None

        df = pd.DataFrame(rows)
        if df.empty or "Time" not in df.columns:
            return None

        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df = df.dropna(subset=["Time"]).sort_values("Time")
        if df.empty:
            return None

        df = df.set_index("Time")
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Amount": "amount",
            "Last": "last",
        })

        numeric_columns = ["open", "high", "low", "close", "volume"]
        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        price_columns = ["open", "high", "low", "close"]
        for column in price_columns:
            if column in df.columns:
                df[column] = df[column] / 1000.0

        if "volume" in df.columns:
            df["volume"] = df["volume"] * 100

        return df[["open", "high", "low", "close", "volume"]].dropna()

    async def _search_etfs(self, query: str) -> List[StockInfo]:
        try:
            data = await self._request("/api/etf")
            etfs = (data or {}).get("list", []) if isinstance(data, dict) else []
            query_text = (query or "").strip().lower()
            results: List[StockInfo] = []

            for item in etfs:
                code = str(item.get("code", "")).strip()
                name = str(item.get("name", "")).strip()
                if not code:
                    continue
                if query_text and query_text not in code.lower() and query_text not in name.lower():
                    continue

                exchange_code = str(item.get("exchange", "")).strip().lower()
                if exchange_code == "sh":
                    symbol = f"{code}.SH"
                    exchange = "上海证券交易所"
                elif exchange_code == "sz":
                    symbol = f"{code}.SZ"
                    exchange = "深圳证券交易所"
                else:
                    symbol = self._to_symbol(code)
                    exchange = self._infer_exchange(code)

                results.append(
                    StockInfo(
                        symbol=symbol,
                        name=name,
                        exchange=exchange,
                        currency="CNY",
                        price=float(item.get("last_price", 0) or 0) or None,
                    )
                )

            return results[:50]
        except Exception:
            return []

    async def _get_etf_info(self, code: str) -> Optional[StockInfo]:
        results = await self._search_etfs(code)
        for item in results:
            if self._to_code(item.symbol) == code:
                return item
        return None

    async def search_stocks(self, query: str) -> List[StockInfo]:
        try:
            results = await self._request("/api/search", {"keyword": query})
            stocks = []
            for item in results or []:
                code = str(item.get("code", "")).strip()
                if not code:
                    continue
                stocks.append(
                    StockInfo(
                        symbol=self._to_symbol(code),
                        name=item.get("name", ""),
                        exchange=self._infer_exchange(code),
                        currency="CNY",
                    )
                )
            if not stocks:
                etf_results = await self._search_etfs(query)
                if etf_results:
                    return etf_results
            return stocks[:50]
        except Exception:
            etf_results = await self._search_etfs(query)
            if etf_results:
                return etf_results
            return await self.fallback.search_stocks(query)

    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        fallback_info = await self.fallback.get_stock_info(symbol)
        try:
            code = self._to_code(symbol)
            etf_info = await self._get_etf_info(code)
            results = await self._request("/api/quote", {"code": code})
            if not results:
                return fallback_info or etf_info

            quote = results[0]
            k_data = quote.get("K", {}) or {}
            close_raw = float(k_data.get("Close", 0) or 0)
            last_raw = float(k_data.get("Last", 0) or 0)
            change = (close_raw - last_raw) / 1000.0
            change_percent = ((close_raw - last_raw) / last_raw * 100) if last_raw else 0.0

            return StockInfo(
                symbol=symbol if "." in symbol else (etf_info.symbol if etf_info else self._to_symbol(code)),
                name=fallback_info.name if fallback_info and fallback_info.name else (etf_info.name if etf_info else ""),
                exchange=(
                    fallback_info.exchange if fallback_info and fallback_info.exchange
                    else (etf_info.exchange if etf_info and etf_info.exchange else self._infer_exchange(code))
                ),
                currency=(
                    fallback_info.currency if fallback_info and fallback_info.currency
                    else (etf_info.currency if etf_info and etf_info.currency else "CNY")
                ),
                price=close_raw / 1000.0 if close_raw else 0.0,
                change=change,
                changePercent=change_percent,
                marketCap=fallback_info.marketCap if fallback_info else None,
                marketStatus=fallback_info.marketStatus if fallback_info else None,
                volume=int(float(quote.get("TotalHand", 0) or 0) * 100),
                pe=fallback_info.pe if fallback_info else None,
                dividend=fallback_info.dividend if fallback_info else None,
            )
        except Exception:
            return fallback_info

    async def get_stock_price_history(
        self,
        symbol: str,
        interval: str = "daily",
        range: str = "1m"
    ) -> Optional[StockPriceHistory]:
        try:
            df = await self.get_historical_data(symbol, interval=interval, range=range)
            return self._build_price_history_from_df(symbol, df)
        except Exception:
            return await self.fallback.get_stock_price_history(symbol, interval=interval, range=range)

    async def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        return await self.fallback.get_fundamentals(symbol)

    async def get_historical_data(
        self,
        symbol: str,
        interval: str = "daily",
        range: str = "1y"
    ) -> Optional[pd.DataFrame]:
        try:
            code = self._to_code(symbol)
            data = await self._request(
                "/api/kline-all/tdx",
                {
                    "code": code,
                    "type": self._interval_to_tdx_type(interval),
                    "limit": self._range_to_limit(interval, range),
                },
            )
            rows = data.get("list", []) if isinstance(data, dict) else []
            df = self._normalize_kline_df(rows)
            if df is None or df.empty:
                return await self.fallback.get_historical_data(symbol, interval=interval, range=range)
            return df
        except Exception:
            return await self.fallback.get_historical_data(symbol, interval=interval, range=range)

    async def get_news_sentiment(self, symbol: str) -> Dict[str, Any]:
        return await self.fallback.get_news_sentiment(symbol)

    async def get_sector_linkage(self, symbol: str) -> Dict[str, Any]:
        return await self.fallback.get_sector_linkage(symbol)

    async def get_concept_distribution(self, symbol: str) -> Dict[str, Any]:
        return await self.fallback.get_concept_distribution(symbol)

    async def get_intraday_data(self, symbol: str, refresh: bool = False) -> Dict[str, Any]:
        try:
            code = self._to_code(symbol)
            data = await self._request("/api/minute", {"code": code})
            points = []
            for row in data.get("List", []) if isinstance(data, dict) else []:
                points.append(
                    {
                        "time": row.get("Time", ""),
                        "price": float(row.get("Price", 0) or 0) / 1000.0,
                        "volume": int(float(row.get("Number", 0) or 0) * 100),
                    }
                )
            if points:
                return {
                    "symbol": symbol,
                    "date": data.get("date") if isinstance(data, dict) else None,
                    "data": points,
                }
        except Exception:
            pass

        return await self.fallback.get_intraday_data(symbol, refresh)

    async def get_market_news(self, symbol: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        return await self.fallback.get_market_news(symbol, limit)
