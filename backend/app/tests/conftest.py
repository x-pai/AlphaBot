"""
Pytest 公共 fixture：测试数据库、测试用户、认证头

对应 docs/ROADMAP.md 中 Phase 0–3 已完成功能的接口测试。
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# 测试使用内存 SQLite，避免污染开发库
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.session import Base
from app.main import app
from app.db.session import get_db
from app.models.user import User, InviteCode
from app.models.stock import Stock
from app.services.user_service import UserService


# ---------- 测试数据库 ----------
# StaticPool 使所有会话共享同一连接，避免 SQLite :memory: 每连接独立库导致 “no such table”
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def get_test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def db_engine():
    """会话级：创建所有表"""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield TEST_ENGINE
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db(db_engine):
    """每个测试一个会话，测试后回滚"""
    conn = TEST_ENGINE.connect()
    trans = conn.begin()
    session = TestSessionLocal(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


# ---------- 测试用户与认证 ----------
TEST_USERNAME = "testuser"
TEST_EMAIL = "test@alphabot.test"
TEST_PASSWORD = "testpass"
TEST_INVITE_CODE = "TESTCODE1"


@pytest.fixture
def test_user(db):
    """创建测试用户（高积分避免用量限制），并预置邀请码"""
    invite = db.query(InviteCode).filter(InviteCode.code == TEST_INVITE_CODE).first()
    if not invite:
        invite = InviteCode(code=TEST_INVITE_CODE, used=False)
        db.add(invite)
        db.flush()
    user = db.query(User).filter(User.username == TEST_USERNAME).first()
    if not user:
        user = User(
            username=TEST_USERNAME,
            email=TEST_EMAIL,
            hashed_password=UserService.get_password_hash(TEST_PASSWORD),
            points=2000,  # 视为无限用量
        )
        db.add(user)
        db.flush()
        invite.used = True
        invite.used_by = user.id
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Bearer token 请求头"""
    token = UserService.create_access_token({"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}


# ---------- 测试客户端 ----------
@pytest.fixture
def client():
    """覆盖 get_db 为测试库的 FastAPI TestClient"""
    app.dependency_overrides[get_db] = get_test_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def authenticated_client(client, test_user, auth_headers):
    """已登录的客户端：client + test_user 已写入 DB，请求带 auth_headers"""
    return client, auth_headers
