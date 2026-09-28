import hashlib
import logging
import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Photo

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
THUMBNAIL_SIZE = (800, 800)
THUMBNAIL_QUALITY = 82
OPTIMIZED_IMAGE_SIZE = (2560, 2560)
OPTIMIZED_IMAGE_QUALITY = 85


class ImageProcessingError(Exception):
    pass


class DuplicatePhotoError(Exception):
    """Файл с таким содержимым уже загружен в галерею."""


def open_image(file_obj) -> Image.Image:
    """Читает изображение с EXIF-поворотом; RGBA для прозрачных, иначе RGB."""
    file_obj.seek(0)
    try:
        img = Image.open(file_obj)
        img.load()
        img = img.copy()
    except Image.DecompressionBombError as exc:
        raise ImageProcessingError("Слишком большое изображение (слишком много пикселей).") from exc
    except UnidentifiedImageError as exc:
        raise ImageProcessingError("Файл не является корректным изображением.") from exc
    except OSError as exc:
        raise ImageProcessingError("Не удалось прочитать изображение.") from exc
    finally:
        file_obj.seek(0)

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        logger.warning("Не удалось обработать EXIF ориентацию")
    return img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")


def make_webp(img: Image.Image, size, quality, source_name, suffix) -> ContentFile:
    """Уменьшенная WEBP-копия; итоговый размер кладётся в image_dimensions."""
    copy = img.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    copy.save(buffer, format="WEBP", quality=quality, method=4)
    base_name = os.path.splitext(os.path.basename(source_name))[0]
    content = ContentFile(buffer.getvalue(), name=f"{base_name}{suffix}.webp")
    content.image_dimensions = copy.size
    content.saved_name = None
    return content


def compute_upload_hash(uploaded_file) -> str:
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def save_uploaded_photo(uploaded_file) -> Photo:
    """Сохраняет оригинал и сразу строит миниатюру и оптимизированную версию.

    Если файл не удалось декодировать, запись удаляется, а ошибка
    пробрасывается - в галерее не остаётся фото без превью.
    """
    content_hash = compute_upload_hash(uploaded_file)
    if Photo.objects.filter(content_hash=content_hash).exists():
        raise DuplicatePhotoError("такое фото уже загружено")

    photo = Photo(content_hash=content_hash)
    try:
        with transaction.atomic():
            photo.image.save(os.path.basename(uploaded_file.name), uploaded_file, save=False)
            photo.save()
    except IntegrityError as exc:
        # Гонка двух одинаковых загрузок: unique-констрейнт поймал вторую
        photo.image.delete(save=False)
        raise DuplicatePhotoError("такое фото уже загружено") from exc
    except Exception:
        if photo.image:
            photo.image.delete(save=False)
        raise

    try:
        ensure_photo_derivatives_by_id(photo.pk)
    except Exception:
        photo.delete()
        raise
    return photo


def ensure_photo_derivatives_by_id(photo_id: int) -> bool:
    """Достраивает недостающие варианты фото; True, если что-то записано.

    Перекодирование идёт вне транзакции: select_for_update держится только
    на короткую запись результата, а не на всё время работы Pillow.
    """
    try:
        photo = Photo.objects.get(pk=photo_id)
    except Photo.DoesNotExist:
        return False

    variants = build_missing_variants(photo)
    if variants is None:
        return False

    try:
        with transaction.atomic():
            locked = Photo.objects.select_for_update().filter(pk=photo_id).first()
            return bool(locked) and apply_variants(locked, variants)
    except Exception:
        # Транзакция откатилась, а файлы в storage уже записаны
        for field_name, content in variants.items():
            if content.saved_name:
                photo._meta.get_field(field_name).storage.delete(content.saved_name)
        raise


def should_delete_original(photo: Photo) -> bool:
    return bool(settings.DELETE_ORIGINAL_AFTER_OPTIMIZE and photo.image)


def build_missing_variants(photo: Photo) -> dict | None:
    """Готовит недостающие варианты в памяти; None, если делать нечего."""
    source = photo.image or photo.optimized_image
    if not source:
        return None
    missing_optimized = not photo.optimized_image
    missing_thumbnail = not photo.thumbnail
    if not (missing_optimized or missing_thumbnail or should_delete_original(photo)):
        return None

    variants = {}
    if missing_optimized or missing_thumbnail:
        with source.open("rb") as fh:
            img = open_image(fh)
        if missing_optimized:
            variants["optimized_image"] = make_webp(
                img, OPTIMIZED_IMAGE_SIZE, OPTIMIZED_IMAGE_QUALITY, source.name, "_optimized"
            )
        if missing_thumbnail:
            variants["thumbnail"] = make_webp(
                img, THUMBNAIL_SIZE, THUMBNAIL_QUALITY, source.name, "_thumb"
            )
    return variants


def apply_variants(photo: Photo, variants: dict) -> bool:
    """Записывает подготовленные варианты в заблокированную строку фото."""
    dimension_fields = {
        "optimized_image": ("optimized_width", "optimized_height"),
        "thumbnail": ("thumbnail_width", "thumbnail_height"),
    }
    update_fields = []
    for field_name, content in variants.items():
        # Параллельный запрос мог успеть раньше - его результат не трогаем
        if getattr(photo, field_name):
            continue
        getattr(photo, field_name).save(content.name, content, save=False)
        content.saved_name = getattr(photo, field_name).name
        width_field, height_field = dimension_fields[field_name]
        setattr(photo, width_field, content.image_dimensions[0])
        setattr(photo, height_field, content.image_dimensions[1])
        update_fields.extend([field_name, width_field, height_field])

    if should_delete_original(photo) and photo.optimized_image and photo.thumbnail:
        # Оригинал удаляется только после коммита: при откате он должен остаться
        storage, original_name = photo.image.storage, photo.image.name
        photo.image = ""
        transaction.on_commit(lambda: storage.delete(original_name))
        update_fields.append("image")

    if not update_fields:
        return False
    photo.save(update_fields=update_fields)
    return True
