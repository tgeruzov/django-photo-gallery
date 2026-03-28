from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Photo
from .services import ensure_photo_derivatives_by_id


@receiver(post_save, sender=Photo)
def ensure_derivatives_on_save(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return

    has_source = bool(instance.image or instance.optimized_image)
    needs_variants = not instance.optimized_image or not instance.thumbnail
    should_delete_original = bool(
        getattr(settings, "DELETE_ORIGINAL_AFTER_OPTIMIZE", False) and instance.image
    )

    if not has_source:
        return

    if not (needs_variants or should_delete_original):
        return

    transaction.on_commit(lambda: ensure_photo_derivatives_by_id(instance.pk))
