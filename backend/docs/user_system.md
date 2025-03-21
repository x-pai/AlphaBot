# 用户系统说明

## 基本规则

1. 注册规则：
   - 必须使用邀请码才能注册
   - 每个邀请码只能使用一次
   - 注册时获得初始积分120点

2. 使用限制：
   - 普通用户每天限制使用10次
   - 积分达到1000点后无使用限制
   - 每天0点重置使用次数

3. 积分规则：
   - 初始积分：120点
   - 积分只能由管理员添加
   - 1000积分可解锁无限制使用

## API 使用说明

### 1. 用户注册
```http
POST /api/users/register
{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "invite_code": "ABC123"  // 必填
}
```

### 2. 查看个人信息
```http
GET /api/users/me

响应：
{
    "username": "testuser",
    "points": 120,
    "daily_usage_count": 5,
    "daily_limit": 10,
    "is_unlimited": false
}
```

### 3. 检查是否可以使用服务
```http
GET /api/users/check-usage

响应：
{
    "can_use": true  // 或 false
}
```

### 4. 管理员功能

#### 生成邀请码
```http
POST /api/users/invite-codes

响应：
"ABC123"  // 新生成的邀请码
```

#### 添加用户积分
```http
POST /api/users/points/{user_id}?points=100

响应：
{
    "success": true,
    "new_points": 220
}
```

## 使用流程

1. 获取邀请码：
   - 联系管理员获取邀请码
   - 每个邀请码只能使用一次

2. 注册账号：
   - 使用邀请码注册
   - 获得初始120积分

3. 使用服务：
   - 每天可使用10次
   - 积分达到1000点后无限制

4. 获取更多积分：
   - 联系管理员获取积分
   - 达到1000积分后解锁无限制使用

## 注意事项

1. 邀请码管理：
   - 邀请码不可重复使用
   - 只有管理员可以生成邀请码
   - 请妥善保管邀请码

2. 积分管理：
   - 积分只能由管理员添加
   - 积分不会自动增加
   - 积分达到1000点是一个重要门槛

3. 使用限制：
   - 每天使用次数在0点重置
   - 请合理规划使用次数
   - 建议累积到1000积分以获得最佳体验 