from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import secrets
import string
from app.models.user import InviteCode, User

class InviteService:
    @staticmethod
    def generate_invite_code(db: Session) -> str:
        """生成新的邀请码"""
        while True:
            # 生成8位随机邀请码
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not db.query(InviteCode).filter(InviteCode.code == code).first():
                invite_code = InviteCode(code=code)
                db.add(invite_code)
                try:
                    db.commit()
                    return code
                except Exception as e:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="生成邀请码失败"
                    )

    @staticmethod
    def get_invite_codes(db: Session) -> List[InviteCode]:
        """获取所有邀请码"""
        try:
            return db.query(InviteCode).order_by(InviteCode.created_at.desc()).all()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取邀请码列表失败"
            )

    @staticmethod
    def verify_invite_code(db: Session, code: str) -> bool:
        """验证邀请码是否有效"""
        invite = db.query(InviteCode).filter(
            InviteCode.code == code,
            InviteCode.used == False
        ).first()
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效或已使用的邀请码"
            )
        return True

    @staticmethod
    def mark_invite_code_used(db: Session, code: str, user_id: int) -> None:
        """标记邀请码为已使用"""
        invite = db.query(InviteCode).filter(InviteCode.code == code).first()
        if invite:
            invite.used = True
            invite.used_by = user_id
            invite.used_at = datetime.utcnow()
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="更新邀请码状态失败"
                )

    @staticmethod
    def get_invite_code_details(db: Session, code: str) -> Optional[InviteCode]:
        """获取邀请码详细信息"""
        try:
            return db.query(InviteCode).filter(InviteCode.code == code).first()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取邀请码详情失败"
            )
