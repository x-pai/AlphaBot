from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class AlertRuleCreate(BaseModel):
    """创建预警规则"""
    symbol: str
    rule_type: str  # price_change_pct | price_vs_ma | volume_spike
    params: Optional[Dict[str, Any]] = None
    enabled: bool = True


class AlertRuleOut(BaseModel):
    id: int
    user_id: int
    symbol: str
    rule_type: str
    params_json: Optional[str] = None
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertTriggerOut(BaseModel):
    id: int
    alert_rule_id: int
    user_id: int
    symbol: str
    triggered_at: datetime
    message: Optional[str] = None
    is_read: bool

    model_config = ConfigDict(from_attributes=True)
