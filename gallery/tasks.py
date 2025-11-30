from PIL import Image, ExifTags
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
import logging
import os
from .models import Photo

logger = logging.getLogger(__name__)

# Костыль для ориентации, но работает
ORIENTATION_TAG = next((tag for tag, name in ExifTags.TAGS.items() if name == 'Orientation'), None)

def fix_image_rotation(img):
    """Исправляет поворот изображения из EXIF"""
    if not hasattr(img, '_getexif') or ORIENTATION_TAG is None:
        return img
    try:
        exif = img._getexif()
        if exif is None:
            return img
        orientation = exif.get(ORIENTATION_TAG, 1)
        if orientation == 3:
            img = img.rotate(180, expand=True)
        elif orientation == 6:
            img = img.rotate(270, expand=True)
        elif orientation == 8:
            img = img.rotate(90, expand=True)
    except Exception:
        logger.warning("Не удалось обработать EXIF ориентацию")
    return img

def create_thumbnail(image_path, size=(600, 600), quality=90, format='WEBP'):
    """Создает миниатюру и возвращает BytesIO"""
    try:
        with Image.open(image_path) as img:
            img = fix_image_rotation(img)
            img = img.convert('RGB')
            img.thumbnail(size, Image.Resampling.LANCZOS)
            thumb_io = BytesIO()
            save_kwargs = {'format': format, 'quality': quality}
            if format == 'WEBP':
                save_kwargs['method'] = 6
            img.save(thumb_io, **save_kwargs)
            thumb_io.seek(0)
            return thumb_io
    except FileNotFoundError:
        logger.error(f"Файл не найден: {image_path}")
        return None
    except Exception as e:
        logger.error(f"Ошибка создания миниатюры для {image_path}: {e}")
        return None

def create_thumbnail_for_photo(photo_id):
    """Создает миниатюру для фото"""
    try:
        with transaction.atomic():
            photo = Photo.objects.select_for_update().get(pk=photo_id)
            if photo.thumbnail:
                logger.info(f"Миниатюра для Photo ID {photo_id} уже существует")
                return f"Миниатюра уже есть для {photo_id}"
            
            if not photo.image or not photo.image.path:
                logger.error(f"Оригинальное изображение отсутствует для Photo ID {photo_id}")
                return f"Ошибка: оригинал отсутствует для {photo_id}"

            thumb_io = create_thumbnail(photo.image.path)
            if thumb_io:
                base_name = os.path.splitext(os.path.basename(photo.image.name))[0]
                thumbnail_filename = f"{base_name}_thumb.webp"
                thumbnail_file = InMemoryUploadedFile(
                    thumb_io, 'ImageField', thumbnail_filename, 'image/webp', thumb_io.tell(), None
                )
                photo.thumbnail.save(thumbnail_filename, thumbnail_file, save=True)
                logger.info(f"Миниатюра создана для Photo ID {photo_id}")
                return f"Миниатюра создана для {photo_id}"
            return f"Ошибка генерации миниатюры для {photo_id}"
    except Photo.DoesNotExist:
        logger.error(f"Photo ID {photo_id} не найден")
        return f"Ошибка: Photo ID {photo_id} не найден"
    except Exception as exc:
        logger.exception(f"Ошибка при обработке Photo ID {photo_id}: {exc}")
        raise