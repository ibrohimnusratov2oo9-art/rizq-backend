from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
import random
from datetime import timedelta, datetime
import math

from auth import get_current_user
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from models import Order as OrderModel, CourierPayout, CourierBonus, User

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
    """Получить роль пользователя"""
    if isinstance(user, str):
        return user
    if hasattr(user, 'role'):
        return user.role
    if isinstance(user, dict):
        return user.get("role")
    return None


def phone_of(user):
    """Получить телефон пользователя"""
    if isinstance(user, str):
        return None
    if hasattr(user, 'phone'):
        return user.phone
    if isinstance(user, dict):
        return user.get("phone")
    return None


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
    delivered_count = db.query(OrderModel).filter(
        OrderModel.status == OrderStatus.DELIVERED.value,
        OrderModel.courier == courier_phone
    ).count()

    result = {
        "bonus_given": False,
        "delivered_count": delivered_count,
        "show_notification": False,
        "notification_title": "",
        "notification_message": "",
        "notification_emoji": "",
        "next_bonus_at": None,
        "next_bonus_amount": None,
        "remaining_deliveries": 0,
        "current_milestone": 100,
        "is_max_reached": False
    }

    if delivered_count <= 100:
        result["current_milestone"] = 100
        result["next_bonus_at"] = 100
        result["next_bonus_amount"] = 500
        result["remaining_deliveries"] = 100 - delivered_count
    elif delivered_count <= 500:
        result["current_milestone"] = 500
        result["next_bonus_at"] = 500
        result["next_bonus_amount"] = 1000
        result["remaining_deliveries"] = 500 - delivered_count
    else:
        result["is_max_reached"] = True
        result["current_milestone"] = 500
        result["next_bonus_at"] = None
        result["next_bonus_amount"] = None
        result["remaining_deliveries"] = 0

    if delivered_count == 100:
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
            result["bonus_given"] = True
            result["show_notification"] = True
            result["notification_emoji"] = "🎁🎉🎁"
            result["notification_title"] = "ПОЗДРАВЛЯЕМ!"
            result["notification_message"] = (
                f"🎉 Вы выполнили 100 доставок!\n\n"
                f"💰 Ваш бонус: 500 сомони\n\n"
                f"Теперь зарабатывайте до 500 доставок\n"
                f"для бонуса 1000 сомони!"
            )
    elif delivered_count == 500:
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
            result["bonus_given"] = True
            result["show_notification"] = True
            result["notification_emoji"] = "🏆🎊🏆"
            result["notification_title"] = "ВЫ ПРОФЕССИОНАЛ!"
            result["notification_message"] = (
                f"🎊 Вы выполнили 500 доставок!\n\n"
                f"💰 Ваш бонус: 1000 сомони\n\n"
                f"Всего получено бонусов:\n"
                f"💎 1500 сомони\n\n"
                f"Спасибо за вашу работу! ⭐"
            )

    return result


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
    
    current_user = db.query(User).filter(User.phone == customer_phone).first()

    distance = calculate_distance(
        data.from_lat, data.from_lng,
        data.to_lat, data.to_lng
    )

    # Расчёт цены
    if distance <= 3:
        delivery_price = 15.0
    else:
        delivery_price = 15.0 + (distance - 3) * 5
    
    # Доплаты
    current_hour = datetime.utcnow().hour + 5
    if current_hour >= 24:
        current_hour -= 24
    
    time_surcharge = 0
    if 18 <= current_hour < 22:
        time_surcharge = distance * 2
    elif current_hour >= 22 or current_hour < 8:
        time_surcharge = distance * 5
    
    weather_surcharge = 0
    service_fee = 5.0
    
    # Проверка подписки
    is_subscription_order = False
    discount_applied = 0
    final_delivery_price = delivery_price
    final_service_fee = service_fee
    
    if current_user and current_user.subscription_type in ["plus", "premium"]:
        if current_user.subscription_expires and datetime.utcnow() < current_user.subscription_expires:
            sub_limits = {"plus": 5, "premium": 15}
            sub_discounts = {"plus": 5, "premium": 10}
            
            limit = sub_limits[current_user.subscription_type]
            
            if current_user.free_deliveries_used < limit:
                final_delivery_price = 0
                final_service_fee = 0
                is_subscription_order = True
                current_user.free_deliveries_used += 1
                db.commit()
            else:
                final_service_fee = 0
            
            discount_applied = sub_discounts[current_user.subscription_type]
    
    base_delivery_for_calc = delivery_price
    commission_percent = 30 if distance <= 5 else 40
    
    rizq_from_delivery = round(base_delivery_for_calc * commission_percent / 100, 2)
    courier_from_delivery = round(base_delivery_for_calc - rizq_from_delivery, 2)
    
    courier_earn = courier_from_delivery + time_surcharge + weather_surcharge
    rizq_fee = rizq_from_delivery + service_fee
    
    total_for_customer = final_delivery_price + final_service_fee + time_surcharge + weather_surcharge
    
    pickup_code = random.randint(1000, 9999)
    delivery_code = random.randint(100000, 999999)

    # Находим seller_phone из товара
    from models import Product as ProductModel
    seller_phone = None
    if data.products and len(data.products) > 0:
        first_product = db.query(ProductModel).filter(
            ProductModel.name == data.products[0]
        ).first()
        if first_product:
            seller_phone = first_product.seller_phone

    order = OrderModel(
        code=random.randint(1000, 9999),
        customer_phone=customer_phone,
        status=OrderStatus.READY.value,
        products=data.products,
        seller_phone=seller_phone,
        courier=None,
        pickup_code=pickup_code,
        delivery_code=delivery_code,
        from_lat=data.from_lat,
        from_lng=data.from_lng,
        to_lat=data.to_lat,
        to_lng=data.to_lng,
        distance_km=distance,
        delivery_price=final_delivery_price,
        price_per_km=5,
        commission_percent=commission_percent,
        time_surcharge=time_surcharge,
        weather_surcharge=weather_surcharge,
        service_fee=final_service_fee,
        is_subscription_order=is_subscription_order,
        discount_applied=discount_applied,
        rizq_fee=rizq_fee,
        courier_earn=courier_earn
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "message": "Заказ создан",
        "order_code": order.code,
        "delivery_price": final_delivery_price,
        "time_surcharge": time_surcharge,
        "weather_surcharge": weather_surcharge,
        "discount_applied": discount_applied,
        "total_price": total_for_customer,
        "distance_km": distance,
        "delivery_code": delivery_code,
        "is_subscription_order": is_subscription_order,
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

    bonus_result = check_and_give_bonus(db, order.courier)

    response = {
        "message": "Заказ доставлен",
        "courier_earn": order.courier_earn,
        "earnings_message": f"💰 Вы заработали: {order.courier_earn} сомони",
        "delivered_count": bonus_result["delivered_count"],
        "current_milestone": bonus_result["current_milestone"],
        "next_bonus_at": bonus_result["next_bonus_at"],
        "next_bonus_amount": bonus_result["next_bonus_amount"],
        "remaining_deliveries": bonus_result["remaining_deliveries"],
        "is_max_reached": bonus_result["is_max_reached"],
        "show_notification": bonus_result["show_notification"]
    }

    if bonus_result["show_notification"]:
        response["notification"] = {
            "emoji": bonus_result["notification_emoji"],
            "title": bonus_result["notification_title"],
            "message": bonus_result["notification_message"],
            "is_bonus": bonus_result["bonus_given"]
        }

    return response


# ================== MY ORDERS ==================
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

    if delivered_count <= 100:
        current_milestone = 100
        next_bonus_amount = 500
        progress_percent = (delivered_count / 100) * 100
        is_max_reached = False
        status_text = "Прогресс к первому бонусу"
    elif delivered_count <= 500:
        current_milestone = 500
        next_bonus_amount = 1000
        progress_percent = (delivered_count / 500) * 100
        is_max_reached = False
        status_text = "Прогресс ко второму бонусу"
    else:
        current_milestone = 500
        next_bonus_amount = None
        progress_percent = 100
        is_max_reached = True
        status_text = "Все бонусы получены! 🏆"

    return {
        "courier_phone": courier_phone,
        "deliveries_count": delivered_count,
        "current_milestone": current_milestone,
        "next_bonus_amount": next_bonus_amount,
        "progress_percent": round(progress_percent, 2),
        "remaining_deliveries": current_milestone - delivered_count if not is_max_reached else 0,
        "is_max_reached": is_max_reached,
        "status_text": status_text,
        "total_bonus_earned": total_bonus,
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