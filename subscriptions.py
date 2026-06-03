from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel

from database import SessionLocal
from models import User, Subscription
from auth import get_current_user

router = APIRouter(prefix="/subscriptions", tags=["Подписки"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================== SCHEMAS ==================
class SubscribeRequest(BaseModel):
    subscription_type: str  # "plus" или "premium"


# ================== ЦЕНЫ ==================
SUBSCRIPTION_PRICES = {
    "plus": {
        "price": 80,
        "free_deliveries": 5,
        "discount_percent": 5,
        "name": "RIZQ+ Plus"
    },
    "premium": {
        "price": 150,
        "free_deliveries": 15,
        "discount_percent": 10,
        "name": "RIZQ+ Premium"
    }
}


# ================== ПОДПИСАТЬСЯ ==================
@router.post("/subscribe")
def subscribe(
    data: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Купить подписку"""
    
    if data.subscription_type not in SUBSCRIPTION_PRICES:
        raise HTTPException(status_code=400, detail="Неверный тип подписки")
    
    sub_info = SUBSCRIPTION_PRICES[data.subscription_type]
    
    # Создаём подписку на 30 дней
    new_subscription = Subscription(
        user_phone=current_user.phone,
        subscription_type=data.subscription_type,
        price=sub_info["price"],
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        is_active=True,
        free_deliveries_used=0,
        free_deliveries_limit=sub_info["free_deliveries"]
    )
    
    db.add(new_subscription)
    
    # Обновляем пользователя
    current_user.subscription_type = data.subscription_type
    current_user.subscription_expires = new_subscription.end_date
    current_user.free_deliveries_used = 0
    
    db.commit()
    db.refresh(new_subscription)
    
    return {
        "message": f"Подписка {sub_info['name']} активирована! 🎉",
        "subscription_type": data.subscription_type,
        "price": sub_info["price"],
        "free_deliveries": sub_info["free_deliveries"],
        "discount_percent": sub_info["discount_percent"],
        "expires_at": new_subscription.end_date,
        "days_remaining": 30
    }


# ================== МОЯ ПОДПИСКА ==================
@router.get("/my")
def my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить свою подписку"""
    
    if not current_user.subscription_type or current_user.subscription_type == "none":
        return {
            "has_subscription": False,
            "message": "У вас нет активной подписки"
        }
    
    # Проверяем не истекла ли
    if current_user.subscription_expires and datetime.utcnow() > current_user.subscription_expires:
        current_user.subscription_type = "none"
        db.commit()
        return {
            "has_subscription": False,
            "message": "Подписка истекла"
        }
    
    sub_info = SUBSCRIPTION_PRICES.get(current_user.subscription_type)
    days_remaining = (current_user.subscription_expires - datetime.utcnow()).days
    
    return {
        "has_subscription": True,
        "subscription_type": current_user.subscription_type,
        "name": sub_info["name"],
        "price": sub_info["price"],
        "discount_percent": sub_info["discount_percent"],
        "free_deliveries_total": sub_info["free_deliveries"],
        "free_deliveries_used": current_user.free_deliveries_used,
        "free_deliveries_remaining": sub_info["free_deliveries"] - current_user.free_deliveries_used,
        "expires_at": current_user.subscription_expires,
        "days_remaining": max(0, days_remaining)
    }


# ================== ИНФО О ВСЕХ ПОДПИСКАХ ==================
@router.get("/info")
def subscription_info():
    """Информация о всех подписках"""
    return {
        "subscriptions": [
            {
                "type": "plus",
                "name": "RIZQ+ Plus",
                "price": 80,
                "currency": "сомони",
                "duration_days": 30,
                "benefits": [
                    "5 бесплатных доставок в месяц",
                    "Скидка 5% на все заказы",
                    "Без Service Fee"
                ]
            },
            {
                "type": "premium",
                "name": "RIZQ+ Premium",
                "price": 150,
                "currency": "сомони",
                "duration_days": 30,
                "benefits": [
                    "15 бесплатных доставок в месяц",
                    "Скидка 10% на все заказы",
                    "Без Service Fee",
                    "Приоритетная поддержка"
                ]
            }
        ]
    }