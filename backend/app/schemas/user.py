from pydantic import BaseModel, ConfigDict, EmailStr, Field
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

    model_config = ConfigDict(from_attributes=True)

class UserInfo(BaseModel):
    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    email: EmailStr = Field(description="邮箱")
    points: int = Field(ge=0, description="用户积分")
    daily_usage_count: int = Field(ge=0, description="每日使用次数")
    mcp_daily_usage_count: int = Field(ge=0, description="MCP每日使用次数")
    daily_limit: int = Field(ge=0, le=999999, description="每日使用限制")
    mcp_daily_limit: int = Field(ge=0, le=999999, description="MCP每日使用限制")
    is_unlimited: bool = Field(description="是否无限制使用")
    can_use_mcp: bool = Field(description="是否可使用MCP")
    is_admin: bool = Field(description="是否是管理员")
    created_at: datetime = Field(description="创建时间")
    last_reset_at: datetime = Field(description="上次重置时间")
    mcp_last_reset_at: datetime = Field(description="上次重置MCP使用时间")

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)


class McpTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="Token名称")
    expires_at: Optional[datetime] = Field(default=None, description="过期时间，可选")


class McpTokenOut(BaseModel):
    id: int
    name: str
    token_prefix: str
    is_active: bool
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    revoked_at: Optional[datetime] = None
    user_id: Optional[int] = None
    username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class McpTokenCreateResponse(BaseModel):
    token: str
    token_info: McpTokenOut
