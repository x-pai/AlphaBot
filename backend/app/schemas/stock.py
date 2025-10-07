from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# 股票基本信息模型
class StockBase(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str] = None
    currency: Optional[str] = None

class StockCreate(StockBase):
    pass

class StockInfo(StockBase):
    price: Optional[float] = None
    change: Optional[float] = None
    changePercent: Optional[float] = None
    marketCap: Optional[float] = None
    marketStatus: Optional[str] = None
    volume: Optional[int] = None
    pe: Optional[float] = None
    dividend: Optional[float] = None
    
    class Config:
        from_attributes = True

# 股票价格历史数据点
class StockPricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

# 股票历史价格数据
class StockPriceHistory(BaseModel):
    symbol: str
    data: List[StockPricePoint]

# AI分析结果
class AIAnalysis(BaseModel):
    summary: str
    sentiment: str = Field(..., description="positive, neutral, negative")
    keyPoints: List[str]
    recommendation: str
    riskLevel: str = Field(..., description="low, medium, high")
    analysisType: Optional[str] = Field(None, description="rule, ml, llm")

# 用户保存的股票
class SavedStockBase(BaseModel):
    symbol: str = Field(..., description="股票代码")
    notes: Optional[str] = Field(None, description="用户备注")

class SavedStockCreate(SavedStockBase):
    pass

class SavedStock(SavedStockBase):
    id: int = Field(..., description="收藏记录ID")
    stock_id: int = Field(..., description="股票ID")
    user_id: int = Field(..., description="用户ID")
    added_at: datetime = Field(..., description="添加时间")
    stock: StockBase = Field(..., description="股票基本信息")

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    def dict(self, *args, **kwargs):
        # 确保返回的数据格式与前端一致
        data = super().dict(*args, **kwargs)
        if isinstance(data['added_at'], datetime):
            data['added_at'] = data['added_at'].isoformat()
        return data

# API响应
class ApiResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None 