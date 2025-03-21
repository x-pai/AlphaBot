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
    username: str
    points: int = Field(ge=0, description="用户积分")
    daily_usage_count: int = Field(ge=0, description="每日使用次数")
    daily_limit: int = Field(ge=0, le=999999, description="每日使用限制")
    is_unlimited: bool = Field(description="是否无限制使用")

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None 