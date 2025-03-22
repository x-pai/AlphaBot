import click
import os
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, InviteCode
from app.services.user_service import UserService
import sys

def create_admin_from_env():
    """从环境变量创建管理员账户"""
    username = os.getenv('ADMIN_USERNAME')
    email = os.getenv('ADMIN_EMAIL')
    password = os.getenv('ADMIN_PASSWORD')

    if not all([username, email, password]):
        print("错误：需要设置所有管理员环境变量 (ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD)")
        return

    db = SessionLocal()
    try:
        # 检查用户名是否已存在
        if db.query(User).filter(User.username == username).first():
            print(f'管理员账户已存在：{username}')
            return
            
        # 检查邮箱是否已存在
        if db.query(User).filter(User.email == email).first():
            print(f'管理员邮箱已存在：{email}')
            return

        # 创建管理员用户
        admin_user = User(
            username=username,
            email=email,
            hashed_password=UserService.get_password_hash(password),
            points=1000,
            is_admin=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f'成功创建管理员账户：{username}')
        
        # 为新管理员生成邀请码
        invite_codes = []
        for _ in range(5):
            code = UserService.generate_invite_code(db)
            invite_codes.append(code)
        
        print('\n生成的邀请码：')
        for code in invite_codes:
            print(code)
            
    except Exception as e:
        print(f'错误：{str(e)}')
        sys.exit(1)
    finally:
        db.close()

@click.command()
@click.option('--username', prompt='管理员用户名', help='管理员账户的用户名')
@click.option('--email', prompt='管理员邮箱', help='管理员账户的邮箱地址')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='管理员账户的密码')
def create_admin_cli(username: str, email: str, password: str):
    """通过命令行创建管理员账户"""
    db = SessionLocal()
    try:
        # 检查用户名是否已存在
        if db.query(User).filter(User.username == username).first():
            click.echo('错误：用户名已存在')
            sys.exit(1)
            
        # 检查邮箱是否已存在
        if db.query(User).filter(User.email == email).first():
            click.echo('错误：邮箱已存在')
            sys.exit(1)

        # 创建管理员用户
        admin_user = User(
            username=username,
            email=email,
            hashed_password=UserService.get_password_hash(password),
            points=1000,  # 给予足够的初始积分
            is_admin=True  # 设置为管理员
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        click.echo(f'成功创建管理员账户：{username}')
        
        # 为新管理员生成一些邀请码
        invite_codes = []
        for _ in range(5):
            code = UserService.generate_invite_code(db)
            invite_codes.append(code)
        
        click.echo('\n生成的邀请码：')
        for code in invite_codes:
            click.echo(code)
            
    except Exception as e:
        click.echo(f'错误：{str(e)}')
        sys.exit(1)
    finally:
        db.close()

if __name__ == '__main__':
    # 检查是否存在环境变量
    if os.getenv('ADMIN_USERNAME') and os.getenv('ADMIN_EMAIL') and os.getenv('ADMIN_PASSWORD'):
        create_admin_from_env()
    else:
        create_admin_cli()