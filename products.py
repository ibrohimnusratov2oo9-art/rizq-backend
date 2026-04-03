from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/products", tags=["Товары"])

PRODUCTS_DB = []


class ProductCreate(BaseModel):
    seller_name: str
    name: str
    price: int
    category: str


@router.post("/add")
def add_product(data: ProductCreate):
    product = {
        "seller_name": data.seller_name,
        "name": data.name,
        "price": data.price,
        "category": data.category
    }
    PRODUCTS_DB.append(product)

    return {
        "message": "Товар успешно добавлен",
        "product": product
    }


@router.get("/{seller_name}")
def get_products_by_seller(seller_name: str):
    return [p for p in PRODUCTS_DB if p["seller_name"] == seller_name]
