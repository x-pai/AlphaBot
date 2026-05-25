from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.account import AccountConnection


class AccountConnector(ABC):
    provider: str = ""
    auto_create_account: bool = False

    @abstractmethod
    def build_default_account(self, user_id: int) -> AccountConnection:
        raise NotImplementedError

    @abstractmethod
    def list_positions(self, db: Session, account: AccountConnection) -> List[Any]:
        raise NotImplementedError

    @abstractmethod
    def list_trades(
        self,
        db: Session,
        account: AccountConnection,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        raise NotImplementedError

    @abstractmethod
    def get_orders(
        self,
        db: Session,
        account: AccountConnection,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        raise NotImplementedError

    @abstractmethod
    def place_order(
        self,
        db: Session,
        account: AccountConnection,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "limit",
    ) -> Any:
        raise NotImplementedError

    def cancel_order(
        self,
        db: Session,
        account: AccountConnection,
        *,
        order_id: Optional[str] = None,
        cancel_all: bool = False,
    ) -> Any:
        raise NotImplementedError("当前账户类型不支持撤单")

    def get_cash_balance(self, account: AccountConnection) -> Optional[float]:
        return account.cash_balance
