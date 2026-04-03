from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import SessionLocal
from models import User
from dependencies import get_current_user   # мы создадим этот файл позже

router = APIRouter(prefix="/auth", tags=["Авторизация"])

SECRET_KEY = "SECRET123"   # потом вынесем в .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ================== DEPENDENCY ==================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ================== Pydantic Models ==================
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserRegister(BaseModel):
    phone: str
    password: str
    role: str
    full_name: str | None = None

# ================== CREATE TOKEN ==================
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ================== REGISTER ==================
@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    # Проверка, существует ли уже такой телефон
    existing = db.query(User).filter(User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким номером уже существует")

    if user_data.role not in ["customer", "seller", "courier"]:
        raise HTTPException(status_code=400, detail="Неверная роль")

    new_user = User(
        phone=user_data.phone,
        role=user_data.role,
        full_name=user_data.full_name
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Регистрация успешна", "phone": new_user.phone, "role": new_user.role}

# ================== LOGIN ==================
@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == form_data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    # Пока пароль простой (1234). Позже добавим хэширование
    if form_data.password != "1234":
        raise HTTPException(status_code=401, detail="Неверный пароль")

    access_token = create_access_token({
        "sub": user.phone,
        "id": user.id,
        "phone": user.phone,
        "role": user.role
    })

    return {"access_token": access_token, "token_type": "bearer"}

# ================== ME ==================
@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "phone": current_user.phone,
        "role": current_user.role,
        "full_name": current_user.full_name
    }