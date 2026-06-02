from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
import random
from datetime import timedelta
import math

from auth import get_current_user
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from models import Order as OrderModel, CourierPayout, CourierBonus


router = APIRouter(prefix="/orders", tags=["Заказы"])


# ================== DB ==================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================== USER HELPERS ==================
def role_of(user):
    return user if isinstance(user, str) else user.get("role")


def phone_of(user):
    return None if isinstance(user, str) else user.get("phone")


def require_phone(user):
    phone = phone_of(user)
    if not phone:
        raise HTTPException(status_code=401, detail="В токене нет phone")
    return phone


def require_admin(user):
    if role_of(user) != "admin":
        raise HTTPException(status_code=403, detail="Только RIZQ (admin)")


# ================== ENUM ==================
class OrderStatus(str, Enum):
    CREATED = "создан"
    READY = "готов"
    ACCEPTED = "принят"
    PICKED_UP = "забран"
    DELIVERED = "доставлен"


# ================== HELPERS ==================
def calculate_distance(lat1, lng1, lat2, lng2):
    return round(math.sqrt((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2) * 111, 2)


def get_commission_percent(distance_km: float) -> int:
    """
    Комиссия RIZQ:
    - До 5 км: 30%
    - Больше 5 км: 40%
    """
    return 30 if distance_km <= 5 else 40


def courier_available_balance(db: Session, courier_phone: str) -> float:
    earned = db.query(func.sum(OrderModel.courier_earn)).filter(
        OrderModel.status == OrderStatus.DELIVERED.value,
        OrderModel.courier == courier_phone
    ).scalar() or 0

    paid = db.query(func.sum(CourierPayout.amount)).filter(
        CourierPayout.courier_phone == courier_phone,
        CourierPayout.status == "paid"
    ).scalar() or 0

    pending = db.query(func.sum(CourierPayout.amount)).filter(
        CourierPayout.courier_phone == courier_phone,
        CourierPayout.status == "pending"
    ).scalar() or 0

    return float(earned - paid - pending)


def check_and_give_bonus(db: Session, courier_phone: str):
    """
    Проверяет количество доставок курьера и выдаёт бонусы:
    - 100 доставок = 500 сомони
    - 500 доставок = 1000 сомони
    """
    delivered_count = db.query(OrderModel).filter(
        OrderModel.status == OrderStatus.DELIVERED.value,
        OrderModel.courier == courier_phone
    ).count()

    # Проверка на 500 доставок
    if delivered_count == 500:
        existing = db.query(CourierBonus).filter(
            CourierBonus.courier_phone == courier_phone,
            CourierBonus.reason == "500_deliveries"
        ).first()
        if not existing:
            bonus = CourierBonus(
                courier_phone=courier_phone,
                amount=1000.0,
                reason="500_deliveries",
                deliveries_count=500
            )
            db.add(bonus)
            db.commit()
            return {"bonus_given": True, "amount": 1000, "reason": "500 доставок"}

    # Проверка на 100 доставок
    elif delivered_count == 100:
        existing = db.query(CourierBonus).filter(
            CourierBonus.courier_phone == courier_phone,
            CourierBonus.reason == "100_deliveries"
        ).first()
        if not existing:
            bonus = CourierBonus(
                courier_phone=courier_phone,
                amount=500.0,
                reason="100_deliveries",
                deliveries_count=100
            )
            db.add(bonus)
            db.commit()
            return {"bonus_given": True, "amount": 500, "reason": "100 доставок"}

    return {"bonus_given": False}


# ================== SCHEMAS ==================
class OrderCreate(BaseModel):
    customer_phone: str
    products: List[str]
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float


class ConfirmDelivery(BaseModel):
    delivery_code: int


class RateCourier(BaseModel):
    rating: int
    review: str = ""


class RateProduct(BaseModel):
    rating: int
    review: str = ""


class PayoutRequest(BaseModel):
    amount: float
    note: str = ""


# ================== SAFE ORDER VIEW ==================
def order_public(o: OrderModel, viewer_role: str):
    base = {
        "code": o.code,
        "status": o.status,
        "distance_km": o.distance_km,
        "created_at": o.created_at + timedelta(hours=5)
    }

    if viewer_role == "customer":
        base["price"] = o.delivery_price
        return base

    if viewer_role == "seller":
        base["price"] = o.delivery_price
        return base

    if viewer_role == "courier":
        base["courier_earn"] = o.courier_earn
        base["from"] = [o.from_lat, o.from_lng]
        base["to"] = [o.to_lat, o.to_lng]
        return base

    if viewer_role == "admin":
        base.update({
            "price": o.delivery_price,
            "price_per_km": o.price_per_km,
            "commission_percent": o.commission_percent,
            "rizq_fee": o.rizq_fee,
            "courier_earn": o.courier_earn,
            "customer_phone": o.customer_phone,
            "seller_phone": o.seller_phone,
            "courier": o.courier
        })
        return base

    return base


# ================== CREATE ==================
@router.post("/create")
def create_order(
    data: OrderCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "customer":
        raise HTTPException(status_code=403, detail="Только клиент")

    customer_phone = require_phone(user)

    distance = calculate_distance(
        data.from_lat, data.from_lng,
        data.to_lat, data.to_lng
    )

    price_per_km = 5
    commission_percent = get_commission_percent(distance)

    total_price = round(distance * price_per_km, 2)
    rizq_fee = round(total_price * commission_percent / 100, 2)
    courier_earn = round(total_price - rizq_fee, 2)

    order = OrderModel(
        code=random.randint(1000, 9999),
        customer_phone=customer_phone,
        status=OrderStatus.CREATED.value,
        products=data.products,
        seller_phone=None,
        courier=None,
        delivery_code=random.randint(100000, 999999),
        from_lat=data.from_lat,
        from_lng=data.from_lng,
        to_lat=data.to_lat,
        to_lng=data.to_lng,
        distance_km=distance,
        delivery_price=total_price,
        price_per_km=price_per_km,
        commission_percent=commission_percent,
        rizq_fee=rizq_fee,
        courier_earn=courier_earn
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "message": "Заказ создан",
        "order_code": order.code,
        "price": order.delivery_price,
        "distance_km": order.distance_km,
        "delivery_code": order.delivery_code,
        "created_at": order.created_at + timedelta(hours=5)
    }


# ================== SELLER READY ==================
@router.post("/{code}/ready")
def seller_ready(
    code: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    order = db.query(OrderModel).filter(OrderModel.code == code).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if order.status == OrderStatus.DELIVERED.value:
        raise HTTPException(status_code=400, detail="Нельзя изменить доставленный заказ")

    seller_phone = require_phone(user)
    order.seller_phone = seller_phone
    order.status = OrderStatus.READY.value
    db.commit()

    return {"message": "Заказ готов"}


# ================== AVAILABLE FOR COURIER ==================
@router.get("/available_for_courier")
def available_for_courier(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    orders = db.query(OrderModel).filter(
        OrderModel.status == OrderStatus.READY.value,
        OrderModel.courier.is_(None)
    ).all()

    return [order_public(o, "courier") for o in orders]


# ================== COURIER ACCEPT ==================
@router.post("/{code}/accept")
def courier_accept(
    code: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    courier_phone = require_phone(user)

    order = db.query(OrderModel).filter(
        OrderModel.code == code,
        OrderModel.status == OrderStatus.READY.value,
        OrderModel.courier.is_(None)
    ).first()

    if not order:
        raise HTTPException(status_code=400, detail="Заказ недоступен")

    order.status = OrderStatus.ACCEPTED.value
    order.courier = courier_phone
    db.commit()

    return {"message": "Заказ принят", "courier": courier_phone}


# ================== PICKED UP ==================
@router.post("/{code}/picked_up")
def picked_up(
    code: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    courier_phone = require_phone(user)

    order = db.query(OrderModel).filter(
        OrderModel.code == code,
        OrderModel.status == OrderStatus.ACCEPTED.value
    ).first()

    if not order:
        raise HTTPException(status_code=400, detail="Нельзя забрать заказ")

    if order.courier != courier_phone:
        raise HTTPException(status_code=403, detail="Это не ваш заказ")

    order.status = OrderStatus.PICKED_UP.value
    db.commit()

    return {"message": "Заказ забран"}


# ================== CONFIRM DELIVERY ==================
@router.post("/{code}/confirm_delivery")
def confirm_delivery(
    code: int,
    data: ConfirmDelivery,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "customer":
        raise HTTPException(status_code=403, detail="Только клиент")

    customer_phone = require_phone(user)

    order = db.query(OrderModel).filter(
        OrderModel.code == code,
        OrderModel.status == OrderStatus.PICKED_UP.value
    ).first()

    if not order:
        raise HTTPException(status_code=400, detail="Нельзя подтвердить доставку")

    if order.customer_phone != customer_phone:
        raise HTTPException(status_code=403, detail="Это не ваш заказ")

    if data.delivery_code != order.delivery_code:
        raise HTTPException(status_code=403, detail="Неверный код")

    order.status = OrderStatus.DELIVERED.value
    db.commit()

    # Проверяем бонус курьера
    bonus_result = check_and_give_bonus(db, order.courier)

    response = {"message": "Заказ доставлен"}
    if bonus_result["bonus_given"]:
        response["bonus"] = bonus_result
        response["bonus_message"] = f"🎉 Поздравляем! Вы получили бонус {bonus_result['amount']} сомони за {bonus_result['reason']}!"

    return response


# ================== MY ORDERS (CURRENT/HISTORY) ==================
@router.get("/my/current")
def my_current(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    r = role_of(user)

    if r == "customer":
        phone = require_phone(user)
        orders = db.query(OrderModel).filter(
            OrderModel.customer_phone == phone,
            OrderModel.status != OrderStatus.DELIVERED.value
        ).order_by(OrderModel.created_at.desc()).all()
        return [order_public(o, "customer") for o in orders]

    if r == "seller":
        phone = require_phone(user)
        orders = db.query(OrderModel).filter(
            OrderModel.seller_phone == phone,
            OrderModel.status != OrderStatus.DELIVERED.value
        ).order_by(OrderModel.created_at.desc()).all()
        return [order_public(o, "seller") for o in orders]

    if r == "courier":
        phone = require_phone(user)
        orders = db.query(OrderModel).filter(
            OrderModel.courier == phone,
            OrderModel.status != OrderStatus.DELIVERED.value
        ).order_by(OrderModel.created_at.desc()).all()
        return [order_public(o, "courier") for o in orders]

    raise HTTPException(status_code=403, detail="Неизвестная роль")


@router.get("/my/history")
def my_history(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    r = role_of(user)

    if r == "customer":
        phone = require_phone(user)
        orders = db.query(OrderModel).filter(
            OrderModel.customer_phone == phone,
            OrderModel.status == OrderStatus.DELIVERED.value
        ).order_by(OrderModel.created_at.desc()).all()
        return [order_public(o, "customer") for o in orders]

    if r == "seller":
        phone = require_phone(user)
        orders = db.query(OrderModel).filter(
            OrderModel.seller_phone == phone,
            OrderModel.status == OrderStatus.DELIVERED.value
        ).order_by(OrderModel.created_at.desc()).all()
        return [order_public(o, "seller") for o in orders]

    if r == "courier":
        phone = require_phone(user)
        orders = db.query(OrderModel).filter(
            OrderModel.courier == phone,
            OrderModel.status == OrderStatus.DELIVERED.value
        ).order_by(OrderModel.created_at.desc()).all()
        return [order_public(o, "courier") for o in orders]

    raise HTTPException(status_code=403, detail="Неизвестная роль")


# ================== RATINGS ==================
@router.post("/{code}/rate/courier")
def rate_courier(
    code: int,
    data: RateCourier,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "customer":
        raise HTTPException(status_code=403, detail="Только клиент")

    customer_phone = require_phone(user)

    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="Рейтинг должен быть от 1 до 5")

    order = db.query(OrderModel).filter(OrderModel.code == code).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if order.customer_phone != customer_phone:
        raise HTTPException(status_code=403, detail="Это не ваш заказ")

    if order.status != OrderStatus.DELIVERED.value:
        raise HTTPException(status_code=400, detail="Можно оценить только после доставки")

    if order.courier_rating is not None:
        raise HTTPException(status_code=400, detail="Курьер уже оценён")

    order.courier_rating = data.rating
    order.courier_review = data.review
    db.commit()

    return {"message": "Рейтинг курьера сохранён"}


@router.post("/{code}/rate/product")
def rate_product(
    code: int,
    data: RateProduct,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "customer":
        raise HTTPException(status_code=403, detail="Только клиент")

    customer_phone = require_phone(user)

    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="Рейтинг должен быть от 1 до 5")

    order = db.query(OrderModel).filter(OrderModel.code == code).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if order.customer_phone != customer_phone:
        raise HTTPException(status_code=403, detail="Это не ваш заказ")

    if order.status != OrderStatus.DELIVERED.value:
        raise HTTPException(status_code=400, detail="Можно оценить только после доставки")

    if order.product_rating is not None:
        raise HTTPException(status_code=400, detail="Продукт уже оценён")

    order.product_rating = data.rating
    order.product_review = data.review
    db.commit()

    return {"message": "Рейтинг продукта сохранён"}


@router.get("/seller/rating")
def seller_rating(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller_phone = require_phone(user)

    res = db.query(
        func.avg(OrderModel.product_rating),
        func.count(OrderModel.product_rating)
    ).filter(
        OrderModel.seller_phone == seller_phone,
        OrderModel.product_rating.isnot(None),
        OrderModel.status == OrderStatus.DELIVERED.value
    ).first()

    avg_rating = round(float(res[0]), 2) if res[0] else 0
    count_reviews = int(res[1] or 0)

    return {
        "seller_phone": seller_phone,
        "seller_rating": avg_rating,
        "reviews_count": count_reviews
    }


@router.get("/seller/dashboard")
def seller_dashboard(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller_phone = require_phone(user)

    delivered = db.query(OrderModel).filter(
        OrderModel.seller_phone == seller_phone,
        OrderModel.status == OrderStatus.DELIVERED.value
    )

    active = db.query(OrderModel).filter(
        OrderModel.seller_phone == seller_phone,
        OrderModel.status != OrderStatus.DELIVERED.value
    )

    delivered_count = delivered.count()
    active_count = active.count()

    turnover = delivered.with_entities(func.sum(OrderModel.delivery_price)).scalar() or 0
    avg_product_rating = delivered.with_entities(func.avg(OrderModel.product_rating)).scalar()

    return {
        "seller_phone": seller_phone,
        "active_orders": int(active_count),
        "delivered_orders": int(delivered_count),
        "turnover_total": float(turnover),
        "avg_product_rating": round(float(avg_product_rating), 2) if avg_product_rating is not None else None
    }


@router.get("/seller/history")
def seller_history(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")

    seller_phone = require_phone(user)

    orders = db.query(OrderModel).filter(
        OrderModel.seller_phone == seller_phone,
        OrderModel.status == OrderStatus.DELIVERED.value
    ).order_by(OrderModel.created_at.desc()).all()

    return [order_public(o, "seller") for o in orders]


@router.get("/courier/balance")
def courier_balance(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    courier_phone = require_phone(user)

    delivered = db.query(OrderModel).filter(
        OrderModel.status == OrderStatus.DELIVERED.value,
        OrderModel.courier == courier_phone
    )

    total_delivered = delivered.count()
    total_earned = delivered.with_entities(func.sum(OrderModel.courier_earn)).scalar() or 0
    avg_rating = delivered.with_entities(func.avg(OrderModel.courier_rating)).scalar()

    return {
        "courier_phone": courier_phone,
        "delivered_orders": int(total_delivered),
        "earned_total": float(total_earned),
        "avg_rating": round(float(avg_rating), 2) if avg_rating is not None else None
    }


@router.get("/courier/history")
def courier_history(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    courier_phone = require_phone(user)

    orders = db.query(OrderModel).filter(
        OrderModel.status == OrderStatus.DELIVERED.value,
        OrderModel.courier == courier_phone
    ).order_by(OrderModel.created_at.desc()).all()

    return [order_public(o, "courier") for o in orders]


# ================== COURIER BONUSES ==================
@router.get("/courier/bonuses")
def courier_bonuses(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список бонусов курьера"""
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    courier_phone = require_phone(user)

    bonuses = db.query(CourierBonus).filter(
        CourierBonus.courier_phone == courier_phone
    ).order_by(CourierBonus.created_at.desc()).all()

    total_bonus = sum(b.amount for b in bonuses)

    delivered_count = db.query(OrderModel).filter(
        OrderModel.status == OrderStatus.DELIVERED.value,
        OrderModel.courier == courier_phone
    ).count()

    next_bonus_at = 100 if delivered_count < 100 else (500 if delivered_count < 500 else None)
    next_bonus_amount = 500 if delivered_count < 100 else (1000 if delivered_count < 500 else None)

    return {
        "courier_phone": courier_phone,
        "total_bonus_earned": total_bonus,
        "deliveries_count": delivered_count,
        "next_bonus_at": next_bonus_at,
        "next_bonus_amount": next_bonus_amount,
        "remaining_deliveries": (next_bonus_at - delivered_count) if next_bonus_at else 0,
        "bonuses_history": [
            {
                "id": b.id,
                "amount": b.amount,
                "reason": b.reason,
                "deliveries_count": b.deliveries_count,
                "date": b.created_at + timedelta(hours=5)
            }
            for b in bonuses
        ]
    }


# ================== RIZQ ANALYTICS ==================
@router.get("/rizq/dashboard")
def rizq_dashboard(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_admin(user)

    delivered = db.query(OrderModel).filter(OrderModel.status == OrderStatus.DELIVERED.value)

    total_orders = delivered.count()
    total_income = delivered.with_entities(func.sum(OrderModel.rizq_fee)).scalar() or 0
    total_courier_paid = delivered.with_entities(func.sum(OrderModel.courier_earn)).scalar() or 0
    total_turnover = delivered.with_entities(func.sum(OrderModel.delivery_price)).scalar() or 0

    return {
        "delivered_orders": int(total_orders),
        "turnover_total": float(total_turnover),
        "rizq_income_total": float(total_income),
        "courier_paid_total": float(total_courier_paid)
    }


@router.get("/rizq/stats/daily")
def rizq_daily_stats(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_admin(user)

    day_col = func.date(OrderModel.created_at)

    stats = (
        db.query(
            day_col.label("date"),
            func.count(OrderModel.code).label("orders_count"),
            func.sum(OrderModel.delivery_price).label("turnover"),
            func.sum(OrderModel.rizq_fee).label("income"),
            func.sum(OrderModel.courier_earn).label("courier_paid"),
        )
        .filter(OrderModel.status == OrderStatus.DELIVERED.value)
        .group_by(day_col)
        .order_by(day_col)
        .all()
    )

    return [
        {
            "date": str(s.date),
            "orders": int(s.orders_count or 0),
            "turnover": float(s.turnover or 0),
            "rizq_income": float(s.income or 0),
            "courier_paid": float(s.courier_paid or 0),
        }
        for s in stats
    ]


@router.get("/rizq/top-sellers")
def rizq_top_sellers(
    limit: int = 10,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_admin(user)

    limit = max(1, min(limit, 50))

    rows = (
        db.query(
            OrderModel.seller_phone.label("seller_phone"),
            func.count(OrderModel.code).label("orders_count"),
            func.sum(OrderModel.delivery_price).label("turnover"),
            func.avg(OrderModel.product_rating).label("avg_rating"),
        )
        .filter(
            OrderModel.status == OrderStatus.DELIVERED.value,
            OrderModel.seller_phone.isnot(None)
        )
        .group_by(OrderModel.seller_phone)
        .order_by(func.sum(OrderModel.delivery_price).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "seller_phone": r.seller_phone,
            "orders": int(r.orders_count or 0),
            "turnover": float(r.turnover or 0),
            "avg_rating": round(float(r.avg_rating), 2) if r.avg_rating is not None else None
        }
        for r in rows
    ]


@router.get("/rizq/couriers/top")
def rizq_top_couriers(
    limit: int = 10,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_admin(user)

    limit = max(1, min(limit, 50))

    rows = (
        db.query(
            OrderModel.courier.label("courier_phone"),
            func.count(OrderModel.code).label("delivered_orders"),
            func.sum(OrderModel.courier_earn).label("earned"),
            func.avg(OrderModel.courier_rating).label("avg_rating"),
        )
        .filter(
            OrderModel.status == OrderStatus.DELIVERED.value,
            OrderModel.courier.isnot(None)
        )
        .group_by(OrderModel.courier)
        .order_by(func.sum(OrderModel.courier_earn).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "courier_phone": r.courier_phone,
            "delivered_orders": int(r.delivered_orders or 0),
            "earned_total": float(r.earned or 0),
            "avg_rating": round(float(r.avg_rating), 2) if r.avg_rating is not None else None
        }
        for r in rows
    ]


@router.get("/courier/wallet")
def courier_wallet(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    courier_phone = require_phone(user)

    available = courier_available_balance(db, courier_phone)

    pending = db.query(func.sum(CourierPayout.amount)).filter(
        CourierPayout.courier_phone == courier_phone,
        CourierPayout.status == "pending"
    ).scalar() or 0

    paid = db.query(func.sum(CourierPayout.amount)).filter(
        CourierPayout.courier_phone == courier_phone,
        CourierPayout.status == "paid"
    ).scalar() or 0

    return {
        "courier_phone": courier_phone,
        "available": float(available),
        "pending": float(pending),
        "paid_total": float(paid)
    }


@router.post("/courier/payout/request")
def request_payout(
    data: PayoutRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if role_of(user) != "courier":
        raise HTTPException(status_code=403, detail="Только курьер")

    courier_phone = require_phone(user)

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0")

    available = courier_available_balance(db, courier_phone)

    if data.amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно средств. Доступно: {round(available, 2)}"
        )

    payout = CourierPayout(
        courier_phone=courier_phone,
        amount=round(float(data.amount), 2),
        status="pending",
        note=data.note.strip() if data.note else None
    )

    db.add(payout)
    db.commit()
    db.refresh(payout)

    return {
        "message": "Запрос на выплату создан",
        "payout_id": payout.id,
        "status": payout.status,
        "amount": payout.amount
    }


@router.get("/rizq/payouts")
def rizq_payouts(
    status: str = "pending",
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_admin(user)

    if status not in ["pending", "paid", "rejected", "all"]:
        raise HTTPException(status_code=400, detail="status должен быть pending/paid/rejected/all")

    q = db.query(CourierPayout).order_by(CourierPayout.created_at.desc())
    if status != "all":
        q = q.filter(CourierPayout.status == status)

    rows = q.limit(100).all()

    return [
        {
            "id": p.id,
            "courier_phone": p.courier_phone,
            "amount": p.amount,
            "status": p.status,
            "note": p.note,
            "created_at": p.created_at + timedelta(hours=5)
        }
        for p in rows
    ]


@router.post("/rizq/payout/{payout_id}/mark_paid")
def mark_payout_paid(
    payout_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_admin(user)

    payout = db.query(CourierPayout).filter(CourierPayout.id == payout_id).first()
    if not payout:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    if payout.status != "pending":
        raise HTTPException(status_code=400, detail="Можно оплатить только pending")

    payout.status = "paid"
    db.commit()

    return {"message": "Выплата отмечена как paid", "payout_id": payout.id}


@router.post("/rizq/payout/{payout_id}/reject")
def reject_payout(
    payout_id: int,
    reason: str = "",
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_admin(user)

    payout = db.query(CourierPayout).filter(CourierPayout.id == payout_id).first()
    if not payout:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    if payout.status != "pending":
        raise HTTPException(status_code=400, detail="Можно отклонить только pending")

    payout.status = "rejected"
    payout.note = (reason or payout.note or "").strip() or None
    db.commit()

    return {"message": "Выплата отклонена", "payout_id": payout.id}