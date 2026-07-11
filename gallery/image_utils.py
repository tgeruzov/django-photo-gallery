import logging
import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .constants import (
    OPTIMIZED_IMAGE_QUALITY,
    OPTIMIZED_IMAGE_SIZE,
    THUMBNAIL_FORMAT,
    THUMBNAIL_QUALITY,
    THUMBNAIL_SIZE,
)

logger = logging.getLogger(__name__)

# Pillow safety guard (DecompressionBombError)
MAX_IMAGE_PIXELS = getattr(settings, "MAX_IMAGE_PIXELS", None)
if MAX_IMAGE_PIXELS:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

class ImageProcessingError(Exception):
    pass


def fix_image_rotation(img):
    """Разворачивает изображение по EXIF Orientation (включая зеркальные 2/4/5/7)."""
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        logger.warning("Не удалось обработать EXIF ориентацию")
        return img


def normalize_image_mode(img):
    """Сохраняет альфа-канал (WEBP его поддерживает), остальное приводит к RGB."""
    if img.mode in ("RGBA", "LA", "P"):
        return img.convert("RGBA")
    return img.convert("RGB")


def _open_image(image_source):
    try:
        img = Image.open(image_source)
        img.load()
        img_copy = img.copy()
        return img_copy
    except Image.DecompressionBombError as exc:
        raise ImageProcessingError("Слишком большое изображение (слишком много пикселей).") from exc
    except UnidentifiedImageError as exc:
        raise ImageProcessingError("Файл не является корректным изображением.") from exc
    except OSError as exc:
        raise ImageProcessingError("Не удалось прочитать изображение.") from exc


def open_image_from_file(file_obj):
    file_obj.seek(0)
    img = _open_image(file_obj)
    file_obj.seek(0)
    img = fix_image_rotation(img)
    return normalize_image_mode(img)


def open_image_from_path(image_path):
    try:
        with open(image_path, "rb") as fh:
            img = _open_image(fh)
    except FileNotFoundError as exc:
        raise ImageProcessingError("Файл не найден.") from exc
    img = fix_image_rotation(img)
    return normalize_image_mode(img)


def make_image_variant_buffer(img, size, quality, fmt):
    img_copy = img.copy()
    img_copy.thumbnail(size, Image.Resampling.LANCZOS)
    if fmt.upper() in {"JPEG", "JPG"} and img_copy.mode not in ("RGB", "L"):
        # JPEG не умеет альфу — страховка на случай смены THUMBNAIL_FORMAT
        img_copy = img_copy.convert("RGB")
    buffer = BytesIO()
    save_kwargs = {"format": fmt, "quality": quality}
    if fmt.upper() == "WEBP":
        save_kwargs["method"] = 4  # баланс скорость/размер (6 — самый медленный)
    img_copy.save(buffer, **save_kwargs)
    buffer.seek(0)
    return buffer, img_copy.size


def make_webp_content(img, size, quality, suffix, base_name):
    buffer, dimensions = make_image_variant_buffer(img, size, quality, "WEBP")
    filename = f"{base_name}{suffix}.webp"
    content = ContentFile(buffer.getvalue(), name=filename)
    content.image_dimensions = dimensions
    return content


def build_optimized_content(img, original_name):
    base_name = os.path.splitext(os.path.basename(original_name))[0]
    return make_webp_content(
        img, OPTIMIZED_IMAGE_SIZE, OPTIMIZED_IMAGE_QUALITY, "_optimized", base_name
    )


def build_thumbnail_content(img, original_name):
    base_name = os.path.splitext(os.path.basename(original_name))[0]
    if THUMBNAIL_FORMAT.upper() == "WEBP":
        return make_webp_content(img, THUMBNAIL_SIZE, THUMBNAIL_QUALITY, "_thumb", base_name)
    buffer, dimensions = make_image_variant_buffer(
        img, THUMBNAIL_SIZE, THUMBNAIL_QUALITY, THUMBNAIL_FORMAT
    )
    filename = f"{base_name}_thumb.{THUMBNAIL_FORMAT.lower()}"
    content = ContentFile(buffer.getvalue(), name=filename)
    content.image_dimensions = dimensions
    return content
