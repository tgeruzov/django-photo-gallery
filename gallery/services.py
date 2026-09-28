import hashlib
import logging
import os

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.db.models import Q

from .image_utils import (
    build_optimized_content,
    build_thumbnail_content,
    open_image_from_file,
)
from .models import Photo

logger = logging.getLogger(__name__)


class DuplicatePhotoError(Exception):
    """Файл с таким содержимым уже загружен в галерею."""


def compute_upload_hash(uploaded_file: UploadedFile) -> str:
    """Считает SHA-256 загружаемого файла почанково и возвращает hex-строку."""
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def cleanup_saved_photo_files(photo: Photo) -> None:
    """Подчищает файлы, записанные в storage до отката транзакции БД."""
    for field_name in ("image", "optimized_image", "thumbnail"):
        file_field = getattr(photo, field_name, None)
        if not file_field:
            continue
        try:
            file_field.delete(save=False)
        except OSError:
            logger.warning("Failed to clean up %s for photo rollback.", field_name)


def save_uploaded_photo(uploaded_file: UploadedFile) -> Photo:
    """Сохраняет оригинал загрузки; варианты генерируются после коммита.

    Варианты (optimized + thumbnail) создаёт post_save-сигнал через
    schedule_photo_derivatives — в Celery-воркере или inline-фолбэком, —
    чтобы HTTP-запрос не ждал перекодирования. Оригинал пишется в storage
    потоково, без чтения файла целиком в память.
    """
    uploaded_file.seek(0)
    original_name = os.path.basename(uploaded_file.name)

    content_hash = compute_upload_hash(uploaded_file)
    if Photo.objects.filter(content_hash=content_hash).exists():
        raise DuplicatePhotoError("такое фото уже загружено")

    photo = Photo(content_hash=content_hash)
    try:
        with transaction.atomic():
            photo.image.save(original_name, uploaded_file, save=False)
            photo.save()
    except IntegrityError as exc:
        # Гонка двух одинаковых загрузок: unique-констрейнт поймал вторую.
        cleanup_saved_photo_files(photo)
        raise DuplicatePhotoError("такое фото уже загружено") from exc
    except Exception:
        cleanup_saved_photo_files(photo)
        raise

    return photo


def photos_missing_derivatives():
    """Фото, у которых есть исходник, но не хватает вариантов."""
    return (
        Photo.objects.filter(Q(optimized_image="") | Q(thumbnail=""))
        .exclude(image="", optimized_image="")
        .order_by("id")
    )


def ensure_photo_derivatives_by_id(photo_id: int) -> bool:
    """Достраивает optimized и thumbnail для существующего фото по id.

    Перекодирование идёт вне транзакции: select_for_update держится только
    на короткую запись результата, а не на всё время работы Pillow.
    """
    try:
        photo = Photo.objects.get(pk=photo_id)
    except Photo.DoesNotExist:
        logger.warning("Photo %s was removed before derivatives were generated.", photo_id)
        return False

    variants = build_missing_variants(photo)
    if variants is None:
        return False

    try:
        with transaction.atomic():
            try:
                locked = Photo.objects.select_for_update().get(pk=photo_id)
            except Photo.DoesNotExist:
                logger.warning("Photo %s was removed while derivatives were generated.", photo_id)
                return False
            return apply_variants(locked, variants)
    except Exception:
        # Транзакция откатилась, а файлы в storage уже записаны
        for field_name in variants:
            saved_name = variants[field_name].saved_name
            if saved_name:
                photo._meta.get_field(field_name).storage.delete(saved_name)
        raise


def build_missing_variants(photo: Photo) -> dict | None:
    """Готовит недостающие варианты в памяти; None, если делать нечего."""
    source_image = photo.image or photo.optimized_image
    if not source_image:
        logger.warning("Photo %s has no source image for derivative generation.", photo.pk)
        return None

    missing_optimized = not photo.optimized_image
    missing_thumbnail = not photo.thumbnail
    if not (missing_optimized or missing_thumbnail or should_delete_original(photo)):
        return None

    variants = {}
    if missing_optimized or missing_thumbnail:
        # Через storage, а не .path: работает с любым бэкендом, не только с диском
        with source_image.open("rb") as fh:
            image = open_image_from_file(fh)
        if missing_optimized:
            variants["optimized_image"] = build_optimized_content(image, source_image.name)
        if missing_thumbnail:
            variants["thumbnail"] = build_thumbnail_content(image, source_image.name)
    for content in variants.values():
        content.saved_name = None
    return variants


def should_delete_original(photo: Photo) -> bool:
    return bool(getattr(settings, "DELETE_ORIGINAL_AFTER_OPTIMIZE", False) and photo.image)


def apply_variants(photo: Photo, variants: dict) -> bool:
    """Записывает подготовленные варианты в заблокированную строку фото."""
    update_fields = []
    dimension_fields = {
        "optimized_image": ("optimized_width", "optimized_height"),
        "thumbnail": ("thumbnail_width", "thumbnail_height"),
    }

    for field_name, content in variants.items():
        # Параллельный воркер мог успеть раньше - его результат не трогаем
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
    logger.info(
        "Generated missing derivatives for photo %s (%s).", photo.pk, ", ".join(update_fields)
    )
    return True
