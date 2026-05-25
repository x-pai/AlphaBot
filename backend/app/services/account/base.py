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
    def add_trade(
        self,
        db: Session,
        account: AccountConnection,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        source: str = "",
        trade_time: Any = None,
    ) -> Any:
        raise NotImplementedError

    def set_position(
        self,
        db: Session,
        account: AccountConnection,
        *,
        symbol: str,
        quantity: float,
        cost_price: float,
        currency: Optional[str] = None,
        source: str = "broker",
    ) -> Any:
        raise NotImplementedError("当前账户类型不支持直接设置持仓")

    def import_trades(
        self,
        db: Session,
        account: AccountConnection,
        *,
        csv_text: str,
        source: str = "import",
    ) -> Dict[str, Any]:
        raise NotImplementedError("当前账户类型不支持导入交易")

    def get_cash_balance(self, account: AccountConnection) -> Optional[float]:
        return account.cash_balance
