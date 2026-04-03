from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/sellers", tags=["Продавцы"])

SELLERS_DB = {}


class SellerCreate(BaseModel):
    owner_phone: str
    name: str
    seller_type: str  # restaurant / market
    categories: List[str]


@router.post("/create")
def create_seller(data: SellerCreate):
    if data.name in SELLERS_DB:
        return {"error": "Продавец уже существует"}

    if data.seller_type not in ["restaurant", "market"]:
        return {"error": "Неверный тип продавца"}

    SELLERS_DB[data.name] = {
        "owner_phone": data.owner_phone,
        "name": data.name,
        "seller_type": data.seller_type,
        "categories": data.categories
    }

    return {
        "message": "Продавец успешно создан",
        "seller": SELLERS_DB[data.name]
    }


@router.get("/")
def list_sellers():
    return list(SELLERS_DB.values())
