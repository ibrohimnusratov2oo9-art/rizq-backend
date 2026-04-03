from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["Пользователи"])

# ================== МОДЕЛИ ==================
class UserCreate(BaseModel):
    phone: str
    role: str
    language: str = "ru"


@router.post("/create")
def create_user(user: UserCreate):
    return {
        "message": "Пользователь создан",
        "user": user
    }


# ================== ВРЕМЕННАЯ БАЗА (ПОТОМ PostgreSQL) ==================
USERS_DB = {}


class RegisterRequest(BaseModel):
    phone: str
    language: str = "ru"
    role: str
    email: str | None = None


@router.post("/register")
def register_user(data: RegisterRequest):
    if data.phone in USERS_DB:
        return {"error": "Пользователь уже существует"}

    if data.role not in ["customer", "seller", "courier"]:
        return {"error": "Неверная роль"}

    USERS_DB[data.phone] = data.dict()

    return {
        "message": "Регистрация прошла успешно",
        "user": USERS_DB[data.phone]
    }


@router.get("/{phone}")
def get_user(phone: str):
    user = USERS_DB.get(phone)
    if not user:
        return {"error": "Пользователь не найден"}

    return user
