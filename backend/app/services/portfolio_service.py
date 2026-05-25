from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.account import AccountService


class PositionService:
    """兼容层：仅保留只读查询能力。"""

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
    """兼容层：保留真实交易查询与委托能力。"""

    @staticmethod
    def place_order(
        db: Session,
        *,
        user_id: int,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "limit",
    ) -> Any:
        return AccountService.place_order(
            db,
            user_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
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
    def list_orders(
        db: Session,
        *,
        user_id: int,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        return AccountService.get_orders(
            db,
            user_id,
            symbol=symbol,
            limit=limit,
        )
