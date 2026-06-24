from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from database import SessionLocal
from models import Seller, Product, User
from auth import get_current_user

router = APIRouter(prefix="/sellers", tags=["Продавцы"])


# ================== DB ==================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================== SCHEMAS ==================
class SellerCreate(BaseModel):
    name: str
    seller_type: str  # restaurant, cafe, fastfood
    address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class SellerUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_active: Optional[bool] = None


# ================== СОЗДАТЬ РЕСТОРАН ==================
@router.post("/create")
def create_seller(
    data: SellerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создать ресторан (только для seller)"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец может создать ресторан")

    # Проверяем существует ли уже
    existing = db.query(Seller).filter(Seller.phone == current_user.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="У вас уже есть ресторан")

    if data.seller_type not in ["restaurant", "cafe", "fastfood"]:
        raise HTTPException(status_code=400, detail="Тип должен быть: restaurant, cafe, fastfood")

    new_seller = Seller(
        phone=current_user.phone,
        name=data.name,
        seller_type=data.seller_type,
        address=data.address,
        lat=data.lat,
        lng=data.lng,
        is_active=True
    )

    db.add(new_seller)
    db.commit()
    db.refresh(new_seller)

    return {
        "message": "Ресторан создан!",
        "seller": {
            "id": new_seller.id,
            "name": new_seller.name,
            "phone": new_seller.phone,
            "seller_type": new_seller.seller_type,
            "address": new_seller.address,
            "is_active": new_seller.is_active,
            "created_at": new_seller.created_at + timedelta(hours=5)
        }
    }


# ================== СПИСОК ВСЕХ РЕСТОРАНОВ ==================
@router.get("/")
def list_sellers(
    seller_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получить список всех ресторанов (публично)"""
    
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
            "lat": s.lat,
            "lng": s.lng,
            "is_active": s.is_active,
            "created_at": s.created_at + timedelta(hours=5)
        }
        for s in sellers
    ]


# ================== ПОЛУЧИТЬ РЕСТОРАН ПО ID ==================
@router.get("/{seller_id}")
def get_seller(seller_id: int, db: Session = Depends(get_db)):
    """Получить информацию о ресторане"""
    
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    
    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    
    # Получаем товары
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
        "lat": seller.lat,
        "lng": seller.lng,
        "is_active": seller.is_active,
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
    """Получить свой ресторан"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")
    
    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()
    
    if not seller:
        return {
            "has_restaurant": False,
            "message": "У вас нет ресторана. Создайте его!"
        }
    
    # Получаем товары
    products = db.query(Product).filter(Product.seller_phone == seller.phone).all()
    
    return {
        "has_restaurant": True,
        "seller": {
            "id": seller.id,
            "phone": seller.phone,
            "name": seller.name,
            "seller_type": seller.seller_type,
            "address": seller.address,
            "is_active": seller.is_active,
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
    """Обновить свой ресторан"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")
    
    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()
    
    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    
    if data.name is not None:
        seller.name = data.name
    if data.address is not None:
        seller.address = data.address
    if data.lat is not None:
        seller.lat = data.lat
    if data.lng is not None:
        seller.lng = data.lng
    if data.is_active is not None:
        seller.is_active = data.is_active
    
    db.commit()
    db.refresh(seller)
    
    return {
        "message": "Ресторан обновлён",
        "seller": {
            "id": seller.id,
            "name": seller.name,
            "address": seller.address,
            "is_active": seller.is_active
        }
    }


# ================== УДАЛИТЬ РЕСТОРАН (admin) ==================
@router.delete("/{seller_id}")
def delete_seller(
    seller_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удалить ресторан (только админ)"""
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Только админ")
    
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    
    if not seller:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    
    db.delete(seller)
    db.commit()
    
    return {"message": "Ресторан удалён"}