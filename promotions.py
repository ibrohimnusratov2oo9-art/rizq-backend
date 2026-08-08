from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

from database import SessionLocal
from models import Promotion, Product, User
from dependencies import get_current_user

router = APIRouter(prefix="/promotions", tags=["Акции"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ SCHEMAS ============

class PromotionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    promo_type: str  # discount_percent, discount_amount, buy_one_get_one, gift_on_order, free_delivery
    discount_value: Optional[float] = None
    min_order_amount: Optional[float] = None
    buy_quantity: Optional[int] = None
    get_quantity: Optional[int] = None
    apply_to: str = "all"  # all, category, products
    apply_category: Optional[str] = None
    product_ids: Optional[List[int]] = None
    gift_product_id: Optional[int] = None
    gift_product_name: Optional[str] = None
    has_end_date: bool = False
    end_date: Optional[datetime] = None


class PromotionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    discount_value: Optional[float] = None
    min_order_amount: Optional[float] = None
    is_active: Optional[bool] = None
    end_date: Optional[datetime] = None


# ============ ENDPOINTS ДЛЯ ПРОДАВЦА ============

@router.post("/create")
def create_promotion(
    data: PromotionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создать новую акцию (только продавец)"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавцы могут создавать акции")
    
    # Валидация типа акции
    valid_types = [
        "discount_percent",
        "discount_amount",
        "buy_one_get_one",
        "gift_on_order",
        "free_delivery"
    ]
    if data.promo_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Неверный тип акции. Доступны: {valid_types}")
    
    # Валидация по типу
    if data.promo_type == "discount_percent":
        if not data.discount_value or data.discount_value <= 0 or data.discount_value > 100:
            raise HTTPException(status_code=400, detail="Скидка в % должна быть от 1 до 100")
    
    elif data.promo_type == "discount_amount":
        if not data.discount_value or data.discount_value <= 0:
            raise HTTPException(status_code=400, detail="Сумма скидки должна быть больше 0")
    
    elif data.promo_type == "buy_one_get_one":
        if not data.buy_quantity or not data.get_quantity:
            raise HTTPException(status_code=400, detail="Укажите buy_quantity и get_quantity")
    
    elif data.promo_type == "gift_on_order":
        if not data.min_order_amount or not data.gift_product_name:
            raise HTTPException(status_code=400, detail="Укажите минимальную сумму и подарок")
    
    elif data.promo_type == "free_delivery":
        if not data.min_order_amount:
            raise HTTPException(status_code=400, detail="Укажите минимальную сумму для бесплатной доставки")
    
    # Создание акции
    promotion = Promotion(
        seller_phone=current_user.phone,
        title=data.title,
        description=data.description,
        promo_type=data.promo_type,
        discount_value=data.discount_value,
        min_order_amount=data.min_order_amount,
        buy_quantity=data.buy_quantity,
        get_quantity=data.get_quantity,
        apply_to=data.apply_to,
        apply_category=data.apply_category,
        product_ids=data.product_ids,
        gift_product_id=data.gift_product_id,
        gift_product_name=data.gift_product_name,
        has_end_date=data.has_end_date,
        end_date=data.end_date,
        is_active=True,
    )
    
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    
    return {
        "message": "✅ Акция создана!",
        "promotion_id": promotion.id,
        "title": promotion.title,
    }


@router.get("/my")
def get_my_promotions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить свои акции (только продавец)"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только для продавцов")
    
    promotions = db.query(Promotion).filter(
        Promotion.seller_phone == current_user.phone
    ).order_by(Promotion.created_at.desc()).all()
    
    result = []
    for p in promotions:
        # Проверка активности по дате
        is_expired = False
        if p.has_end_date and p.end_date:
            is_expired = datetime.utcnow() > p.end_date
        
        result.append({
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "promo_type": p.promo_type,
            "discount_value": p.discount_value,
            "min_order_amount": p.min_order_amount,
            "buy_quantity": p.buy_quantity,
            "get_quantity": p.get_quantity,
            "apply_to": p.apply_to,
            "apply_category": p.apply_category,
            "product_ids": p.product_ids,
            "gift_product_name": p.gift_product_name,
            "has_end_date": p.has_end_date,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "is_active": p.is_active,
            "is_expired": is_expired,
            "times_used": p.times_used,
            "created_at": p.created_at,
        })
    
    return result


@router.patch("/{promo_id}/toggle")
def toggle_promotion(
    promo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Включить / выключить акцию"""
    
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    
    if not promo:
        raise HTTPException(status_code=404, detail="Акция не найдена")
    
    if promo.seller_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    promo.is_active = not promo.is_active
    db.commit()
    
    return {
        "message": "✅ Статус обновлён",
        "is_active": promo.is_active,
    }


@router.put("/{promo_id}")
def update_promotion(
    promo_id: int,
    data: PromotionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Редактировать акцию"""
    
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    
    if not promo:
        raise HTTPException(status_code=404, detail="Акция не найдена")
    
    if promo.seller_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    if data.title is not None:
        promo.title = data.title
    if data.description is not None:
        promo.description = data.description
    if data.discount_value is not None:
        promo.discount_value = data.discount_value
    if data.min_order_amount is not None:
        promo.min_order_amount = data.min_order_amount
    if data.is_active is not None:
        promo.is_active = data.is_active
    if data.end_date is not None:
        promo.end_date = data.end_date
    
    db.commit()
    db.refresh(promo)
    
    return {"message": "✅ Акция обновлена"}


@router.delete("/{promo_id}")
def delete_promotion(
    promo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удалить акцию"""
    
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    
    if not promo:
        raise HTTPException(status_code=404, detail="Акция не найдена")
    
    if promo.seller_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    db.delete(promo)
    db.commit()
    
    return {"message": "✅ Акция удалена"}


# ============ ENDPOINTS ДЛЯ КЛИЕНТА ============

@router.get("/seller/{seller_phone}")
def get_seller_promotions(
    seller_phone: str,
    db: Session = Depends(get_db)
):
    """Получить активные акции продавца (для клиента)"""
    
    promotions = db.query(Promotion).filter(
        Promotion.seller_phone == seller_phone,
        Promotion.is_active == True
    ).all()
    
    result = []
    now = datetime.utcnow()
    
    for p in promotions:
        # Пропускаем истёкшие
        if p.has_end_date and p.end_date and now > p.end_date:
            continue
        # Пропускаем ещё не начавшиеся
        if p.start_date and now < p.start_date:
            continue
        
        result.append({
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "promo_type": p.promo_type,
            "discount_value": p.discount_value,
            "min_order_amount": p.min_order_amount,
            "buy_quantity": p.buy_quantity,
            "get_quantity": p.get_quantity,
            "apply_to": p.apply_to,
            "apply_category": p.apply_category,
            "product_ids": p.product_ids,
            "gift_product_name": p.gift_product_name,
            "end_date": p.end_date,
        })
    
    return result


@router.get("/product/{product_id}")
def get_product_promotions(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Получить активные акции для конкретного продукта"""
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    
    promotions = db.query(Promotion).filter(
        Promotion.seller_phone == product.seller_phone,
        Promotion.is_active == True
    ).all()
    
    result = []
    now = datetime.utcnow()
    
    for p in promotions:
        # Проверка даты
        if p.has_end_date and p.end_date and now > p.end_date:
            continue
        if p.start_date and now < p.start_date:
            continue
        
        # Проверка применимости
        applies = False
        
        if p.apply_to == "all":
            applies = True
        elif p.apply_to == "category" and p.apply_category == product.category:
            applies = True
        elif p.apply_to == "products" and p.product_ids and product_id in p.product_ids:
            applies = True
        
        if applies:
            result.append({
                "id": p.id,
                "title": p.title,
                "promo_type": p.promo_type,
                "discount_value": p.discount_value,
                "min_order_amount": p.min_order_amount,
                "buy_quantity": p.buy_quantity,
                "get_quantity": p.get_quantity,
                "gift_product_name": p.gift_product_name,
            })
    
    return result