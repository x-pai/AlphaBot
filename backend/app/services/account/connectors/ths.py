from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from urllib import parse, request

from sqlalchemy.orm import Session

from app.models.account import AccountConnection
from app.services.account.base import AccountConnector


class THSAccountConnector(AccountConnector):
    provider = "ths"
    auto_create_account = False
    default_base_url = "http://trade.10jqka.com.cn:8088"
    default_yybid = "997376"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def build_default_account(self, user_id: int) -> AccountConnection:  # noqa: ARG002
        raise NotImplementedError("同花顺账户需要显式配置连接信息")

    @staticmethod
    def _load_account_config(account: AccountConnection) -> dict:
        payload = {}
        raw = (account.config_json or "").strip()
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:  # noqa: PERF203
                raise ValueError("THS 账户配置不是合法 JSON") from exc
        return payload

    @classmethod
    def _runtime(cls, account: AccountConnection) -> dict:
        config = cls._load_account_config(account)
        capital_account = str(
            config.get("capital_account")
            or config.get("account")
            or ""
        ).strip()
        if not capital_account:
            raise ValueError("THS 账户缺少 capital_account")
        return {
            "account": capital_account,
            "username": str(config.get("username") or "").strip(),
            "yybid": str(config.get("department_id") or config.get("yybid") or cls.default_yybid).strip(),
            "base_url": str(config.get("base_url") or cls.default_base_url).strip().rstrip("/"),
            "shareholder_accounts": config.get("shareholder_accounts") or {},
            "market_codes": config.get("market_codes") or {"sz": "1", "sh": "2"},
        }

    @classmethod
    def _get(cls, runtime: dict, path: str, params: dict, timeout: int = 30) -> dict:
        url = f"{runtime['base_url']}{path}?{parse.urlencode(params)}"
        req = request.Request(url, headers={"User-Agent": cls.user_agent}, method="GET")
        with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            charset = resp.headers.get_content_charset() or "utf-8"
            data = json.loads(resp.read().decode(charset))
        for key in ("errorcode", "error_no", "code"):
            if key in data and str(data.get(key)) not in ("0", "0.0"):
                message = data.get("errormsg", data.get("error_info", data.get("msg", "未知错误")))
                raise RuntimeError(f"THS 接口调用失败: {message}")
        return data

    @staticmethod
    def _float(value, default: float = 0.0) -> float:
        try:
            text = str(value or "").replace(",", "").strip()
            if not text or text == "--":
                return default
            return float(text)
        except (TypeError, ValueError):
            return default

    def get_cash_balance(self, account: AccountConnection) -> float | None:
        runtime = self._runtime(account)
        data = self._get(runtime, "/pt_qry_fund_t", {"usrid": runtime["account"], "datatype": "json"})
        result_data = data.get("result")
        fund_list = data.get("list")
        if not fund_list and isinstance(result_data, dict):
            fund_list = result_data.get("list")
        if not isinstance(fund_list, list) or not fund_list:
            fund_list = result_data if isinstance(result_data, list) else []
        fund = fund_list[0] if fund_list else {}
        return self._float(fund.get("kyje", fund.get("zjye")), 0.0)

    def list_positions(self, db: Session, account: AccountConnection):  # noqa: ARG002
        runtime = self._runtime(account)
        self._get(runtime, "/pt_qry_fund_t", {"usrid": runtime["account"], "datatype": "json"})
        stock_data = self._get(
            runtime,
            "/pt_web_qry_stock",
            {"name": runtime["account"], "yybid": runtime["yybid"], "type": "1", "datatype": "json"},
        )
        account.cash_balance = self.get_cash_balance(account)
        raw = stock_data.get("data") or stock_data.get("result") or stock_data.get("list") or []
        rows = []
        for idx, row in enumerate(raw if isinstance(raw, list) else []):
            if not isinstance(row, dict):
                continue
            quantity = self._float(row.get("gpsl", row.get("quantity")), 0.0)
            cost_price = self._float(row.get("gpcb", row.get("cost_price")), 0.0)
            current_price = self._float(row.get("zxjg", row.get("price")), 0.0)
            market_value = self._float(row.get("gpz", row.get("market_value")), quantity * current_price)
            rows.append(
                SimpleNamespace(
                    id=idx + 1,
                    account_id=account.id,
                    user_id=account.user_id,
                    symbol=str(row.get("zqdm", row.get("stock_code", ""))).strip(),
                    quantity=quantity,
                    cost_price=cost_price,
                    currency=account.currency or "CNY",
                    source="broker",
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=self._float(row.get("fdyk", row.get("pnl")), market_value - quantity * cost_price),
                    unrealized_pnl_pct=self._float(row.get("ydl", row.get("pnl_pct")), 0.0),
                )
            )
        return rows

    def list_trades(self, db: Session, account: AccountConnection, symbol=None, limit: int = 100):  # noqa: ARG002
        runtime = self._runtime(account)
        data = self._get(
            runtime,
            "/pt_qry_busin_nocache",
            {"usrname": runtime["account"], "kind": "1", "datatype": "json"},
        )
        raw = data.get("result") or data.get("list") or data.get("ret", {}).get("item", [])
        rows = []
        symbol_filter = str(symbol or "").strip().upper()
        today = datetime.utcnow().date()
        for idx, row in enumerate(raw if isinstance(raw, list) else []):
            if not isinstance(row, dict):
                continue
            row_symbol = str(row.get("zqdm", "")).strip().upper()
            if symbol_filter and row_symbol != symbol_filter:
                continue
            price = self._float(row.get("cjg", row.get("cjj")), 0.0)
            amount = self._float(row.get("cje"), 0.0)
            quantity = self._float(row.get("cjsl"), amount / price if price else 0.0)
            raw_time = str(row.get("cjsj", "")).strip()
            trade_time = datetime.utcnow()
            if raw_time:
                try:
                    parsed = datetime.strptime(raw_time, "%H:%M:%S").time()
                    trade_time = datetime.combine(today, parsed)
                except ValueError:
                    trade_time = datetime.utcnow()
            rows.append(
                SimpleNamespace(
                    id=idx + 1,
                    account_id=account.id,
                    user_id=account.user_id,
                    symbol=row_symbol,
                    side="buy" if "买" in str(row.get("mmlb", "")) or str(row.get("mmlb", "")).upper() == "B" else "sell",
                    quantity=quantity,
                    price=price,
                    amount=amount or round(price * quantity, 2),
                    fee=0.0,
                    trade_time=trade_time,
                    source="broker",
                    created_at=datetime.utcnow(),
                )
            )
            if len(rows) >= limit:
                break
        return rows

    def get_orders(self, db: Session, account: AccountConnection, symbol=None, limit: int = 100):  # noqa: ARG002
        runtime = self._runtime(account)
        data = self._get(
            runtime,
            "/pt_qry_busin1",
            {
                "usrname": runtime["account"],
                "start": "0",
                "end": str(max(limit, 100)),
                "yhbId": runtime["yybid"],
                "kind": "1",
                "datatype": "json",
            },
        )
        raw = data.get("result") or data.get("list") or data.get("ret", {}).get("item", [])
        rows = []
        symbol_filter = str(symbol or "").strip().upper()
        today = datetime.utcnow().date()
        for idx, row in enumerate(raw if isinstance(raw, list) else []):
            if not isinstance(row, dict):
                continue
            row_symbol = str(row.get("zqdm", row.get("stock_code", ""))).strip().upper()
            if symbol_filter and row_symbol != symbol_filter:
                continue
            price = self._float(row.get("wtjg", row.get("price")), 0.0)
            quantity = self._float(row.get("wtsl", row.get("quantity")), 0.0)
            filled_quantity = self._float(row.get("cjsl", row.get("filled_quantity")), 0.0)
            raw_time = str(row.get("wtsj", row.get("time", ""))).strip()
            order_time = datetime.utcnow()
            if raw_time:
                try:
                    parsed = datetime.strptime(raw_time, "%H:%M:%S").time()
                    order_time = datetime.combine(today, parsed)
                except ValueError:
                    order_time = datetime.utcnow()
            direction = str(row.get("mmlb", row.get("direction", ""))).strip().upper()
            status = str(row.get("status", row.get("wtzt", "submitted"))).strip() or "submitted"
            rows.append(
                SimpleNamespace(
                    id=idx + 1,
                    account_id=account.id,
                    user_id=account.user_id,
                    order_id=str(row.get("wtbh", row.get("entrust_no", row.get("order_id", "")))).strip(),
                    symbol=row_symbol,
                    name=str(row.get("zqmc", row.get("name", ""))).strip(),
                    side="buy" if ("买" in direction or direction == "B") else "sell",
                    quantity=quantity,
                    filled_quantity=filled_quantity,
                    price=price,
                    status=status,
                    order_type="limit",
                    order_time=order_time,
                    source="broker",
                    created_at=datetime.utcnow(),
                )
            )
            if len(rows) >= limit:
                break
        return rows

    def place_order(self, db: Session, account: AccountConnection, **kwargs):  # noqa: ARG002
        runtime = self._runtime(account)
        symbol = str(kwargs.get("symbol") or "").strip()
        side = str(kwargs.get("side") or "").strip().lower()
        quantity = int(float(kwargs.get("quantity") or 0))
        price = float(kwargs.get("price") or 0)
        order_type = str(kwargs.get("order_type") or "limit").strip().lower()
        if order_type != "limit":
            raise ValueError("THS 当前仅支持 limit 限价单")
        if not symbol or quantity <= 0 or price <= 0:
            raise ValueError("THS 下单需要有效的 symbol、quantity、price")
        market = "sh" if symbol.startswith(("6", "5", "9")) else "sz"
        shareholder = str((runtime.get("shareholder_accounts") or {}).get(market) or "").strip()
        if not shareholder:
            raise ValueError(f"缺少 THS {market.upper()} 股东账号")
        market_code = str((runtime.get("market_codes") or {}).get(market) or ("2" if market == "sh" else "1")).strip()
        payload = self._get(
            runtime,
            "/pt_stk_weituo_dklc",
            {
                "usrid": runtime["account"],
                "zqdm": symbol,
                "gddh": shareholder,
                "scdm": market_code,
                "yybd": runtime["yybid"],
                "wtjg": str(price),
                "wtsl": str(quantity),
                "mmlb": "B" if side == "buy" else "S",
                "datatype": "json",
            },
        )
        result = payload.get("result", [])
        row = result[0] if isinstance(result, list) and result else result if isinstance(result, dict) else {}
        order_id = str(row.get("entrust_no", row.get("wtbh", row.get("order_id", "")))).strip()
        return SimpleNamespace(
            id=None,
            account_id=account.id,
            user_id=account.user_id,
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=float(quantity),
            filled_quantity=0.0,
            price=price,
            status="submitted",
            order_type=order_type,
            order_time=datetime.utcnow(),
            source="broker",
            created_at=datetime.utcnow(),
        )

    def cancel_order(
        self,
        db: Session,
        account: AccountConnection,
        *,
        order_id: str | None = None,
        cancel_all: bool = False,
    ):  # noqa: ARG002
        raise NotImplementedError("THS hithink-moni 当前未找到可用撤单端点，暂无法实现 cancel_order")
