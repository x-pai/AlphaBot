from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.account import AccountConnection
from app.services.account.registry import AccountConnectorRegistry


class AccountService:
    """统一账户门面：AlphaBot 上层只与这里交互。"""

    @staticmethod
    def list_accounts(db: Session, user_id: int) -> List[AccountConnection]:
        return (
            db.query(AccountConnection)
            .filter(AccountConnection.user_id == user_id, AccountConnection.is_active.is_(True))
            .order_by(AccountConnection.provider.asc(), AccountConnection.id.asc())
            .all()
        )

    @classmethod
    def resolve_account(
        cls,
        db: Session,
        user_id: int,
        *,
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> AccountConnection:
        if account_id is not None:
            account = (
                db.query(AccountConnection)
                .filter(
                    AccountConnection.id == account_id,
                    AccountConnection.user_id == user_id,
                    AccountConnection.is_active.is_(True),
                )
                .first()
            )
            if account is None:
                raise ValueError("账户不存在或无权访问")
            return account

        query = db.query(AccountConnection).filter(
            AccountConnection.user_id == user_id,
            AccountConnection.is_active.is_(True),
        )
        if provider:
            query = query.filter(AccountConnection.provider == provider.strip().lower())
        account = query.order_by(AccountConnection.is_default.desc(), AccountConnection.id.asc()).first()
        if account is None:
            detail = f"provider={provider} 的账户尚未配置" if provider else "当前用户尚未配置可用账户"
            raise ValueError(detail)
        return account

    @classmethod
    def get_positions(
        cls,
        db: Session,
        user_id: int,
        *,
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> List[Any]:
        account = cls.resolve_account(db, user_id, account_id=account_id, provider=provider)
        connector = AccountConnectorRegistry.get(account.provider)
        return connector.list_positions(db, account)

    @classmethod
    async def get_positions_with_pnl(
        cls,
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
        *,
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from app.services.stock_service import StockService

        account = cls.resolve_account(db, user_id, account_id=account_id, provider=provider)
        connector = AccountConnectorRegistry.get(account.provider)
        positions = connector.list_positions(db, account)
        result: List[Dict[str, Any]] = []
        for pos in positions:
            row: Dict[str, Any] = {
                "id": pos.id,
                "account_id": account.id,
                "provider": account.provider,
                "account_name": account.name,
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "cost_price": pos.cost_price,
                "currency": pos.currency or account.currency or "",
                "source": pos.source,
                "market_value": getattr(pos, "market_value", None),
                "current_price": getattr(pos, "current_price", None),
                "unrealized_pnl": getattr(pos, "unrealized_pnl", None),
                "unrealized_pnl_pct": getattr(pos, "unrealized_pnl_pct", None),
            }
            if row["current_price"] is None:
                try:
                    info = await StockService.get_stock_info(pos.symbol, data_source)
                    if info and getattr(info, "price", None) is not None:
                        price = float(info.price)
                        row["current_price"] = price
                except Exception:
                    pass
            if row["current_price"] is not None and row["market_value"] is None:
                row["market_value"] = round(pos.quantity * float(row["current_price"]), 2)
            cost_total = pos.quantity * pos.cost_price
            if row["market_value"] is not None and row["unrealized_pnl"] is None:
                pnl = float(row["market_value"]) - cost_total
                row["unrealized_pnl"] = round(pnl, 2)
                row["unrealized_pnl_pct"] = round(pnl / cost_total * 100, 2) if cost_total else None
            result.append(row)
        return result

    @classmethod
    def set_position(
        cls,
        db: Session,
        user_id: int,
        *,
        symbol: str,
        quantity: float,
        cost_price: float,
        currency: Optional[str] = None,
        source: str = "broker",
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> Any:
        account = cls.resolve_account(db, user_id, account_id=account_id, provider=provider)
        connector = AccountConnectorRegistry.get(account.provider)
        position = connector.set_position(
            db,
            account,
            symbol=symbol,
            quantity=quantity,
            cost_price=cost_price,
            currency=currency,
            source=source,
        )
        db.commit()
        if position is not None:
            db.refresh(position)
        return position

    @classmethod
    def list_trades(
        cls,
        db: Session,
        user_id: int,
        *,
        symbol: Optional[str] = None,
        limit: int = 100,
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> List[Any]:
        account = cls.resolve_account(db, user_id, account_id=account_id, provider=provider)
        connector = AccountConnectorRegistry.get(account.provider)
        return connector.list_trades(db, account, symbol=symbol, limit=limit)

    @classmethod
    def add_trade(
        cls,
        db: Session,
        user_id: int,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        trade_time: Any = None,
        source: str = "",
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> Any:
        account = cls.resolve_account(db, user_id, account_id=account_id, provider=provider)
        connector = AccountConnectorRegistry.get(account.provider)
        return connector.add_trade(
            db,
            account,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            source=source,
            trade_time=trade_time,
        )

    @classmethod
    def import_trades(
        cls,
        db: Session,
        user_id: int,
        *,
        csv_text: str,
        source: str = "import",
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        account = cls.resolve_account(db, user_id, account_id=account_id, provider=provider)
        connector = AccountConnectorRegistry.get(account.provider)
        return connector.import_trades(db, account, csv_text=csv_text, source=source)

    @classmethod
    async def get_portfolio_summary(
        cls,
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
        *,
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        account = cls.resolve_account(db, user_id, account_id=account_id, provider=provider)
        positions_with_pnl = await cls.get_positions_with_pnl(
            db,
            user_id,
            data_source,
            account_id=account.id,
            provider=account.provider,
        )
        total_cost = sum(p["quantity"] * p["cost_price"] for p in positions_with_pnl)
        total_market_value = sum(
            (p["market_value"] or p["quantity"] * p["cost_price"]) for p in positions_with_pnl
        )
        total_pnl = round(total_market_value - total_cost, 2) if total_cost else None
        total_pnl_pct = round(total_pnl / total_cost * 100, 2) if total_pnl is not None and total_cost else None
        return {
            "account_id": account.id,
            "provider": account.provider,
            "account_name": account.name,
            "cash_balance": account.cash_balance,
            "currency": account.currency,
            "total_cost": round(total_cost, 2),
            "total_market_value": round(total_market_value, 2),
            "total_unrealized_pnl": total_pnl,
            "total_unrealized_pnl_pct": total_pnl_pct,
            "positions_count": len(positions_with_pnl),
            "positions": positions_with_pnl,
        }

    @classmethod
    async def get_portfolio_health(
        cls,
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
        *,
        account_id: Optional[int] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        summary = await cls.get_portfolio_summary(
            db,
            user_id,
            data_source,
            account_id=account_id,
            provider=provider,
        )
        positions = summary.get("positions") or []
        total_cost = summary.get("total_cost") or 0
        total_market_value = summary.get("total_market_value")
        total_pnl = summary.get("total_unrealized_pnl")
        total_pnl_pct = summary.get("total_unrealized_pnl_pct")
        n = len(positions)
        labels: List[str] = []
        if n == 0:
            labels.append("空仓")
        else:
            if total_cost and total_market_value is not None:
                if (total_pnl_pct or 0) >= 5:
                    labels.append("组合浮盈")
                elif (total_pnl_pct or 0) <= -5:
                    labels.append("组合浮亏")
                else:
                    labels.append("组合盈亏平衡附近")
            if total_market_value and positions:
                max_mv = max((p.get("market_value") or p["quantity"] * p["cost_price"]) for p in positions)
                concentration = max_mv / total_market_value if total_market_value else 0
                if concentration >= 0.5:
                    labels.append("单股集中度高")
                elif concentration >= 0.3:
                    labels.append("有一定集中度")
                else:
                    labels.append("分散持仓")
            if n <= 2:
                labels.append("持股较少")
            elif n >= 6:
                labels.append("持股较多")
        if n == 0:
            comment = "当前无持仓，可结合计划逐步建仓。"
        else:
            parts: List[str] = []
            if total_pnl is not None and total_cost:
                parts.append(f"组合{'浮盈' if total_pnl >= 0 else '浮亏'} {abs(total_pnl):.2f}（{total_pnl_pct or 0:.1f}%）")
            if "单股集中度高" in labels:
                parts.append("注意单只仓位过重，可考虑分散风险。")
            if "组合浮亏" in labels and "单股集中度高" in labels:
                parts.append("建议关注重仓股基本面与仓位管理。")
            comment = "；".join(parts) if parts else "组合结构正常，可定期复盘。"
        return {
            **summary,
            "labels": labels,
            "comment": comment,
        }
