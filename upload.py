import os
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from dependencies import get_current_user
from models import User

router = APIRouter(prefix="/upload", tags=["Загрузка файлов"])

# Настройка Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Загрузить фото в Cloudinary и получить URL"""
    
    # Проверка типа файла
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемый формат. Используйте JPG, PNG или WEBP"
        )
    
    # Проверка размера (макс 5 МБ)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Файл слишком большой. Максимум 5 МБ"
        )
    
    try:
        # Загружаем в Cloudinary
        result = cloudinary.uploader.upload(
            contents,
            folder=f"rizq/{current_user.role}s/{current_user.id}",
            resource_type="image",
            transformation=[
                {"width": 800, "height": 800, "crop": "limit"},
                {"quality": "auto"},
                {"fetch_format": "auto"}
            ]
        )
        
        return {
            "success": True,
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "width": result["width"],
            "height": result["height"],
            "format": result["format"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка загрузки: {str(e)}"
        )


@router.delete("/image/{public_id:path}")
async def delete_image(
    public_id: str,
    current_user: User = Depends(get_current_user)
):
    """Удалить фото из Cloudinary"""
    try:
        result = cloudinary.uploader.destroy(public_id)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка удаления: {str(e)}"
        )