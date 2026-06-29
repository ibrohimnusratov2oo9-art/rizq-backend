from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine
from models import Base

# Импортируем роутеры
from auth import router as auth_router
from orders import router as orders_router
from products import router as products_router
from sellers import router as sellers_router
from users import router as users_router
from onboarding import router as onboarding_router
from subscriptions import router as subscriptions_router  # ← НОВОЕ!
from admin import router as admin_router
from chat import router as chat_router

# Создаём таблицы при запуске
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RIZQ API",
    description="API сервиса доставки RIZQ (Душанбе)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # позже сделаем строже
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальный обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return {"ok": False, "error": str(exc)}

# Подключаем роутеры с префиксом
API_PREFIX = "/api/v1"

app.include_router(onboarding_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(sellers_router, prefix=API_PREFIX)
app.include_router(products_router, prefix=API_PREFIX)
app.include_router(orders_router, prefix=API_PREFIX)
app.include_router(subscriptions_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(chat_router, prefix=API_PREFIX)  # ← НОВОЕ!
@app.get("/")
def root():
    return {
        "status": "RIZQ server is running",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "RIZQ"}