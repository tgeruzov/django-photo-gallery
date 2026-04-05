from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from gallery.models import Photo
from gallery.tasks import schedule_photo_derivatives


class Command(BaseCommand):
    help = "Backfill missing optimized images and thumbnails in small synchronous batches."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            help="Maximum number of photos to process in one run.",
        )

    def handle(self, *args, **options):
        limit = max(1, options["limit"])

        pending_filter = (
            Q(optimized_image__isnull=True)
            | Q(optimized_image="")
            | Q(thumbnail__isnull=True)
            | Q(thumbnail="")
        )
        if getattr(settings, "DELETE_ORIGINAL_AFTER_OPTIMIZE", False):
            pending_filter |= Q(image__isnull=False) & ~Q(image="")

        photo_ids = list(
            Photo.objects.filter(pending_filter)
            .order_by("uploaded_at", "pk")
            .values_list("pk", flat=True)[:limit]
        )

        processed = 0
        skipped = 0
        failed = 0

        for photo_id in photo_ids:
            result = schedule_photo_derivatives(photo_id)
            if result == "processed":
                processed += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

        self.stdout.write(
            "Derivative batch completed: "
            f"checked={len(photo_ids)}, processed={processed}, skipped={skipped}, failed={failed}."
        )
