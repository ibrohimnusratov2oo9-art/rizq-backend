from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from database import SessionLocal
from models import Seller, Product, User, Order
from auth import get_current_user

router = APIRouter(prefix="/sellers", tags=["Продавцы"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================== SCHEMAS ==================
class SellerCreate(BaseModel):
    name: str
    seller_type: str
    address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class SellerUpdate(BaseModel):
    name: Optional[str] = None
    seller_type: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    logo_url: Optional[str] = None
    phone_public: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_active: Optional[bool] = None


class WorkingHoursUpdate(BaseModel):
    working_hours: Dict[str, Any]


class ToggleStatus(BaseModel):
    is_open: bool


# ================== СОЗДАТЬ РЕСТОРАН ==================
@router.post("/create")
def create_seller(
    data: SellerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец может создать ресторан")

    existing = db.query(Seller).filter(Seller.phone == current_user.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="У вас уже есть ресторан")

    if data.seller_type not in ["restaurant", "cafe", "fastfood", "dessert"]:
        raise HTTPException(status_code=400, detail="Тип должен быть: restaurant, cafe, fastfood, dessert")

    # Дефолтные часы работы (все дни 09:00-23:00)
    default_hours = {
        "mon": {"open": "09:00", "close": "23:00", "is_open": True},
        "tue": {"open": "09:00", "close": "23:00", "is_open": True},
        "wed": {"open": "09:00", "close": "23:00", "is_open": True},
        "thu": {"open": "09:00", "close": "23:00", "is_open": True},
        "fri": {"open": "09:00", "close": "23:00", "is_open": True},
        "sat": {"open": "09:00", "close": "23:00", "is_open": True},
        "sun": {"open": "09:00", "close": "23:00", "is_open": True},
    }

    new_seller = Seller(
        phone=current_user.phone,
        name=data.name,
        seller_type=data.seller_type,
        address=data.address,
        description=data.description,
        image_url=data.image_url,
        lat=data.lat,
        lng=data.lng,
        working_hours=default_hours,
        is_active=True,
        is_open=True,
    )

    db.add(new_seller)
    db.commit()
    db.refresh(new_seller)

    return {
        "message": "✅ Ресторан создан!",
        "seller_id": new_seller.id,
        "name": new_seller.name,
    }


# ================== СПИСОК ВСЕХ РЕСТОРАНОВ ==================
@router.get("/")
def list_sellers(
    seller_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Seller).filter(Seller.is_active == True)

    if seller_type:
        query = query.filter(Seller.seller_type == seller_type)

    sellers = query.all()

    return [
        {
            "id": s.id,
            "phone": s.phone,
            "name": s.name,
            "seller_type": s.seller_type,
            "address": s.address,
            "description": s.description,
            "image_url": s.image_url,
            "logo_url": s.logo_url,
            "phone_public": s.phone_public,
            "lat": s.lat,
            "lng": s.lng,
            "is_active": s.is_active,
            "is_open": s.is_open,
            "rating": s.rating,
            "reviews_count": s.reviews_count,
            "working_hours": s.working_hours,
            "created_at": s.created_at + timedelta(hours=5)
        }
        for s in sellers
    ]


# ================== ПОЛУЧИТЬ РЕСТОРАН ПО ID ==================
@router.get("/{seller_id}")
def get_seller(seller_id: int, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    products = db.query(Product).filter(
        Product.seller_phone == seller.phone,
        Product.is_available == True
    ).all()

    return {
        "id": seller.id,
        "phone": seller.phone,
        "name": seller.name,
        "seller_type": seller.seller_type,
        "address": seller.address,
        "description": seller.description,
        "image_url": seller.image_url,
        "logo_url": seller.logo_url,
        "phone_public": seller.phone_public,
        "lat": seller.lat,
        "lng": seller.lng,
        "is_active": seller.is_active,
        "is_open": seller.is_open,
        "rating": seller.rating,
        "reviews_count": seller.reviews_count,
        "working_hours": seller.working_hours,
        "products_count": len(products),
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "description": p.description,
                "category": p.category,
                "image_url": p.image_url,
                "is_available": p.is_available
            }
            for p in products
        ]
    }


# ================== МОЙ РЕСТОРАН (для seller) ==================
@router.get("/my/restaurant")
def my_restaurant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()

    if not seller:
        return {
            "has_restaurant": False,
            "message": "У вас нет ресторана. Создайте его!"
        }

    products = db.query(Product).filter(Product.seller_phone == seller.phone).all()

    return {
        "has_restaurant": True,
        "seller": {
            "id": seller.id,
            "phone": seller.phone,
            "name": seller.name,
            "seller_type": seller.seller_type,
            "address": seller.address,
            "description": seller.description,
            "image_url": seller.image_url,
            "logo_url": seller.logo_url,
            "phone_public": seller.phone_public,
            "lat": seller.lat,
            "lng": seller.lng,
            "is_active": seller.is_active,
            "is_open": seller.is_open,
            "rating": seller.rating,
            "reviews_count": seller.reviews_count,
            "balance": seller.balance,
            "total_earnings": seller.total_earnings,
            "working_hours": seller.working_hours,
            "products_count": len(products),
            "created_at": seller.created_at + timedelta(hours=5)
        }
    }


# ================== ОБНОВИТЬ РЕСТОРАН ==================
@router.put("/update")
def update_seller(
    data: SellerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    if data.name is not None:
        seller.name = data.name
    if data.seller_type is not None:
        if data.seller_type not in ["restaurant", "cafe", "fastfood", "dessert"]:
            raise HTTPException(status_code=400, detail="Неверный тип")
        seller.seller_type = data.seller_type
    if data.address is not None:
        seller.address = data.address
    if data.description is not None:
        seller.description = data.description
    if data.image_url is not None:
        seller.image_url = data.image_url
    if data.logo_url is not None:
        seller.logo_url = data.logo_url
    if data.phone_public is not None:
        seller.phone_public = data.phone_public
    if data.lat is not None:
        seller.lat = data.lat
    if data.lng is not None:
        seller.lng = data.lng
    if data.is_active is not None:
        seller.is_active = data.is_active

    db.commit()
    db.refresh(seller)

    return {
        "message": "✅ Ресторан обновлён",
        "seller_id": seller.id,
    }


# ================== БЫСТРОЕ ПЕРЕКЛЮЧЕНИЕ ОТКРЫТО/ЗАКРЫТО ==================
@router.post("/me/toggle-status")
def toggle_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Переключить статус: открыто <-> закрыто"""
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    seller.is_open = not seller.is_open
    db.commit()

    return {
        "message": "🟢 Открыто" if seller.is_open else "🔴 Закрыто",
        "is_open": seller.is_open,
    }


# ================== ОБНОВИТЬ ЧАСЫ РАБОТЫ ==================
@router.post("/me/update-hours")
def update_working_hours(
    data: WorkingHoursUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Обновить часы работы для каждого дня недели.
    
    Формат:
    {
        "mon": {"open": "09:00", "close": "23:00", "is_open": true},
        "tue": {"open": "09:00", "close": "23:00", "is_open": true},
        "wed": {"open": "09:00", "close": "23:00", "is_open": true},
        "thu": {"open": "09:00", "close": "23:00", "is_open": true},
        "fri": {"open": "09:00", "close": "23:00", "is_open": true},
        "sat": {"open": "10:00", "close": "02:00", "is_open": true},
        "sun": {"open": "00:00", "close": "00:00", "is_open": false}
    }
    """
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    valid_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    for day in data.working_hours.keys():
        if day not in valid_days:
            raise HTTPException(status_code=400, detail=f"Неверный день: {day}")

    seller.working_hours = data.working_hours
    db.commit()

    return {
        "message": "✅ Часы работы обновлены",
        "working_hours": seller.working_hours,
    }


# ================== ПОЛУЧИТЬ БАЛАНС И ФИНАНСЫ ==================
@router.get("/me/balance")
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить баланс и финансовую статистику"""
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    # Считаем доходы за периоды
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    all_orders = db.query(Order).filter(
        Order.seller_phone == current_user.phone,
        Order.status.in_(["доставлен", "completed"])
    ).all()

    total_earnings = 0
    today_earnings = 0
    week_earnings = 0
    month_earnings = 0
    total_orders = len(all_orders)

    for order in all_orders:
        price = order.total_price or 0
        total_earnings += price

        if order.created_at >= today_start:
            today_earnings += price
        if order.created_at >= week_start:
            week_earnings += price
        if order.created_at >= month_start:
            month_earnings += price

    return {
        "balance": seller.balance,
        "total_earnings": total_earnings,
        "today_earnings": today_earnings,
        "week_earnings": week_earnings,
        "month_earnings": month_earnings,
        "total_orders": total_orders,
    }


# ================== УДАЛИТЬ РЕСТОРАН (admin) ==================
@router.delete("/{seller_id}")
def delete_seller(
    seller_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Только админ")

    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    db.delete(seller)
    db.commit()

    return {"message": "Ресторан удалён"}