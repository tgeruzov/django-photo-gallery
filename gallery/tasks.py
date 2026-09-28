import logging

from celery import shared_task
from django.conf import settings
from django.db.utils import OperationalError

from .image_utils import ImageProcessingError
from .services import ensure_photo_derivatives_by_id, photos_missing_derivatives

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


@shared_task
def backfill_missing_derivatives():
    """Периодическая самопочинка: доделывает варианты, потерянные воркером.

    Если брокер принял задачу, но воркер умер до выполнения (или ретраи
    исчерпаны), фото остаётся без вариантов. Beat-расписание добирает такие
    записи пачками.
    """
    photo_ids = list(photos_missing_derivatives().values_list("id", flat=True)[:100])
    for photo_id in photo_ids:
        ensure_photo_derivatives_task.delay(photo_id)
    return len(photo_ids)


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
