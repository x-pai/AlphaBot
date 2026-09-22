import logging
import json
import time

import pytest

from app.services import market_cache
from app.services.market_domain_service import MarketDomainService
from app.services.market_strategy_service import MarketStrategyService


@pytest.fixture(autouse=True)
def legacy_market_source(monkeypatch):
    from app.core.config import settings
    from app.services.market_data_sources.factory import MarketDataSourceFactory
    monkeypatch.setattr(settings, "DEFAULT_MARKET_DATA_SOURCE", "xgb")
    monkeypatch.setattr(MarketDataSourceFactory, "_explicit_bindings", {})


class TestMarketRouteContracts:
    @pytest.fixture(autouse=True)
    def isolate_route_lifespan(self, monkeypatch):
        # 领域路由契约测试不启动调度器/外部 MCP，也不访问独立的生产 SessionLocal。
        from contextlib import asynccontextmanager
        from app.main import app
        @asynccontextmanager
        async def lifespan(_app):
            yield
        monkeypatch.setattr(app.router, "lifespan_context", lifespan)


    def test_tdxaidata_source_info_and_unavailable_response(self, client, auth_headers, monkeypatch):
        from app.core.config import settings
        from app.services.market_data_sources.tdxaidata_client import TdxAiDataUnavailable
        monkeypatch.setattr(settings, "DEFAULT_MARKET_DATA_SOURCE", "tdxaidata")
        response = client.get("/api/v1/market/source-info", headers=auth_headers)
        data = response.json()["data"]
        assert set(data["bindings"].values()) == {"tdxaidata"}
        assert {"emotion_short", "payoff_hot", "historical_pools", "historical_payoff"} <= set(data["unavailable"])
        assert "token" not in response.text.lower()
    def test_tdxaidata_error_is_503(self, client, auth_headers, monkeypatch):
        from app.services.market_data_sources.tdxaidata_client import TdxAiDataUnavailable
        async def fail(_symbols):
            raise TdxAiDataUnavailable("upstream unavailable")
        monkeypatch.setattr(MarketDomainService, "get_quotes", fail)
        failed = client.get("/api/v1/market/quotes?symbols=600000", headers=auth_headers)
        assert failed.status_code == 503
        assert failed.json()["success"] is False

    def test_market_strategy_read_returns_encrypted_envelope(self, client, auth_headers, monkeypatch):
        async def fake_get_strategy():
            return {"version": "test", "private": {"rebound": {"weights": {"gap2": 8}}}}

        monkeypatch.setattr(MarketDomainService, "get_strategy", fake_get_strategy)

        response = client.get("/api/v1/market/strategy", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["payload"].startswith("v1.")
        assert "private" not in data
        assert set(data) == {"payload"}

    def test_market_strategy_write_requires_admin(self, client, auth_headers, monkeypatch):
        async def fail_if_called(*_args, **_kwargs):
            raise AssertionError("non-admin must not write market strategy")

        monkeypatch.setattr(MarketDomainService, "set_strategy", fail_if_called)

        response = client.put(
            "/api/v1/market/strategy",
            headers=auth_headers,
            json={"version": "manual-test", "private": {"rebound": {"weights": {"gap2": 8}}}},
        )

        assert response.status_code == 403

    def test_market_strategy_admin_can_write(self, client, auth_headers, db, test_user, monkeypatch):
        test_user.is_admin = True
        db.commit()

        async def fake_set_strategy(private, version):
            assert private == {"rebound": {"weights": {"gap2": 8}}}
            assert version == "manual-test"
            return {"version": version, "private": private}

        monkeypatch.setattr(MarketDomainService, "set_strategy", fake_set_strategy)

        response = client.put(
            "/api/v1/market/strategy",
            headers=auth_headers,
            json={"version": "manual-test", "private": {"rebound": {"weights": {"gap2": 8}}}},
        )

        assert response.status_code == 200
        assert response.json()["data"]["version"] == "manual-test"

    def test_market_universe_returns_list_envelope(self, client, auth_headers, monkeypatch):
        async def fake_get_universe():
            return {"date": "20260830", "items": [{"code": "123", "name": "AI", "change": 1.2}]}

        monkeypatch.setattr(MarketDomainService, "get_universe", fake_get_universe)

        response = client.get("/api/v1/market/universe", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["items"] == [{"code": "123", "name": "AI", "change": 1.2,
            "netFlow": None, "ztCount": None, "upCount": None, "downCount": None, "flatCount": None}]
        assert body["data"]["date"] == "20260830"

    def test_market_quotes_returns_map_envelope(self, client, auth_headers, monkeypatch):
        async def fake_get_quotes(symbols: str):
            assert symbols == "000001,600000"
            return {
                "items": {
                    "000001": {"name": "PingAn", "price": 12.3, "change": 1.1},
                    "600000": {"name": "PF Bank", "price": 9.8, "change": -0.2},
                }
            }

        monkeypatch.setattr(MarketDomainService, "get_quotes", fake_get_quotes)

        response = client.get("/api/v1/market/quotes?symbols=000001,600000", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["items"]["000001"]["name"] == "PingAn"
        assert body["data"]["items"]["600000"]["change"] == -0.2

    def test_market_turnover_returns_object_envelope(self, client, auth_headers, monkeypatch):
        async def fake_get_turnover():
            return {
                "current": 12345.0,
                "predict": 15600.0,
                "previous": 11000.0,
                "change": 1345.0,
                "points": [{"time": "09:30", "today": 100.0, "yesterday": 80.0}],
            }

        monkeypatch.setattr(MarketDomainService, "get_turnover", fake_get_turnover)

        response = client.get("/api/v1/market/turnover", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["current"] == 12345.0
        assert body["data"]["points"][0]["time"] == "09:30"

    def test_market_pool_invalid_kind_returns_404(self, client, auth_headers):
        response = client.get("/api/v1/market/pool/invalid", headers=auth_headers)

        assert response.status_code == 404


class TestMarketDomainServiceCaching:
    @pytest.mark.asyncio
    async def test_quotes_uses_cache_after_first_fetch(self, monkeypatch, caplog):
        calls = {"count": 0}
        latest_day = "20260831"
        cache_key = market_cache.source_key("quotes", "xgb", market_cache.quotes_key(["000001", "600000"], latest_day))

        async def fake_get_json(key: str):
            assert key == cache_key
            if calls["count"] == 0:
                return None
            return {
                "000001": {"name": "PingAn", "price": 12.3, "change": 1.1},
                "600000": {"name": "PF Bank", "price": 9.8, "change": -0.2},
            }

        async def fake_cached_call(key, ttl, fetch):
            assert key == cache_key
            expected_ttl = MarketDomainService._ttl_with_jitter(
                MarketDomainService.QUOTES_TTL_SECONDS,
                cache_key,
                enabled=True,
            )
            assert ttl == expected_ttl
            calls["count"] += 1
            return await fetch()

        class FakeSource:
            async def fetch_quotes(self, codes):
                assert codes == ["000001", "600000"]
                return {
                    "000001": {"name": "PingAn", "price": 12.3, "change": 1.1},
                    "600000": {"name": "PF Bank", "price": 9.8, "change": -0.2},
                }

        monkeypatch.setattr(market_cache, "get_json", fake_get_json)
        monkeypatch.setattr(market_cache, "cached_call", fake_cached_call)
        monkeypatch.setattr(
            "app.services.market_domain_service.MarketDataSourceFactory.resolve",
            lambda dataset: ("xgb", FakeSource()),
        )

        async def fake_cache_trade_day():
            return latest_day

        monkeypatch.setattr(MarketDomainService, "_cache_trade_day", fake_cache_trade_day)

        with caplog.at_level(logging.INFO, logger="uvicorn"):
            first = await MarketDomainService.get_quotes("000001,600000")
            second = await MarketDomainService.get_quotes("000001,600000")

        assert first["items"]["000001"]["name"] == "PingAn"
        assert second["items"]["600000"]["name"] == "PF Bank"
        assert calls["count"] == 1
        assert "market.cache refresh label=quotes" in caplog.text
        assert "market.cache hit label=quotes" in caplog.text

    @pytest.mark.asyncio
    async def test_get_pool_returns_empty_when_refresh_fails_even_with_existing_cache(self, monkeypatch):
        latest_day = "20260831"
        cache_key = market_cache.pool_key("zt", latest_day)
        stored = {
            cache_key: {
            "date": latest_day,
            "fetchedAtTs": 0,
            "items": [{"code": "000001", "name": "PingAn"}],
        }
        }

        async def fake_latest_trading_day():
            return latest_day

        async def fake_get_json(key: str):
            return stored.get(key)

        async def fake_set_json(key: str, value, ttl=None):
            stored[key] = value

        async def fake_single_flight_freshness(key, min_interval, fetch):
            raise RuntimeError("upstream failure")

        monkeypatch.setattr(MarketDomainService, "latest_trading_day", fake_latest_trading_day)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)
        monkeypatch.setattr(market_cache, "set_json", fake_set_json)
        monkeypatch.setattr(MarketDomainService, "_single_flight_freshness", fake_single_flight_freshness)

        payload = await MarketDomainService.get_pool("zt", latest_day)

        assert payload == {
            "date": latest_day,
            "items": [],
        }

    @pytest.mark.asyncio
    async def test_get_latest_context_returns_empty_pool_when_refresh_fails_without_cache(self, monkeypatch):
        latest_day = "20260831"
        stored: dict[str, dict] = {}

        async def fake_latest_trading_day():
            return latest_day

        async def fake_get_json(key: str):
            return stored.get(key)

        async def fake_set_json(key: str, value, ttl=None):
            stored[key] = value

        async def fake_single_flight_freshness(key, min_interval, fetch):
            if key.endswith(":pool-zt") or key.endswith(":pool-zb") or key.endswith(":pool-dt"):
                raise RuntimeError("upstream failure")
            return None

        async def fake_get_surge():
            return {"date": latest_day, "items": []}

        async def fake_get_universe():
            return {"date": latest_day, "items": []}

        monkeypatch.setattr(MarketDomainService, "latest_trading_day", fake_latest_trading_day)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)
        monkeypatch.setattr(market_cache, "set_json", fake_set_json)
        monkeypatch.setattr(MarketDomainService, "_single_flight_freshness", fake_single_flight_freshness)
        monkeypatch.setattr(MarketDomainService, "get_surge", fake_get_surge)
        monkeypatch.setattr(MarketDomainService, "get_universe", fake_get_universe)

        payload = await MarketDomainService.get_latest_context()

        assert payload["latestDay"] == latest_day
        assert payload["latestZt"] == []
        assert payload["latestZb"] == []
        assert payload["latestDt"] == []
        assert payload["pools"]["ztByDate"] == {latest_day: []}
        assert payload["pools"]["zbByDate"] == {latest_day: []}
        assert payload["pools"]["dtByDate"] == {latest_day: []}

    @pytest.mark.asyncio
    async def test_universe_refreshes_existing_intraday_cache_by_overwrite(self, monkeypatch):
        latest_day = "20260831"
        cache_key = market_cache.source_key("universe", "xgb", market_cache.universe_key_for_day(latest_day))
        stored = {
            cache_key: {
                "date": latest_day,
                "fetchedAtTs": 0,
                "items": [{"code": "old", "name": "Old"}],
            }
        }

        async def fake_cache_trade_day():
            return latest_day

        async def fake_get_json(key: str):
            return stored.get(key)

        async def fake_overwrite_json(key: str, value, ttl=None):
            resolved = await value if hasattr(value, "__await__") else value
            stored[key] = resolved
            return resolved

        async def fake_is_closed_window():
            return False

        async def fake_single_flight_freshness(key, min_interval, fetch):
            assert key == "xgb:universe"
            assert min_interval == MarketDomainService.UNIVERSE_FRESH_SECONDS
            await fetch()

        class FakeSource:
            async def fetch_universe(self):
                return [{"code": "new", "name": "New"}]

        monkeypatch.setattr(MarketDomainService, "_cache_trade_day", fake_cache_trade_day)
        monkeypatch.setattr(MarketDomainService, "_is_closed_window", fake_is_closed_window)
        monkeypatch.setattr(MarketDomainService, "_single_flight_freshness", fake_single_flight_freshness)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)
        monkeypatch.setattr(market_cache, "overwrite_json", fake_overwrite_json)
        monkeypatch.setattr(
            "app.services.market_domain_service.MarketDataSourceFactory.resolve",
            lambda dataset: ("xgb", FakeSource()),
        )

        payload = await MarketDomainService.get_universe()

        assert payload["date"] == latest_day
        assert payload["items"] == [{"code": "new", "name": "New"}]

    @pytest.mark.asyncio
    async def test_surge_skips_refresh_after_close_when_cache_exists(self, monkeypatch):
        latest_day = "20260831"
        cache_key = market_cache.source_key("surge", "xgb", market_cache.surge_key_for_day(latest_day))
        stored = {
            cache_key: {
                "date": latest_day,
                "fetchedAtTs": 0,
                "items": [{"code": "001", "name": "Surge"}],
            }
        }

        async def fake_cache_trade_day():
            return latest_day

        async def fake_get_json(key: str):
            return stored.get(key)

        async def fake_is_closed_window():
            return True

        async def fail_single_flight_freshness(*args, **kwargs):
            raise AssertionError("should not refresh after close")

        monkeypatch.setattr(MarketDomainService, "_cache_trade_day", fake_cache_trade_day)
        monkeypatch.setattr(MarketDomainService, "_is_closed_window", fake_is_closed_window)
        monkeypatch.setattr(MarketDomainService, "_single_flight_freshness", fail_single_flight_freshness)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)

        payload = await MarketDomainService.get_surge()

        assert payload["date"] == latest_day
        assert payload["items"] == [{"code": "001", "name": "Surge"}]

    @pytest.mark.asyncio
    async def test_plate_members_backfill_latest_trade_day_on_first_weekend_request(self, monkeypatch):
        latest_day = "20260828"
        cache_key = market_cache.source_key("members", "xgb", market_cache.members_key("885001", latest_day))
        stored: dict[str, dict] = {}

        async def fake_cache_trade_day():
            return latest_day

        async def fake_is_closed_window():
            return True

        async def fake_get_json(key: str):
            return stored.get(key)

        async def fake_cached_call(key, ttl, fetch):
            assert key == cache_key
            assert ttl == MarketDomainService.TRADE_DAY_RETENTION_SECONDS
            payload = await fetch()
            stored[key] = payload
            return payload

        class FakeSource:
            async def fetch_members(self, plate_id):
                assert plate_id == "885001"
                return [{"code": "000001", "name": "PingAn"}]

        monkeypatch.setattr(MarketDomainService, "_cache_trade_day", fake_cache_trade_day)
        monkeypatch.setattr(MarketDomainService, "_is_closed_window", fake_is_closed_window)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)
        monkeypatch.setattr(market_cache, "cached_call", fake_cached_call)
        monkeypatch.setattr(
            "app.services.market_domain_service.MarketDataSourceFactory.resolve",
            lambda dataset: ("xgb", FakeSource()),
        )

        payload = await MarketDomainService.get_plate_members("885001")

        assert stored[cache_key]["date"] == latest_day
        assert payload["items"] == [{"code": "000001", "name": "PingAn"}]

    @pytest.mark.asyncio
    async def test_fundflow_reuses_frozen_trade_day_cache_after_close(self, monkeypatch):
        latest_day = "20260828"
        cache_key = market_cache.source_key("fundflow", "xgb", market_cache.fundflow_key(["000001"], 5, latest_day))
        stored = {
            cache_key: {
                "date": latest_day,
                "fetchedAtTs": 0,
                "items": {"000001": [{"date": latest_day, "netInflow": 1.0}]},
            }
        }

        async def fake_cache_trade_day():
            return latest_day

        async def fake_is_closed_window():
            return True

        async def fake_get_json(key: str):
            return stored.get(key)

        async def fail_single_flight_freshness(*args, **kwargs):
            raise AssertionError("should not refresh frozen trade-day cache")

        monkeypatch.setattr(MarketDomainService, "_cache_trade_day", fake_cache_trade_day)
        monkeypatch.setattr(MarketDomainService, "_is_closed_window", fake_is_closed_window)
        monkeypatch.setattr(MarketDomainService, "_single_flight_freshness", fail_single_flight_freshness)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)

        payload = await MarketDomainService.get_fundflow("000001", 5)

        assert payload["items"] == {"000001": [{"date": latest_day, "netInflow": 1.0}]}

    @pytest.mark.asyncio
    async def test_payoff_drawdown_accepts_legacy_list_cache_shape(self, monkeypatch):
        latest_day = "20260901"
        cache_key = market_cache.source_key("payoff_drawdown", "ths", market_cache.payoff_key("drawdown", latest_day))
        legacy_items = [
            {"name": "Alpha", "change": -3.2, "maxDrawdown": -8.6, "industryBlock": "AI"}
        ]

        async def fake_cache_trade_day():
            return latest_day

        async def fake_is_closed_window():
            return False

        async def fake_get_json(key: str):
            assert key == cache_key
            return legacy_items

        async def fail_single_flight_freshness(*args, **kwargs):
            raise AssertionError("freshness refresh should not run when serving legacy cache within fallback path")

        monkeypatch.setattr(MarketDomainService, "_cache_trade_day", fake_cache_trade_day)
        monkeypatch.setattr(MarketDomainService, "_is_closed_window", fake_is_closed_window)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)
        monkeypatch.setattr(MarketDomainService, "_single_flight_freshness", fail_single_flight_freshness)
        monkeypatch.setattr(MarketDomainService, "_trade_day_fetched_at", lambda payload: time.time())

        payload = await MarketDomainService.get_payoff("drawdown", latest_day)

        assert payload["items"] == legacy_items

    @pytest.mark.asyncio
    async def test_payoff_history_stores_trade_day_payload(self, monkeypatch):
        latest_day = "20260901"
        history_day = "20260831"
        cache_key = market_cache.source_key("payoff_drawdown", "ths", market_cache.payoff_key("drawdown", history_day))
        stored = {}
        expected_items = [{"name": "Alpha", "change": -3.2, "maxDrawdown": -8.6}]

        async def fake_cache_trade_day():
            return latest_day

        async def fake_get_json(key: str):
            return stored.get(key)

        async def fake_cached_call(key, ttl, fetch):
            assert key == cache_key
            assert ttl == MarketDomainService.PAYOFF_DRAWDOWN_HISTORY_TTL_SECONDS
            stored[key] = await fetch()
            return stored[key]

        class FakeSource:
            async def fetch_payoff(self, kind, date):
                assert kind == "drawdown"
                assert date == history_day
                return expected_items

        monkeypatch.setattr(MarketDomainService, "_cache_trade_day", fake_cache_trade_day)
        monkeypatch.setattr(market_cache, "get_json", fake_get_json)
        monkeypatch.setattr(market_cache, "cached_call", fake_cached_call)
        monkeypatch.setattr(
            "app.services.market_domain_service.MarketDataSourceFactory.resolve",
            lambda dataset: ("ths", FakeSource()),
        )

        payload = await MarketDomainService.get_payoff("drawdown", history_day)

        assert payload == {"items": expected_items}
        assert stored[cache_key]["date"] == history_day
        assert stored[cache_key]["items"] == expected_items
        assert isinstance(stored[cache_key]["fetchedAtTs"], float)


class TestMarketStrategyService:
    def test_load_defaults_payload_seeds_empty_file_from_default_schema(self, tmp_path, monkeypatch):
        defaults_path = tmp_path / "private.defaults.json"
        defaults_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(MarketStrategyService, "DEFAULTS_PATH", defaults_path)

        payload = MarketStrategyService.load_defaults_payload()

        assert payload == MarketStrategyService.DEFAULT_PAYLOAD
        assert json.loads(defaults_path.read_text(encoding="utf-8")) == MarketStrategyService.DEFAULT_PAYLOAD

    def test_default_private_is_zero_placeholder(self):
        """代码内置骨架只允许全 0 占位：防止真实 fitted 权重误入仓库。"""

        def assert_all_zero(node):
            if isinstance(node, dict):
                for value in node.values():
                    assert_all_zero(value)
            elif isinstance(node, list):
                for value in node:
                    assert_all_zero(value)
            else:
                assert node == 0, f"default schema must only contain placeholder 0, got {node!r}"

        payload = MarketStrategyService.DEFAULT_PAYLOAD
        assert payload["version"] == MarketStrategyService.DEFAULT_VERSION
        assert set(payload["private"]) == {"mainline", "rebound", "relay", "flowStrength"}
        assert_all_zero(payload["private"])

    @pytest.mark.asyncio
    async def test_set_strategy_writes_defaults_file(self, tmp_path, monkeypatch):
        defaults_path = tmp_path / "private.defaults.json"
        monkeypatch.setattr(MarketStrategyService, "DEFAULTS_PATH", defaults_path)

        payload = await MarketStrategyService.set_strategy({"rebound": {"weights": {"gap2": 8}}}, "manual-test")

        assert payload == {
            "version": "manual-test",
            "private": {"rebound": {"weights": {"gap2": 8}}},
        }
        assert json.loads(defaults_path.read_text(encoding="utf-8")) == payload
