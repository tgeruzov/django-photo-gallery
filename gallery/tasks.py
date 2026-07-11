import logging

from celery import shared_task
from django.conf import settings
from django.db.utils import OperationalError

from .image_utils import ImageProcessingError
from .services import ensure_photo_derivatives_by_id

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(OperationalError, OSError),  # только транзиентные ошибки
    dont_autoretry_for=(ImageProcessingError,),  # битый файл ретраить бессмысленно
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    soft_time_limit=120,
    time_limit=180,
)
def ensure_photo_derivatives_task(self, photo_id):
    return ensure_photo_derivatives_by_id(photo_id)


def schedule_photo_derivatives(photo_id):
    if getattr(settings, "ENABLE_BACKGROUND_TASKS", False):
        try:
            ensure_photo_derivatives_task.delay(photo_id)
            return "scheduled"
        except Exception:
            logger.exception(
                "Failed to queue derivative generation for photo %s. Falling back to inline processing.",
                photo_id,
            )

    try:
        updated = ensure_photo_derivatives_by_id(photo_id)
    except Exception:
        logger.exception("Inline derivative generation failed for photo %s.", photo_id)
        return "failed"

    return "processed" if updated else "skipped"


def create_thumbnail_for_photo(photo_id):
    """Backward-compatible wrapper retained for older imports."""
    return ensure_photo_derivatives_by_id(photo_id)
