from app.services.account.base import AccountConnector
from app.services.account.connectors.qmt import QMTAccountConnector
from app.services.account.connectors.ths import THSAccountConnector


class AccountConnectorRegistry:
    _connectors: dict[str, AccountConnector] = {
        "ths": THSAccountConnector(),
        "qmt": QMTAccountConnector(),
    }

    @classmethod
    def get(cls, provider: str) -> AccountConnector:
        connector = cls._connectors.get((provider or "").strip().lower())
        if connector is None:
            raise ValueError(f"未知账户 provider: {provider}")
        return connector
