from django.db import transaction
import logging
from .models import Photo
from .image_utils import build_thumbnail_content, open_image_from_path, ImageProcessingError

logger = logging.getLogger(__name__)

def create_thumbnail_for_photo(photo_id):
    """Создает миниатюру для фото"""
    try:
        with transaction.atomic():
            photo = Photo.objects.select_for_update().get(pk=photo_id)
            if photo.thumbnail:
                logger.info(f"Миниатюра для Photo ID {photo_id} уже существует")
                return f"Миниатюра уже есть для {photo_id}"

            source_image = photo.optimized_image or photo.image
            if not source_image:
                logger.error(f"Оригинальное изображение отсутствует для Photo ID {photo_id}")
                return f"Ошибка: оригинал отсутствует для {photo_id}"

            img = open_image_from_path(source_image.path)
            thumbnail_content = build_thumbnail_content(img, source_image.name)
            photo.thumbnail.save(thumbnail_content.name, thumbnail_content, save=True)
            logger.info(f"Миниатюра создана для Photo ID {photo_id}")
            return f"Миниатюра создана для {photo_id}"
    except Photo.DoesNotExist:
        logger.error(f"Photo ID {photo_id} не найден")
        return f"Ошибка: Photo ID {photo_id} не найден"
    except ImageProcessingError as exc:
        logger.error("Ошибка генерации миниатюры для %s: %s", photo_id, exc)
        return f"Ошибка генерации миниатюры для {photo_id}"
    except Exception as exc:
        logger.exception(f"Ошибка при обработке Photo ID {photo_id}: {exc}")
        raise
