from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from database import SessionLocal
from models import ChatMessage, User
from auth import get_current_user

router = APIRouter(prefix="/chat", tags=["Чат"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def role_of(user):
    if isinstance(user, str):
        return user
    if hasattr(user, 'role'):
        return user.role
    if isinstance(user, dict):
        return user.get("role")
    return None


def phone_of(user):
    if isinstance(user, str):
        return None
    if hasattr(user, 'phone'):
        return user.phone
    if isinstance(user, dict):
        return user.get("phone")
    return None


class SendMessage(BaseModel):
    order_code: int
    message: str


@router.post("/send")
def send_message(
    data: SendMessage,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Отправить сообщение"""
    phone = phone_of(user)
    role = role_of(user)
    
    if not phone or not role:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    new_message = ChatMessage(
        order_code=data.order_code,
        sender_phone=phone,
        sender_role=role,
        message=data.message,
        is_read=False
    )
    
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    return {
        "message": "Сообщение отправлено",
        "data": {
            "id": new_message.id,
            "order_code": new_message.order_code,
            "sender_phone": new_message.sender_phone,
            "sender_role": new_message.sender_role,
            "message": new_message.message,
            "created_at": (new_message.created_at + timedelta(hours=5)).isoformat()
        }
    }


@router.get("/{order_code}")
def get_messages(
    order_code: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить сообщения чата"""
    messages = db.query(ChatMessage).filter(
        ChatMessage.order_code == order_code
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # Отмечаем как прочитанные
    phone = phone_of(user)
    for m in messages:
        if m.sender_phone != phone:
            m.is_read = True
    db.commit()
    
    return [
        {
            "id": m.id,
            "sender_phone": m.sender_phone,
            "sender_role": m.sender_role,
            "message": m.message,
            "is_read": m.is_read,
            "created_at": (m.created_at + timedelta(hours=5)).isoformat() if m.created_at else None,
            "is_mine": m.sender_phone == phone
        }
        for m in messages
    ]