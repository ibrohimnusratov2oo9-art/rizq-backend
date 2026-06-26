from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from database import SessionLocal
from models import User, Seller, Product, Order, CourierBonus, CourierPayout

router = APIRouter(prefix="/admin", tags=["Admin Panel"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================== АВТОРИЗАЦИЯ АДМИНА ==================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "rizq2025admin"  # ПОМЕНЯЙ НА СВОЙ!


@router.post("/login")
def admin_login(username: str, password: str):
    """Вход для админа"""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return {
            "success": True,
            "message": "Добро пожаловать!",
            "token": "admin_token_secret"
        }
    raise HTTPException(status_code=401, detail="Неверный логин или пароль")


# ================== СТАТИСТИКА ==================
@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Общая статистика приложения"""
    
    total_users = db.query(User).count()
    total_customers = db.query(User).filter(User.role == "customer").count()
    total_sellers = db.query(User).filter(User.role == "seller").count()
    total_couriers = db.query(User).filter(User.role == "courier").count()
    
    total_restaurants = db.query(Seller).count()
    total_products = db.query(Product).count()
    total_orders = db.query(Order).count()
    
    delivered_orders = db.query(Order).filter(Order.status == "доставлен").count()
    
    total_revenue = db.query(func.sum(Order.rizq_fee)).filter(
        Order.status == "доставлен"
    ).scalar() or 0
    
    total_courier_paid = db.query(func.sum(Order.courier_earn)).filter(
        Order.status == "доставлен"
    ).scalar() or 0
    
    total_turnover = db.query(func.sum(Order.delivery_price)).filter(
        Order.status == "доставлен"
    ).scalar() or 0
    
    return {
        "users": {
            "total": total_users,
            "customers": total_customers,
            "sellers": total_sellers,
            "couriers": total_couriers
        },
        "business": {
            "restaurants": total_restaurants,
            "products": total_products,
            "orders": total_orders,
            "delivered": delivered_orders
        },
        "money": {
            "rizq_income": float(total_revenue),
            "courier_paid": float(total_courier_paid),
            "total_turnover": float(total_turnover)
        }
    }


# ================== ВСЕ ПОЛЬЗОВАТЕЛИ ==================
@router.get("/users")
def get_all_users(
    role: str = None,
    db: Session = Depends(get_db)
):
    """Получить всех пользователей"""
    
    query = db.query(User).order_by(User.created_at.desc())
    
    if role:
        query = query.filter(User.role == role)
    
    users = query.all()
    
    return [
        {
            "id": u.id,
            "phone": u.phone,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "email_verified": u.email_verified,
            "subscription_type": u.subscription_type,
            "free_deliveries_used": u.free_deliveries_used,
            "created_at": (u.created_at + timedelta(hours=5)).isoformat() if u.created_at else None
        }
        for u in users
    ]


# ================== ВСЕ РЕСТОРАНЫ ==================
@router.get("/sellers")
def get_all_sellers(db: Session = Depends(get_db)):
    """Получить все рестораны"""
    
    sellers = db.query(Seller).order_by(Seller.created_at.desc()).all()
    
    return [
        {
            "id": s.id,
            "phone": s.phone,
            "name": s.name,
            "seller_type": s.seller_type,
            "address": s.address,
            "is_active": s.is_active,
            "products_count": db.query(Product).filter(Product.seller_phone == s.phone).count(),
            "orders_count": db.query(Order).filter(Order.seller_phone == s.phone).count(),
            "created_at": (s.created_at + timedelta(hours=5)).isoformat() if s.created_at else None
        }
        for s in sellers
    ]


# ================== ВСЕ ТОВАРЫ ==================
@router.get("/products")
def get_all_products(db: Session = Depends(get_db)):
    """Получить все товары"""
    
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "description": p.description,
            "category": p.category,
            "image_url": p.image_url,
            "is_available": p.is_available,
            "seller_phone": p.seller_phone,
            "created_at": (p.created_at + timedelta(hours=5)).isoformat() if p.created_at else None
        }
        for p in products
    ]


# ================== ВСЕ ЗАКАЗЫ ==================
@router.get("/orders")
def get_all_orders(
    status: str = None,
    db: Session = Depends(get_db)
):
    """Получить все заказы"""
    
    query = db.query(Order).order_by(Order.created_at.desc())
    
    if status:
        query = query.filter(Order.status == status)
    
    orders = query.limit(100).all()
    
    return [
        {
            "id": o.id,
            "code": o.code,
            "customer_phone": o.customer_phone,
            "seller_phone": o.seller_phone,
            "courier": o.courier,
            "status": o.status,
            "products": o.products,
            "delivery_price": o.delivery_price,
            "rizq_fee": o.rizq_fee,
            "courier_earn": o.courier_earn,
            "distance_km": o.distance_km,
            "pickup_code": o.pickup_code,
            "delivery_code": o.delivery_code,
            "created_at": (o.created_at + timedelta(hours=5)).isoformat() if o.created_at else None
        }
        for o in orders
    ]


# ================== ЗАБЛОКИРОВАТЬ ПОЛЬЗОВАТЕЛЯ ==================
@router.post("/users/{user_id}/block")
def block_user(user_id: int, db: Session = Depends(get_db)):
    """Заблокировать пользователя"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.is_active = False
    db.commit()
    
    return {"message": "Пользователь заблокирован"}


# ================== РАЗБЛОКИРОВАТЬ ПОЛЬЗОВАТЕЛЯ ==================
@router.post("/users/{user_id}/unblock")
def unblock_user(user_id: int, db: Session = Depends(get_db)):
    """Разблокировать пользователя"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.is_active = True
    db.commit()
    
    return {"message": "Пользователь разблокирован"}


# ================== ВЕРИФИЦИРОВАТЬ КУРЬЕРА ==================
@router.post("/couriers/{user_id}/verify")
def verify_courier(user_id: int, db: Session = Depends(get_db)):
    """Подтвердить курьера"""
    
    user = db.query(User).filter(User.id == user_id, User.role == "courier").first()
    if not user:
        raise HTTPException(status_code=404, detail="Курьер не найден")
    
    user.is_verified = True
    db.commit()
    
    return {"message": "Курьер верифицирован"}


# ================== СТАТИСТИКА ЗА СЕГОДНЯ ==================
@router.get("/stats/today")
def get_today_stats(db: Session = Depends(get_db)):
    """Статистика за сегодня"""
    
    today = datetime.utcnow().date()
    
    today_orders = db.query(Order).filter(
        func.date(Order.created_at) == today
    ).count()
    
    today_delivered = db.query(Order).filter(
        func.date(Order.created_at) == today,
        Order.status == "доставлен"
    ).count()
    
    today_revenue = db.query(func.sum(Order.rizq_fee)).filter(
        func.date(Order.created_at) == today,
        Order.status == "доставлен"
    ).scalar() or 0
    
    today_new_users = db.query(User).filter(
        func.date(User.created_at) == today
    ).count()
    
    return {
        "orders": today_orders,
        "delivered": today_delivered,
        "revenue": float(today_revenue),
        "new_users": today_new_users
    }