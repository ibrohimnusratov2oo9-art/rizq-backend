from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from pydantic import BaseModel
import hashlib

from database import SessionLocal
from models import User
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Авторизация"])

SECRET_KEY = "SECRET123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ХЭШИРОВАНИЕ
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

# MODELS
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserRegister(BaseModel):
    phone: str
    password: str
    role: str
    full_name: str | None = None
    email: str | None = None

# CREATE TOKEN
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# REGISTER
@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким номером уже существует")

    if user_data.role not in ["customer", "seller", "courier"]:
        raise HTTPException(status_code=400, detail="Неверная роль")

    hashed_pwd = hash_password(user_data.password)

    new_user = User(
        phone=user_data.phone,
        password=hashed_pwd,
        role=user_data.role,
        full_name=user_data.full_name,
        email=user_data.email,
        is_verified=False if user_data.role == "courier" else True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Регистрация успешна",
        "phone": new_user.phone,
        "role": new_user.role,
        "user_id": new_user.id,
        "needs_verification": new_user.role == "courier"
    }

# LOGIN
@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == form_data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    if not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Неверный пароль")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Аккаунт заблокирован")

    access_token = create_access_token({
        "sub": user.phone,
        "id": user.id,
        "phone": user.phone,
        "role": user.role
    })

    return {"access_token": access_token, "token_type": "bearer"}

# ME
@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "phone": current_user.phone,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "passport_photo": current_user.passport_photo,
        "selfie_photo": current_user.selfie_photo,
        "selfie_with_passport": current_user.selfie_with_passport,
    }