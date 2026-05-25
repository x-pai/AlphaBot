from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.account import AccountService


class PositionService:
    """兼容层：统一委托给新的 AccountService（使用默认外部账户）。"""

    @staticmethod
    def upsert_position(
        db: Session,
        *,
        user_id: int,
        symbol: str,
        quantity_delta: float,
        price: float,
        currency: Optional[str] = None,
        source: str = "broker",
    ) -> Any:
        rows = AccountService.get_positions(db, user_id)
        current = next((row for row in rows if (row.symbol or "").upper() == symbol.upper()), None)
        current_qty = current.quantity if current else 0.0
        new_qty = current_qty + quantity_delta
        if new_qty < -1e-8:
            raise ValueError("卖出数量超过持仓数量")
        if new_qty <= 1e-8:
            return AccountService.set_position(
                db,
                user_id,
                symbol=symbol,
                quantity=0,
                cost_price=price,
                currency=currency,
                source=source,
            )
        if quantity_delta > 0 and current is not None:
            total_cost = current.cost_price * current.quantity + price * quantity_delta
            cost_price = total_cost / new_qty
        elif current is not None:
            cost_price = current.cost_price
        else:
            cost_price = price
        return AccountService.set_position(
            db,
            user_id,
            symbol=symbol,
            quantity=new_qty,
            cost_price=cost_price,
            currency=currency,
            source=source,
        )

    @staticmethod
    def set_position(
        db: Session,
        *,
        user_id: int,
        symbol: str,
        quantity: float,
        cost_price: float,
        currency: Optional[str] = None,
        source: str = "broker",
    ) -> Any:
        return AccountService.set_position(
            db,
            user_id,
            symbol=symbol,
            quantity=quantity,
            cost_price=cost_price,
            currency=currency,
            source=source,
        )

    @staticmethod
    def get_positions(db: Session, user_id: int) -> List[Any]:
        return AccountService.get_positions(db, user_id)

    @staticmethod
    async def get_positions_with_pnl(
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await AccountService.get_positions_with_pnl(
            db,
            user_id,
            data_source,
        )

    @staticmethod
    async def get_portfolio_summary(
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await AccountService.get_portfolio_summary(
            db,
            user_id,
            data_source,
        )

    @staticmethod
    async def get_portfolio_health(
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await AccountService.get_portfolio_health(
            db,
            user_id,
            data_source,
        )


class TradeLogService:
    """兼容层：统一委托给新的 AccountService（使用默认外部账户）。"""

    @staticmethod
    def add_trade(
        db: Session,
        *,
        user_id: int,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        trade_time=None,
        source: str = "broker",
    ) -> Any:
        return AccountService.add_trade(
            db,
            user_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            trade_time=trade_time,
            source=source,
        )

    @staticmethod
    def list_trades(
        db: Session,
        *,
        user_id: int,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        return AccountService.list_trades(
            db,
            user_id,
            symbol=symbol,
            limit=limit,
        )

    @staticmethod
    def import_from_csv(
        db: Session,
        *,
        user_id: int,
        csv_text: str,
        source: str = "import",
    ) -> Dict[str, Any]:
        return AccountService.import_trades(
            db,
            user_id,
            csv_text=csv_text,
            source=source,
        )
