from fastapi import APIRouter

from onboarding import router as onboarding_router
from users import router as users_router
from auth import router as auth_router
from orders import router as orders_router
from products import router as products_router
from sellers import router as sellers_router

router = APIRouter()

# подключаем все модули
router.include_router(onboarding_router)
router.include_router(users_router)
router.include_router(auth_router)
router.include_router(orders_router)
router.include_router(products_router)
router.include_router(sellers_router)
