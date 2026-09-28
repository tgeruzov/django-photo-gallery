from django.core.management.base import BaseCommand

from gallery.image_utils import ImageProcessingError
from gallery.services import ensure_photo_derivatives_by_id, photos_missing_derivatives


class Command(BaseCommand):
    help = (
        "Синхронно достраивает недостающие optimized/thumbnail варианты. "
        "Для окружений без Celery beat: запускать вручную или по cron."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=0, help="Обработать не больше N фото (0 - все)."
        )

    def handle(self, *args, limit, **options):
        photo_ids = photos_missing_derivatives().values_list("id", flat=True)
        if limit > 0:
            photo_ids = photo_ids[:limit]

        processed = failed = 0
        for photo_id in list(photo_ids):
            try:
                if ensure_photo_derivatives_by_id(photo_id):
                    processed += 1
            except (ImageProcessingError, OSError) as exc:
                failed += 1
                self.stderr.write(f"Photo {photo_id}: {exc}")

        self.stdout.write(f"Processed: {processed}, failed: {failed}.")
