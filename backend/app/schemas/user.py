from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    invite_code: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserInDB(UserBase):
    id: int
    points: int
    daily_usage_count: int
    is_admin: bool
    created_at: datetime
    last_reset_at: datetime

    class Config:
        from_attributes = True

class UserInfo(BaseModel):
    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    email: EmailStr = Field(description="邮箱")
    points: int = Field(ge=0, description="用户积分")
    daily_usage_count: int = Field(ge=0, description="每日使用次数")
    daily_limit: int = Field(ge=0, le=999999, description="每日使用限制")
    is_unlimited: bool = Field(description="是否无限制使用")
    is_admin: bool = Field(description="是否是管理员")
    created_at: datetime = Field(description="创建时间")
    last_reset_at: datetime = Field(description="上次重置时间")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

class InviteCodeResponse(BaseModel):
    code: str
    used: bool
    used_by: Optional[str] = None
    used_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        } 