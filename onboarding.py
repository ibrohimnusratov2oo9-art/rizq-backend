from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/onboarding", tags=["Онбординг"])

@router.get("/ads")
def onboarding_ads():
    return {
        "pages": [
            {
                "title": "Добро пожаловать в RIZQ",
                "text": "RIZQ — сервис для заказа еды и товаров рядом с вами"
            },
            {
                "title": "Для кого RIZQ",
                "text": "Покупатели, магазины, рестораны и курьеры"
            },
            {
                "title": "Быстро и удобно",
                "text": "Заказывайте — мы доставим быстро и надёжно"
            }
        ],
        "can_skip": True
    }


@router.get("/languages")
def onboarding_languages():
    return {
        "default": "ru",
        "available": ["ru", "tj", "en"],
        "message": "Доступные языки приложения"
    }


@router.post("/select-role")
def select_role(role: str):
    if role not in ["customer", "seller", "courier"]:
        raise HTTPException(
            status_code=400,
            detail="Неверная роль пользователя"
        )

    roles_ru = {
        "customer": "покупатель",
        "seller": "продавец",
        "courier": "курьер"
    }

    return {
        "message": "Роль успешно выбрана",
        "role": role,
        "role_ru": roles_ru[role]
    }
