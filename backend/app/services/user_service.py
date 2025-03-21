from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.models.user import User, InviteCode
import secrets
import string

# JWT相关配置
SECRET_KEY = "your-secret-key"  # 在生产环境中应该使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def generate_invite_code(db: Session) -> str:
        while True:
            # 生成8位随机邀请码
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not db.query(InviteCode).filter(InviteCode.code == code).first():
                invite_code = InviteCode(code=code)
                db.add(invite_code)
                db.commit()
                return code

    @staticmethod
    async def register_user(db: Session, username: str, email: str, password: str, invite_code: str) -> User:
        # 检查用户名是否已存在
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已被使用"
            )

        # 检查邮箱是否已存在
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )

        # 验证邀请码
        invite = db.query(InviteCode).filter(
            InviteCode.code == invite_code,
            InviteCode.used == False
        ).first()
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效或已使用的邀请码"
            )

        # 创建用户
        db_user = User(
            username=username,
            email=email,
            hashed_password=UserService.get_password_hash(password),
            points=120  # 初始积分
        )
        db.add(db_user)
        
        # 标记邀请码为已使用
        invite.used = True
        invite.used_by = db_user.id
        invite.used_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(db_user)
            return db_user
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="注册失败，请稍后重试"
            )

    @staticmethod
    async def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        user = db.query(User).filter(User.username == username).first()
        if not user or not UserService.verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    async def get_current_user(db: Session, token: str) -> User:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception
        return user

    @staticmethod
    async def check_user_usage(user: User, db: Session) -> bool:
        # 检查是否需要重置每日使用次数
        now = datetime.utcnow()
        last_reset = user.last_reset_at.replace(tzinfo=None)
        if now.date() > last_reset.date():
            user.daily_usage_count = 0
            user.last_reset_at = now
            db.commit()

        # 检查是否可以使用服务
        if user.is_unlimited:
            return True
        
        return user.daily_usage_count < user.daily_limit

    @staticmethod
    async def increment_usage(user: User, db: Session):
        if not user.is_unlimited:
            user.daily_usage_count += 1
            db.commit()

    @staticmethod
    async def add_points(db: Session, user_id: int, points: int) -> bool:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.points += points
        db.commit()
        return True 