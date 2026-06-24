from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from database import SessionLocal
from models import Product, Seller, User
from auth import get_current_user

router = APIRouter(prefix="/products", tags=["Товары"])


# ================== DB ==================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================== SCHEMAS ==================
class ProductCreate(BaseModel):
    name: str
    price: float
    description: Optional[str] = None
    category: Optional[str] = "main"
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None


# ================== ДОБАВИТЬ ТОВАР ==================
@router.post("/add")
def add_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Добавить товар (только seller)"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец может добавлять товары")
    
    # Проверяем что у него есть ресторан
    seller = db.query(Seller).filter(Seller.phone == current_user.phone).first()
    if not seller:
        raise HTTPException(status_code=400, detail="Сначала создайте ресторан")
    
    if data.price <= 0:
        raise HTTPException(status_code=400, detail="Цена должна быть больше 0")
    
    new_product = Product(
        seller_phone=current_user.phone,
        name=data.name,
        price=data.price,
        description=data.description,
        category=data.category or "main",
        image_url=data.image_url,
        is_available=True
    )
    
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    return {
        "message": "Товар добавлен!",
        "product": {
            "id": new_product.id,
            "name": new_product.name,
            "price": new_product.price,
            "description": new_product.description,
            "category": new_product.category,
            "image_url": new_product.image_url,
            "is_available": new_product.is_available
        }
    }


# ================== СПИСОК ТОВАРОВ РЕСТОРАНА ==================
@router.get("/seller/{seller_phone}")
def get_products_by_seller(seller_phone: str, db: Session = Depends(get_db)):
    """Получить товары конкретного ресторана"""
    
    products = db.query(Product).filter(
        Product.seller_phone == seller_phone,
        Product.is_available == True
    ).all()
    
    return [
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


# ================== МОИ ТОВАРЫ (для seller) ==================
@router.get("/my/products")
def my_products(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить свои товары"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")
    
    products = db.query(Product).filter(
        Product.seller_phone == current_user.phone
    ).all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "description": p.description,
            "category": p.category,
            "image_url": p.image_url,
            "is_available": p.is_available,
            "created_at": p.created_at + timedelta(hours=5)
        }
        for p in products
    ]


# ================== ОБНОВИТЬ ТОВАР ==================
@router.put("/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновить товар"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    if product.seller_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Это не ваш товар")
    
    if data.name is not None:
        product.name = data.name
    if data.price is not None:
        if data.price <= 0:
            raise HTTPException(status_code=400, detail="Цена должна быть больше 0")
        product.price = data.price
    if data.description is not None:
        product.description = data.description
    if data.category is not None:
        product.category = data.category
    if data.image_url is not None:
        product.image_url = data.image_url
    if data.is_available is not None:
        product.is_available = data.is_available
    
    db.commit()
    db.refresh(product)
    
    return {
        "message": "Товар обновлён",
        "product": {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "category": product.category,
            "is_available": product.is_available
        }
    }


# ================== УДАЛИТЬ ТОВАР ==================
@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удалить товар"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    if product.seller_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Это не ваш товар")
    
    db.delete(product)
    db.commit()
    
    return {"message": "Товар удалён"}


# ================== ВКЛЮЧИТЬ/ВЫКЛЮЧИТЬ ТОВАР ==================
@router.post("/{product_id}/toggle")
def toggle_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Включить или выключить товар"""
    
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Только продавец")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    if product.seller_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Это не ваш товар")
    
    product.is_available = not product.is_available
    db.commit()
    
    return {
        "message": "Статус изменён",
        "is_available": product.is_available
    }


# ================== ПОИСК ТОВАРОВ ==================
@router.get("/search/{query}")
def search_products(query: str, db: Session = Depends(get_db)):
    """Поиск товаров по названию"""
    
    products = db.query(Product).filter(
        Product.is_available == True,
        Product.name.ilike(f"%{query}%")
    ).all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "description": p.description,
            "category": p.category,
            "image_url": p.image_url,
            "seller_phone": p.seller_phone
        }
        for p in products
    ]