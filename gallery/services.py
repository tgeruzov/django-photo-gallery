import logging
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from .image_utils import (
    build_optimized_content,
    build_thumbnail_content,
    open_image_from_file,
    open_image_from_path,
)
from .models import Photo

logger = logging.getLogger(__name__)


def cleanup_saved_photo_files(photo):
    """Best-effort cleanup for files written before the DB transaction failed."""
    for field_name in ("image", "optimized_image", "thumbnail"):
        file_field = getattr(photo, field_name, None)
        if not file_field:
            continue
        try:
            file_field.delete(save=False)
        except OSError:
            logger.warning("Failed to clean up %s for photo rollback.", field_name)


def save_uploaded_photo(uploaded_file):
    """Persist the original upload and eagerly generate its derived files."""
    uploaded_file.seek(0)
    image = open_image_from_file(uploaded_file)
    optimized_content = build_optimized_content(image, uploaded_file.name)
    thumbnail_content = build_thumbnail_content(image, uploaded_file.name)

    uploaded_file.seek(0)
    original_name = os.path.basename(uploaded_file.name)
    original_content = ContentFile(uploaded_file.read(), name=original_name)

    photo = Photo()
    try:
        with transaction.atomic():
            photo.image.save(original_name, original_content, save=False)
            photo.optimized_image.save(optimized_content.name, optimized_content, save=False)
            photo.thumbnail.save(thumbnail_content.name, thumbnail_content, save=False)
            photo.save()

            if getattr(settings, "DELETE_ORIGINAL_AFTER_OPTIMIZE", False):
                photo.image.delete(save=False)
                photo.image = ""
                photo.save(update_fields=["image"])
    except Exception:
        cleanup_saved_photo_files(photo)
        raise

    return photo


def ensure_photo_derivatives_by_id(photo_id):
    """Backfill optimized and thumbnail files for an existing photo."""
    try:
        with transaction.atomic():
            photo = Photo.objects.select_for_update().get(pk=photo_id)
            return ensure_photo_derivatives(photo)
    except Photo.DoesNotExist:
        logger.warning("Photo %s was removed before derivatives were generated.", photo_id)
        return False


def ensure_photo_derivatives(photo):
    """Generate any missing image variants for a photo instance."""
    source_image = photo.image or photo.optimized_image
    if not source_image:
        logger.warning("Photo %s has no source image for derivative generation.", photo.pk)
        return False

    missing_optimized = not bool(photo.optimized_image)
    missing_thumbnail = not bool(photo.thumbnail)
    delete_original = bool(
        getattr(settings, "DELETE_ORIGINAL_AFTER_OPTIMIZE", False) and photo.image
    )

    if not (missing_optimized or missing_thumbnail or delete_original):
        return False

    image = open_image_from_path(source_image.path)
    update_fields = []

    if missing_optimized:
        optimized_content = build_optimized_content(image, source_image.name)
        photo.optimized_image.save(optimized_content.name, optimized_content, save=False)
        update_fields.append("optimized_image")

    if missing_thumbnail:
        thumbnail_content = build_thumbnail_content(image, source_image.name)
        photo.thumbnail.save(thumbnail_content.name, thumbnail_content, save=False)
        update_fields.append("thumbnail")

    if delete_original and photo.optimized_image and photo.thumbnail:
        photo.image.delete(save=False)
        photo.image = ""
        update_fields.append("image")

    if update_fields:
        photo.save(update_fields=update_fields)
        logger.info(
            "Generated missing derivatives for photo %s (%s).",
            photo.pk,
            ", ".join(update_fields),
        )
        return True

    return False
