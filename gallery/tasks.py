import logging

from .image_utils import ImageProcessingError
from .services import ensure_photo_derivatives_by_id

logger = logging.getLogger(__name__)


def ensure_photo_derivatives_task(photo_id):
    """
    Compatibility wrapper retained for older imports.

    Shared hosting on Timeweb runs the derivative generation inline inside the
    current request, admin action, or cron job instead of relying on a worker queue.
    """
    try:
        return ensure_photo_derivatives_by_id(photo_id)
    except ImageProcessingError as exc:
        logger.warning("Permanent image processing error for photo %s: %s", photo_id, exc)
        return False


def schedule_photo_derivatives(photo_id):
    """Process derivative files inline for a single photo."""
    try:
        updated = ensure_photo_derivatives_by_id(photo_id)
    except ImageProcessingError as exc:
        logger.warning("Inline derivative generation failed for photo %s: %s", photo_id, exc)
        return "failed"
    except Exception:
        logger.exception("Inline derivative generation failed for photo %s.", photo_id)
        return "failed"

    return "processed" if updated else "skipped"


def create_thumbnail_for_photo(photo_id):
    """Backward-compatible wrapper retained for older imports."""
    return ensure_photo_derivatives_by_id(photo_id)
