from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.account import AccountConnection
from app.services.account.base import AccountConnector


class QMTAccountConnector(AccountConnector):
    provider = "qmt"
    auto_create_account = False

    def build_default_account(self, user_id: int) -> AccountConnection:  # noqa: ARG002
        raise NotImplementedError("QMT 账户需要显式配置连接信息")

    def list_positions(self, db: Session, account: AccountConnection):  # noqa: ARG002
        raise NotImplementedError("QMT 接入器暂未实现")

    def list_trades(self, db: Session, account: AccountConnection, symbol=None, limit: int = 100):  # noqa: ARG002
        raise NotImplementedError("QMT 接入器暂未实现")

    def get_orders(self, db: Session, account: AccountConnection, symbol=None, limit: int = 100):  # noqa: ARG002
        raise NotImplementedError("QMT 接入器暂未实现")

    def place_order(self, db: Session, account: AccountConnection, **kwargs):  # noqa: ARG002
        raise NotImplementedError("QMT 接入器暂未实现")

    def cancel_order(self, db: Session, account: AccountConnection, **kwargs):  # noqa: ARG002
        raise NotImplementedError("QMT 接入器暂未实现")
