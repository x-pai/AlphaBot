"""
Phase 6 T6.3: 模拟交易 — 虚拟资金 + 实盘行情，不触碰实盘持仓。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.sim_portfolio import SimAccount, SimPosition


class SimTradeService:
    """模拟交易：仅操作 sim_accounts 与 sim_positions。"""

    @staticmethod
    def get_or_create_account(db: Session, user_id: int) -> SimAccount:
        acc = db.query(SimAccount).filter(SimAccount.user_id == user_id).first()
        if not acc:
            acc = SimAccount(user_id=user_id, cash_balance=1_000_000.0)
            db.add(acc)
            db.flush()
        return acc

    @staticmethod
    def get_positions(db: Session, user_id: int) -> List[SimPosition]:
        return (
            db.query(SimPosition)
            .filter(SimPosition.user_id == user_id)
            .all()
        )

    @staticmethod
    def add_trade(
        db: Session,
        user_id: int,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Dict[str, Any]:
        """下单：买则扣现金、加持仓；卖则减持仓、加现金。"""
        acc = SimTradeService.get_or_create_account(db, user_id)
        symbol = (symbol or "").strip().upper()
        quantity = float(quantity)
        price = float(price)
        if quantity <= 0:
            return {"success": False, "error": "数量必须大于 0"}

        if side.lower() == "buy":
            cost = quantity * price
            if acc.cash_balance < cost:
                return {"success": False, "error": f"资金不足，需 {cost:.2f}"}
            acc.cash_balance -= cost
            pos = (
                db.query(SimPosition)
                .filter(SimPosition.user_id == user_id, SimPosition.symbol == symbol)
                .first()
            )
            if pos:
                total_cost = pos.cost_price * pos.quantity + cost
                pos.quantity += quantity
                pos.cost_price = total_cost / pos.quantity
            else:
                pos = SimPosition(
                    user_id=user_id,
                    symbol=symbol,
                    quantity=quantity,
                    cost_price=price,
                )
                db.add(pos)
            db.flush()
            return {
                "success": True,
                "message": "模拟买入成功",
                "cash_balance": acc.cash_balance,
                "position": {"symbol": symbol, "quantity": pos.quantity, "cost_price": pos.cost_price},
            }
        elif side.lower() == "sell":
            pos = (
                db.query(SimPosition)
                .filter(SimPosition.user_id == user_id, SimPosition.symbol == symbol)
                .first()
            )
            if not pos or pos.quantity < quantity:
                return {"success": False, "error": "持仓不足"}
            acc.cash_balance += quantity * price
            pos.quantity -= quantity
            if pos.quantity <= 1e-8:
                db.delete(pos)
            db.flush()
            return {
                "success": True,
                "message": "模拟卖出成功",
                "cash_balance": acc.cash_balance,
            }
        return {"success": False, "error": "side 须为 buy 或 sell"}
