from .services import ensure_photo_derivatives_by_id


def create_thumbnail_for_photo(photo_id):
    """Backward-compatible wrapper around the derivative backfill service."""
    return ensure_photo_derivatives_by_id(photo_id)
