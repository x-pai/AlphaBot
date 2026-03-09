from fastapi import APIRouter, Depends, HTTPException, status, Security, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional, List

from app.db.session import get_db
from app.services.user_service import UserService
from app.services.stock_service import StockService
from app.services.invite_service import InviteService
from app.schemas.user import UserCreate, UserInfo, Token, InviteCodeResponse
from app.schemas.stock import SavedStockCreate
from app.schemas.portfolio import PositionCreate, TradeIn, PositionOut, TradeOut
from app.schemas.alert import AlertRuleCreate, AlertRuleOut, AlertTriggerOut
from app.models.user import User
from app.services.portfolio_service import PositionService, TradeLogService
from app.services.alert_service import AlertService
from app.utils.response import api_response

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/token")

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    return await UserService.get_current_user(db, token)

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges"
        )
    return current_user

@router.post("/register", response_model=dict)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """用户注册"""
    try:
        user = await UserService.register_user(
            db,
            user_data.username,
            user_data.email,
            user_data.password,
            user_data.invite_code
        )
        return api_response(data={"username": user.username})
    except HTTPException as e:
        return api_response(success=False, error=str(e.detail))

@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录"""
    user = await UserService.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = UserService.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=dict)
async def get_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取个人信息"""
    try:
        user_info = UserInfo(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            points=current_user.points,
            daily_usage_count=current_user.daily_usage_count,
            daily_limit=current_user.daily_limit,
            is_unlimited=current_user.is_unlimited,
            is_admin=current_user.is_admin,
            created_at=current_user.created_at,
            last_reset_at=current_user.last_reset_at
        )
        return api_response(data=user_info.model_dump())
    except Exception as e:
        return api_response(success=False, error=str(e))

@router.get("/check-usage")
async def check_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查是否可以使用服务"""
    can_use = await UserService.check_user_usage(current_user, db)
    return api_response(data={"can_use": can_use})

@router.post("/invite-codes")
async def generate_invite_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """生成邀请码（仅管理员）"""
    try:
        code = InviteService.generate_invite_code(db)
        return api_response(data=code)
    except HTTPException as e:
        return api_response(success=False, error=str(e.detail))

@router.get("/invite-codes", response_model=dict)
async def list_invite_codes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """获取邀请码列表（仅管理员）"""
    try:
        codes = InviteService.get_invite_codes(db)
        response_codes = []
        for code in codes:
            response_code = InviteCodeResponse(
                code=code.code,
                used=code.used,
                used_by=db.query(User.username).filter(User.id == code.used_by).scalar() if code.used_by else None,
                used_at=code.used_at,
                created_at=code.created_at
            )
            response_codes.append(response_code)
        return api_response(data=[code.model_dump() for code in response_codes])
    except HTTPException as e:
        return api_response(success=False, error=str(e.detail))

@router.post("/points/{user_id}")
async def add_user_points(
    user_id: int,
    points: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """添加用户积分（仅管理员）"""
    success = await UserService.add_points(db, user_id, points)
    if not success:
        return api_response(success=False, error="User not found")
    return api_response()

@router.get("/saved-stocks", response_model=dict)
async def get_saved_stocks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户保存的股票列表"""
    try:
        saved_stocks = await StockService.get_saved_stocks(db, current_user.id)
        return api_response(data=saved_stocks)
    except Exception as e:
        return api_response(success=False, error=f"获取收藏股票失败: {str(e)}")

@router.post("/saved-stocks", response_model=dict)
async def save_stock(
    stock_data: SavedStockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存股票到收藏夹"""
    try:
        saved_stock = await StockService.save_stock_to_db(
            db,
            current_user.id,
            stock_data.symbol,
            stock_data.notes
        )
        if not saved_stock:
            return api_response(success=False, error="保存股票失败")
        return api_response(data=saved_stock)
    except Exception as e:
        return api_response(success=False, error=f"保存股票失败: {str(e)}")

# ---------- 持仓与交易（个人数据底座） ----------

@router.get("/positions", response_model=dict)
async def get_positions(
    data_source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户持仓列表（含当前价与浮盈浮亏）"""
    try:
        rows = await PositionService.get_positions_with_pnl(
            db, current_user.id, data_source
        )
        return api_response(data=rows)
    except Exception as e:
        return api_response(success=False, error=str(e))

@router.post("/positions", response_model=dict)
async def create_or_update_position(
    body: PositionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """直接录入/覆盖单只持仓（不记交易流水）"""
    try:
        pos = PositionService.set_position(
            db,
            user_id=current_user.id,
            symbol=body.symbol,
            quantity=body.quantity,
            cost_price=body.cost_price,
            currency=body.currency,
            source=body.source,
        )
        db.commit()
        if pos is None:
            return api_response(data={"message": "已清除该持仓"})
        db.refresh(pos)
        return api_response(data=PositionOut.model_validate(pos))
    except ValueError as e:
        return api_response(success=False, error=str(e))
    except Exception as e:
        db.rollback()
        return api_response(success=False, error=str(e))

@router.get("/trades", response_model=dict)
async def list_trades(
    symbol: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户交易记录"""
    try:
        trades = TradeLogService.list_trades(
            db, user_id=current_user.id, symbol=symbol, limit=limit
        )
        return api_response(data=[TradeOut.model_validate(t) for t in trades])
    except Exception as e:
        return api_response(success=False, error=str(e))

@router.post("/trades", response_model=dict)
async def add_trade(
    body: TradeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """记录一笔买入或卖出，并自动更新持仓"""
    try:
        trade = TradeLogService.add_trade(
            db,
            user_id=current_user.id,
            symbol=body.symbol,
            side=body.side,
            quantity=body.quantity,
            price=body.price,
            fee=body.fee or 0.0,
            trade_time=body.trade_time,
            source=body.source,
        )
        return api_response(data=TradeOut.model_validate(trade))
    except ValueError as e:
        return api_response(success=False, error=str(e))
    except Exception as e:
        db.rollback()
        return api_response(success=False, error=str(e))

@router.get("/portfolio/summary", response_model=dict)
async def get_portfolio_summary(
    data_source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """组合总览：总成本、总市值、总浮盈浮亏"""
    try:
        summary = await PositionService.get_portfolio_summary(
            db, current_user.id, data_source
        )
        return api_response(data=summary)
    except Exception as e:
        return api_response(success=False, error=str(e))

@router.get("/portfolio/health", response_model=dict)
async def get_portfolio_health(
    data_source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """组合体检：趋势/估值标签与简短点评（Phase 3）"""
    try:
        health = await PositionService.get_portfolio_health(
            db, current_user.id, data_source
        )
        return api_response(data=health)
    except Exception as e:
        return api_response(success=False, error=str(e))

# ---------- 预警规则（Phase 2） ----------

@router.get("/alerts", response_model=dict)
async def list_alerts(
    symbol: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的预警规则列表"""
    try:
        rules = AlertService.list_rules(db, current_user.id, symbol)
        return api_response(data=[AlertRuleOut.model_validate(r) for r in rules])
    except Exception as e:
        return api_response(success=False, error=str(e))

@router.post("/alerts", response_model=dict)
async def create_alert(
    body: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建一条预警规则"""
    try:
        rule = AlertService.create_rule(
            db,
            user_id=current_user.id,
            symbol=body.symbol.strip().upper(),
            rule_type=body.rule_type,
            params=body.params,
            enabled=body.enabled,
        )
        return api_response(data=AlertRuleOut.model_validate(rule))
    except ValueError as e:
        return api_response(success=False, error=str(e))
    except Exception as e:
        db.rollback()
        return api_response(success=False, error=str(e))

@router.delete("/alerts/{rule_id}", response_model=dict)
async def delete_alert(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除一条预警规则"""
    try:
        ok = AlertService.delete_rule(db, rule_id, current_user.id)
        if not ok:
            return api_response(success=False, error="规则不存在或无权操作")
        return api_response(data={"message": "已删除"})
    except Exception as e:
        return api_response(success=False, error=str(e))

@router.get("/alerts/triggers/unread", response_model=dict)
async def get_unread_alert_triggers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户未读的预警触发记录（会话内会展示并标记已读）"""
    try:
        triggers = AlertService.get_unread_triggers(db, current_user.id)
        return api_response(data=[AlertTriggerOut.model_validate(t) for t in triggers])
    except Exception as e:
        return api_response(success=False, error=str(e))

# ---------- 收藏股票 ----------

@router.delete("/saved-stocks/{symbol}", response_model=dict)
async def delete_saved_stock(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从收藏夹中删除股票"""
    try:
        success = await StockService.delete_saved_stock(db, current_user.id, symbol)
        if not success:
            return api_response(success=False, error="删除股票失败")
        return api_response()
    except Exception as e:
        return api_response(success=False, error=f"删除股票失败: {str(e)}")

@router.post("/logout", response_model=dict)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """用户退出登录"""
    try:
        # 这里可以添加一些清理逻辑，比如：
        # - 清除用户的会话
        # - 记录退出日志
        # - 更新用户的最后活动时间等
        
        return api_response(data={"message": "退出登录成功"})
    except Exception as e:
        return api_response(success=False, error=f"退出登录失败: {str(e)}")

@router.post("/change-password", response_model=dict)
async def change_password(
    old_password: str = Body(...),
    new_password: str = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    try:
        await UserService.change_password(db, current_user, old_password, new_password)
        return api_response(data={"message": "密码修改成功"})
    except HTTPException as e:
        return api_response(success=False, error=str(e.detail))
    except Exception as e:
        return api_response(success=False, error=str(e)) 