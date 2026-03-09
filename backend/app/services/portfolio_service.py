import csv
import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.portfolio import Position, TradeLog
from app.models.stock import Stock


class PositionService:
    """持仓服务：管理用户持仓，并计算简单盈亏。"""

    @staticmethod
    def upsert_position(
        db: Session,
        *,
        user_id: int,
        symbol: str,
        quantity_delta: float,
        price: float,
        currency: Optional[str] = None,
        source: str = "manual",
    ) -> Position:
        """
        基于交易增量更新持仓：
        - buy: quantity_delta > 0，使用加权成本价
        - sell: quantity_delta < 0，减少持仓，数量不允许为负
        """
        # 先尝试找到对应的 Stock 记录（如无则为空，symbol 冗余保存）
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()

        position = (
            db.query(Position)
            .filter(Position.user_id == user_id, Position.symbol == symbol)
            .first()
        )

        if position is None:
            if quantity_delta <= 0:
                # 无持仓却卖出，直接忽略（也可以选择抛异常，看产品策略）
                raise ValueError("卖出失败：当前无持仓")

            position = Position(
                user_id=user_id,
                stock_id=stock.id if stock else None,
                symbol=symbol,
                quantity=quantity_delta,
                cost_price=price,
                currency=currency or (stock.currency if stock else None),
                source=source,
            )
            db.add(position)
            db.flush()
            return position

        new_quantity = position.quantity + quantity_delta
        if new_quantity < -1e-8:
            raise ValueError("卖出数量超过持仓数量")

        if new_quantity <= 1e-8:
            # 全部卖出，清空持仓
            db.delete(position)
            db.flush()
            return position

        # 买入：按加权成本价更新
        if quantity_delta > 0:
            total_cost = position.cost_price * position.quantity + price * quantity_delta
            position.quantity = new_quantity
            position.cost_price = total_cost / new_quantity
        else:
            # 卖出：只更新数量，不动成本价
            position.quantity = new_quantity

        if stock and not position.stock_id:
            position.stock_id = stock.id
        if currency and not position.currency:
            position.currency = currency
        position.source = source or position.source

        db.flush()
        return position

    @staticmethod
    def set_position(
        db: Session,
        *,
        user_id: int,
        symbol: str,
        quantity: float,
        cost_price: float,
        currency: Optional[str] = None,
        source: str = "manual",
    ) -> Optional[Position]:
        """直接设置或覆盖某只股票的持仓（不记交易流水）。数量为 0 则删除该持仓。"""
        if quantity < -1e-8:
            raise ValueError("持仓数量不能为负")
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        position = (
            db.query(Position)
            .filter(Position.user_id == user_id, Position.symbol == symbol)
            .first()
        )
        if quantity <= 1e-8:
            if position:
                db.delete(position)
                db.flush()
            return None
        if position is None:
            position = Position(
                user_id=user_id,
                stock_id=stock.id if stock else None,
                symbol=symbol,
                quantity=quantity,
                cost_price=cost_price,
                currency=currency or (stock.currency if stock else None),
                source=source,
            )
            db.add(position)
        else:
            position.quantity = quantity
            position.cost_price = cost_price
            if currency is not None:
                position.currency = currency
            position.source = source
        db.flush()
        return position

    @staticmethod
    def get_positions(db: Session, user_id: int) -> List[Position]:
        """获取用户全部持仓（不含盈亏计算）。"""
        return (
            db.query(Position)
            .filter(Position.user_id == user_id)
            .order_by(Position.symbol.asc())
            .all()
        )

    @staticmethod
    async def get_positions_with_pnl(
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取用户持仓并附带当前价与浮盈浮亏。
        依赖数据源获取最新价，若某只股票取价失败则 current_price/pnl 为 None。
        """
        from app.services.stock_service import StockService

        positions = PositionService.get_positions(db, user_id)
        result = []
        for pos in positions:
            row: Dict[str, Any] = {
                "id": pos.id,
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "cost_price": pos.cost_price,
                "currency": pos.currency or "",
                "source": pos.source,
                "market_value": None,
                "current_price": None,
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
            }
            try:
                info = await StockService.get_stock_info(pos.symbol, data_source)
                if info and getattr(info, "price", None) is not None:
                    price = float(info.price)
                    row["current_price"] = price
                    row["market_value"] = round(pos.quantity * price, 2)
                    cost_total = pos.quantity * pos.cost_price
                    pnl = row["market_value"] - cost_total
                    row["unrealized_pnl"] = round(pnl, 2)
                    row["unrealized_pnl_pct"] = (
                        round(pnl / cost_total * 100, 2) if cost_total else None
                    )
            except Exception:
                pass
            result.append(row)
        return result

    @staticmethod
    async def get_portfolio_summary(
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """组合总览：总成本、总市值、总浮盈浮亏、持仓列表摘要。"""
        positions_with_pnl = await PositionService.get_positions_with_pnl(
            db, user_id, data_source
        )
        total_cost = sum(p["quantity"] * p["cost_price"] for p in positions_with_pnl)
        total_market_value = sum(
            (p["market_value"] or p["quantity"] * p["cost_price"]) for p in positions_with_pnl
        )
        total_pnl = None
        total_pnl_pct = None
        if total_cost and total_market_value is not None:
            total_pnl = round(total_market_value - total_cost, 2)
            total_pnl_pct = round(total_pnl / total_cost * 100, 2)
        return {
            "total_cost": round(total_cost, 2),
            "total_market_value": round(total_market_value, 2) if total_market_value is not None else None,
            "total_unrealized_pnl": total_pnl,
            "total_unrealized_pnl_pct": total_pnl_pct,
            "positions_count": len(positions_with_pnl),
            "positions": positions_with_pnl,
        }

    @staticmethod
    async def get_portfolio_health(
        db: Session,
        user_id: int,
        data_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        组合体检：基于持仓与市值给出趋势/估值标签与简短点评（T3.4）。
        """
        summary = await PositionService.get_portfolio_summary(db, user_id, data_source)
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
            if total_cost and total_cost > 0 and total_market_value is not None:
                if (total_pnl_pct or 0) >= 5:
                    labels.append("组合浮盈")
                elif (total_pnl_pct or 0) <= -5:
                    labels.append("组合浮亏")
                else:
                    labels.append("组合盈亏平衡附近")
            # 集中度：单只市值占比
            if total_market_value and total_market_value > 0 and positions:
                max_mv = max((p.get("market_value") or p["quantity"] * p["cost_price"]) for p in positions)
                concentration = max_mv / total_market_value
                if concentration >= 0.5:
                    labels.append("单股集中度高")
                elif concentration >= 0.3:
                    labels.append("有一定集中度")
                else:
                    labels.append("分散持仓")
            if n <= 2 and n > 0:
                labels.append("持股较少")
            elif n >= 6:
                labels.append("持股较多")

        # 简短点评
        if n == 0:
            comment = "当前无持仓，可结合计划逐步建仓。"
        else:
            parts = []
            if total_pnl is not None and total_cost:
                parts.append(f"组合{'浮盈' if total_pnl >= 0 else '浮亏'} {abs(total_pnl):.2f}（{total_pnl_pct or 0:.1f}%）")
            if "单股集中度高" in labels:
                parts.append("注意单只仓位过重，可考虑分散风险。")
            if "组合浮亏" in labels and "单股集中度高" in labels:
                parts.append("建议关注重仓股基本面与仓位管理。")
            comment = "；".join(parts) if parts else "组合结构正常，可定期复盘。"

        return {
            "labels": labels,
            "comment": comment,
            "positions_count": n,
            "total_cost": total_cost,
            "total_market_value": total_market_value,
            "total_unrealized_pnl": total_pnl,
            "total_unrealized_pnl_pct": total_pnl_pct,
            "positions": positions,
        }


class TradeLogService:
    """交易流水服务：记录并查询交易。"""

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
        trade_time: Optional[datetime] = None,
        source: str = "manual",
    ) -> TradeLog:
        """新增一条交易，并同步更新持仓。"""
        if side not in {"buy", "sell"}:
            raise ValueError("side 必须是 'buy' 或 'sell'")

        amount = quantity * price
        trade = TradeLog(
            user_id=user_id,
            stock_id=None,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            amount=amount,
            fee=fee,
            trade_time=trade_time or datetime.utcnow(),
            source=source,
        )
        db.add(trade)
        db.flush()

        # 更新持仓
        quantity_delta = quantity if side == "buy" else -quantity
        PositionService.upsert_position(
            db,
            user_id=user_id,
            symbol=symbol,
            quantity_delta=quantity_delta,
            price=price,
            source=source,
        )

        # 尝试绑定 stock_id
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if stock:
            trade.stock_id = stock.id

        db.commit()
        db.refresh(trade)
        return trade

    @staticmethod
    def list_trades(
        db: Session,
        *,
        user_id: int,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[TradeLog]:
        """查询用户交易记录。"""
        q = db.query(TradeLog).filter(TradeLog.user_id == user_id)
        if symbol:
            q = q.filter(TradeLog.symbol == symbol)
        return q.order_by(TradeLog.trade_time.desc()).limit(limit).all()

    @staticmethod
    def import_from_csv(
        db: Session,
        *,
        user_id: int,
        csv_text: str,
        source: str = "import",
    ) -> Dict[str, Any]:
        """
        从 CSV 文本批量导入交易。支持表头：日期/date, 代码/symbol, 方向/side, 数量/quantity, 价格/price, 手续费/fee。
        方向可为 买/buy 或 卖/sell。
        """
        def norm(s: str) -> str:
            return (s or "").strip().lower()

        def parse_date(s: str) -> Optional[datetime]:
            if not s or not s.strip():
                return None
            s = s.strip()
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(s[:10], fmt)
                except ValueError:
                    continue
            return None

        reader = csv.reader(io.StringIO(csv_text.strip()))
        rows = list(reader)
        if not rows:
            return {"success": True, "imported": 0, "failed": 0, "errors": []}
        header = [norm(c) for c in rows[0]]
        data_rows = rows[1:]
        # 列名映射：支持中英文
        col_map = {}
        for i, h in enumerate(header):
            if h in ("date", "日期", "time", "时间"):
                col_map["trade_time"] = i
            elif h in ("symbol", "代码", "股票", "stock"):
                col_map["symbol"] = i
            elif h in ("side", "方向", "买卖", "type"):
                col_map["side"] = i
            elif h in ("quantity", "数量", "股数", "qty"):
                col_map["quantity"] = i
            elif h in ("price", "价格", "成交价"):
                col_map["price"] = i
            elif h in ("fee", "手续费", "佣金"):
                col_map["fee"] = i
        if "symbol" not in col_map or "side" not in col_map or "quantity" not in col_map or "price" not in col_map:
            return {"success": False, "imported": 0, "failed": len(data_rows), "errors": ["CSV 需包含：代码/symbol、方向/side、数量/quantity、价格/price"]}
        imported = 0
        errors: List[str] = []
        for idx, row in enumerate(data_rows):
            if len(row) <= max(col_map.values()):
                errors.append(f"第{idx+2}行列数不足")
                continue
            try:
                symbol = (row[col_map["symbol"]] or "").strip().upper()
                side_raw = (row[col_map["side"]] or "").strip().lower()
                side = "buy" if side_raw in ("买", "buy", "b", "买入") else "sell" if side_raw in ("卖", "sell", "s", "卖出") else None
                if not symbol or side not in ("buy", "sell"):
                    errors.append(f"第{idx+2}行 代码或方向无效")
                    continue
                quantity = float(re.sub(r"[^\d.]", "", row[col_map["quantity"]]) or 0)
                price = float(re.sub(r"[^\d.]", "", row[col_map["price"]]) or 0)
                fee = float(re.sub(r"[^\d.]", "", (row[col_map["fee"]] if col_map["fee"] < len(row) else "0") or "0")) if "fee" in col_map else 0.0
                trade_time = parse_date(row[col_map["trade_time"]]) if "trade_time" in col_map else None
                if quantity <= 0 or price <= 0:
                    errors.append(f"第{idx+2}行 数量或价格须为正数")
                    continue
                TradeLogService.add_trade(
                    db, user_id=user_id, symbol=symbol, side=side,
                    quantity=quantity, price=price, fee=fee, trade_time=trade_time, source=source,
                )
                imported += 1
            except Exception as e:
                errors.append(f"第{idx+2}行: {str(e)}")
        return {"success": True, "imported": imported, "failed": len(data_rows) - imported, "errors": errors}

