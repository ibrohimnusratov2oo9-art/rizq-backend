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


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "rizq2025admin"


@router.post("/login")
def admin_login(username: str, password: str):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return {"success": True, "message": "Добро пожаловать!", "token": "admin_token_secret"}
    raise HTTPException(status_code=401, detail="Неверный логин или пароль")


# ================== СТАТИСТИКА ==================
@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
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
    
    total_bonuses = db.query(func.sum(CourierBonus.amount)).scalar() or 0
    
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
            "total_turnover": float(total_turnover),
            "total_bonuses": float(total_bonuses)
        }
    }


@router.get("/stats/today")
def get_today_stats(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    
    today_orders = db.query(Order).filter(func.date(Order.created_at) == today).count()
    today_delivered = db.query(Order).filter(func.date(Order.created_at) == today, Order.status == "доставлен").count()
    today_revenue = db.query(func.sum(Order.rizq_fee)).filter(func.date(Order.created_at) == today, Order.status == "доставлен").scalar() or 0
    today_new_users = db.query(User).filter(func.date(User.created_at) == today).count()
    
    return {
        "orders": today_orders,
        "delivered": today_delivered,
        "revenue": float(today_revenue),
        "new_users": today_new_users
    }


# ================== ПОЛЬЗОВАТЕЛИ ==================
@router.get("/users")
def get_all_users(role: str = None, db: Session = Depends(get_db)):
    query = db.query(User).order_by(User.created_at.desc())
    if role:
        query = query.filter(User.role == role)
    users = query.all()
    
    result = []
    for u in users:
        user_data = {
            "id": u.id,
            "phone": u.phone,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "email_verified": u.email_verified,
            "subscription_type": u.subscription_type,
            "subscription_expires": u.subscription_expires.isoformat() if u.subscription_expires else None,
            "free_deliveries_used": u.free_deliveries_used,
            "password_hash": u.password[:20] + "..." if u.password else None,
            "has_passport": bool(u.passport_photo),
            "has_selfie": bool(u.selfie_photo),
            "has_selfie_passport": bool(u.selfie_with_passport),
            "created_at": (u.created_at + timedelta(hours=5)).isoformat() if u.created_at else None,
        }
        
        # Для курьеров добавляем статистику
        if u.role == "courier":
            delivered = db.query(Order).filter(Order.courier == u.phone, Order.status == "доставлен").count()
            total_earned = db.query(func.sum(Order.courier_earn)).filter(Order.courier == u.phone, Order.status == "доставлен").scalar() or 0
            avg_rating = db.query(func.avg(Order.courier_rating)).filter(Order.courier == u.phone, Order.courier_rating.isnot(None)).scalar()
            bonuses = db.query(CourierBonus).filter(CourierBonus.courier_phone == u.phone).all()
            total_bonus = sum(b.amount for b in bonuses)
            
            user_data["courier_stats"] = {
                "deliveries": delivered,
                "total_earned": float(total_earned),
                "avg_rating": round(float(avg_rating), 2) if avg_rating else None,
                "total_bonus": float(total_bonus),
                "bonuses": [{"amount": b.amount, "reason": b.reason, "date": (b.created_at + timedelta(hours=5)).isoformat()} for b in bonuses],
                "progress": {
                    "current": delivered,
                    "next_milestone": 100 if delivered < 100 else (500 if delivered < 500 else None),
                    "next_bonus": 500 if delivered < 100 else (1000 if delivered < 500 else None),
                    "remaining": (100 - delivered) if delivered < 100 else ((500 - delivered) if delivered < 500 else 0)
                }
            }
        
        # Для клиентов добавляем статистику
        if u.role == "customer":
            orders_count = db.query(Order).filter(Order.customer_phone == u.phone).count()
            total_spent = db.query(func.sum(Order.delivery_price)).filter(Order.customer_phone == u.phone, Order.status == "доставлен").scalar() or 0
            
            user_data["customer_stats"] = {
                "orders_count": orders_count,
                "total_spent": float(total_spent)
            }
        
        # Для продавцов добавляем статистику
        if u.role == "seller":
            seller = db.query(Seller).filter(Seller.phone == u.phone).first()
            if seller:
                products_count = db.query(Product).filter(Product.seller_phone == u.phone).count()
                orders_count = db.query(Order).filter(Order.seller_phone == u.phone).count()
                
                user_data["seller_stats"] = {
                    "restaurant_name": seller.name,
                    "restaurant_type": seller.seller_type,
                    "products_count": products_count,
                    "orders_count": orders_count
                }
        
        result.append(user_data)
    
    return result


# ================== ДЕТАЛИ ПОЛЬЗОВАТЕЛЯ ==================
@router.get("/users/{user_id}")
def get_user_detail(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user_data = {
        "id": user.id,
        "phone": user.phone,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "email_verified": user.email_verified,
        "subscription_type": user.subscription_type,
        "password_hash": user.password[:20] + "..." if user.password else None,
        "passport_photo": user.passport_photo,
        "selfie_photo": user.selfie_photo,
        "selfie_with_passport": user.selfie_with_passport,
        "created_at": (user.created_at + timedelta(hours=5)).isoformat() if user.created_at else None,
    }
    
    # Все заказы пользователя
    if user.role == "customer":
        orders = db.query(Order).filter(Order.customer_phone == user.phone).order_by(Order.created_at.desc()).all()
    elif user.role == "seller":
        orders = db.query(Order).filter(Order.seller_phone == user.phone).order_by(Order.created_at.desc()).all()
    elif user.role == "courier":
        orders = db.query(Order).filter(Order.courier == user.phone).order_by(Order.created_at.desc()).all()
    else:
        orders = []
    
    user_data["orders"] = [
        {
            "code": o.code,
            "status": o.status,
            "delivery_price": o.delivery_price,
            "rizq_fee": o.rizq_fee,
            "courier_earn": o.courier_earn,
            "distance_km": o.distance_km,
            "created_at": (o.created_at + timedelta(hours=5)).isoformat() if o.created_at else None
        }
        for o in orders
    ]
    
    return user_data


# ================== СБРОС ПАРОЛЯ ==================
@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, new_password: str = "rizq12345", db: Session = Depends(get_db)):
    import hashlib
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.password = hashlib.sha256(new_password.encode()).hexdigest()
    db.commit()
    
    return {"message": f"Пароль сброшен на: {new_password}"}


# ================== РЕСТОРАНЫ ==================
@router.get("/sellers")
def get_all_sellers(db: Session = Depends(get_db)):
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


# ================== ТОВАРЫ ==================
@router.get("/products")
def get_all_products(db: Session = Depends(get_db)):
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


# ================== ЗАКАЗЫ ==================
@router.get("/orders")
def get_all_orders(status: str = None, db: Session = Depends(get_db)):
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


# ================== БЛОКИРОВКА ==================
@router.post("/users/{user_id}/block")
def block_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_active = False
    db.commit()
    return {"message": "Пользователь заблокирован"}


@router.post("/users/{user_id}/unblock")
def unblock_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_active = True
    db.commit()
    return {"message": "Пользователь разблокирован"}


@router.post("/couriers/{user_id}/verify")
def verify_courier(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.role == "courier").first()
    if not user:
        raise HTTPException(status_code=404, detail="Курьер не найден")
    user.is_verified = True
    db.commit()
    return {"message": "Курьер верифицирован"}


# ================== БОНУСЫ ==================
@router.get("/bonuses")
def get_all_bonuses(db: Session = Depends(get_db)):
    bonuses = db.query(CourierBonus).order_by(CourierBonus.created_at.desc()).all()
    return [
        {
            "id": b.id,
            "courier_phone": b.courier_phone,
            "amount": b.amount,
            "reason": b.reason,
            "deliveries_count": b.deliveries_count,
            "created_at": (b.created_at + timedelta(hours=5)).isoformat() if b.created_at else None
        }
        for b in bonuses
    ]


# ================== ВЫПЛАТЫ ==================
@router.get("/payouts")
def get_all_payouts(db: Session = Depends(get_db)):
    payouts = db.query(CourierPayout).order_by(CourierPayout.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "courier_phone": p.courier_phone,
            "amount": p.amount,
            "status": p.status,
            "note": p.note,
            "created_at": (p.created_at + timedelta(hours=5)).isoformat() if p.created_at else None
        }
        for p in payouts
    ]