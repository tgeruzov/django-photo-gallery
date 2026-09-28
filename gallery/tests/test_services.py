from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import override_settings

from gallery.image_utils import open_image_from_file
from gallery.models import Photo
from gallery.services import (
    DuplicatePhotoError,
    apply_variants,
    build_missing_variants,
    ensure_photo_derivatives_by_id,
    save_uploaded_photo,
)
from gallery.tasks import schedule_photo_derivatives

from .base import GalleryTestCase, build_test_image


class PhotoServicesTest(GalleryTestCase):
    def test_save_uploaded_photo_creates_all_variants(self):
        with self.captureOnCommitCallbacks(execute=True):
            photo = save_uploaded_photo(build_test_image(filename="service.png"))

        photo.refresh_from_db()
        self.assertTrue(bool(photo.image))
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    def test_save_uploaded_photo_stores_variant_dimensions(self):
        with self.captureOnCommitCallbacks(execute=True):
            photo = save_uploaded_photo(build_test_image(filename="dims.png", size=(64, 48)))

        photo.refresh_from_db()
        self.assertEqual((photo.thumbnail_width, photo.thumbnail_height), (64, 48))
        self.assertEqual((photo.optimized_width, photo.optimized_height), (64, 48))

    def test_save_uploaded_photo_rejects_duplicate_content(self):
        with self.captureOnCommitCallbacks(execute=True):
            save_uploaded_photo(build_test_image(filename="dup.png"))

        with self.assertRaises(DuplicatePhotoError):
            save_uploaded_photo(build_test_image(filename="dup-renamed.png"))

        self.assertEqual(Photo.objects.count(), 1)

    def test_save_uploaded_photo_cleans_up_files_when_database_save_fails(self):
        before_files = {
            path.relative_to(self._temp_media_root)
            for path in Path(self._temp_media_root).rglob("*")
            if path.is_file()
        }

        with (
            patch.object(Photo, "save", side_effect=RuntimeError("db unavailable")),
            self.assertRaises(RuntimeError),
        ):
            save_uploaded_photo(build_test_image(filename="rollback.png"))

        after_files = {
            path.relative_to(self._temp_media_root)
            for path in Path(self._temp_media_root).rglob("*")
            if path.is_file()
        }
        self.assertEqual(after_files, before_files)
        self.assertEqual(Photo.objects.count(), 0)

    @override_settings(DELETE_ORIGINAL_AFTER_OPTIMIZE=True)
    def test_save_uploaded_photo_can_delete_original_after_optimization(self):
        with self.captureOnCommitCallbacks(execute=True):
            photo = save_uploaded_photo(build_test_image(filename="cleanup.png"))
        photo.refresh_from_db()

        self.assertFalse(bool(photo.image))
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    def test_signal_backfills_missing_variants_after_create(self):
        with self.captureOnCommitCallbacks(execute=True):
            photo = Photo.objects.create(image=build_test_image(filename="signal.png"))

        photo.refresh_from_db()
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    def test_backfill_service_generates_missing_thumbnail(self):
        photo = Photo.objects.create(
            image=build_test_image(filename="existing.png"),
            optimized_image=build_test_image(filename="existing_optimized.png"),
        )
        Photo.objects.filter(pk=photo.pk).update(thumbnail="")

        updated = ensure_photo_derivatives_by_id(photo.pk)
        photo.refresh_from_db()

        self.assertTrue(updated)
        self.assertTrue(bool(photo.thumbnail))

    @override_settings(ENABLE_BACKGROUND_TASKS=False)
    def test_schedule_photo_derivatives_processes_inline_when_background_disabled(self):
        photo = Photo.objects.create(image=build_test_image(filename="inline.png"))

        result = schedule_photo_derivatives(photo.pk)
        photo.refresh_from_db()

        self.assertEqual(result, "processed")
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    @override_settings(ENABLE_BACKGROUND_TASKS=True)
    def test_schedule_photo_derivatives_falls_back_inline_when_queueing_fails(self):
        photo = Photo.objects.create(image=build_test_image(filename="fallback.png"))

        with patch("gallery.tasks.ensure_photo_derivatives_task.delay", side_effect=RuntimeError):
            result = schedule_photo_derivatives(photo.pk)

        photo.refresh_from_db()
        self.assertEqual(result, "processed")
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    @override_settings(ENABLE_BACKGROUND_TASKS=True)
    def test_signal_schedules_background_processing_on_commit(self):
        with (
            patch("gallery.signals.schedule_photo_derivatives") as schedule_mock,
            self.captureOnCommitCallbacks(execute=True),
        ):
            photo = Photo.objects.create(image=build_test_image(filename="queued.png"))

        schedule_mock.assert_called_once_with(photo.pk)

    def test_derivatives_work_with_non_filesystem_storage(self):
        in_memory = {
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        with override_settings(STORAGES=in_memory):
            photo = Photo.objects.create(image=build_test_image(filename="memory.png"))
            Photo.objects.filter(pk=photo.pk).update(optimized_image="", thumbnail="")

            self.assertTrue(ensure_photo_derivatives_by_id(photo.pk))

        photo.refresh_from_db()
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    def test_image_is_processed_outside_the_row_lock(self):
        photo = Photo.objects.create(image=build_test_image(filename="lock.png"))
        Photo.objects.filter(pk=photo.pk).update(optimized_image="", thumbnail="")
        in_atomic = []

        def spy(*args, **kwargs):
            in_atomic.append(connection.in_atomic_block)
            return open_image_from_file(*args, **kwargs)

        with patch("gallery.services.open_image_from_file", side_effect=spy):
            # TestCase сам оборачивает тест в транзакцию - сравниваем с ней
            baseline = connection.in_atomic_block
            ensure_photo_derivatives_by_id(photo.pk)

        self.assertEqual(in_atomic, [baseline])

    def test_concurrent_result_is_not_overwritten(self):
        photo = Photo.objects.create(image=build_test_image(filename="race.png"))
        Photo.objects.filter(pk=photo.pk).update(optimized_image="", thumbnail="")
        variants = build_missing_variants(Photo.objects.get(pk=photo.pk))
        Photo.objects.filter(pk=photo.pk).update(thumbnail="thumbnails/other-worker.webp")

        apply_variants(Photo.objects.get(pk=photo.pk), variants)

        photo.refresh_from_db()
        self.assertEqual(photo.thumbnail.name, "thumbnails/other-worker.webp")
        self.assertTrue(bool(photo.optimized_image))

    @override_settings(DELETE_ORIGINAL_AFTER_OPTIMIZE=True)
    def test_original_survives_failed_derivative_write(self):
        photo = Photo.objects.create(image=build_test_image(filename="keep.png"))
        Photo.objects.filter(pk=photo.pk).update(optimized_image="", thumbnail="")
        original = Path(self._temp_media_root) / photo.image.name

        with (
            patch.object(Photo, "save", side_effect=RuntimeError("db unavailable")),
            self.captureOnCommitCallbacks(execute=True),
            self.assertRaises(RuntimeError),
        ):
            ensure_photo_derivatives_by_id(photo.pk)

        self.assertTrue(original.exists())
        leftovers = [
            path for path in Path(self._temp_media_root).rglob("*") if "keep_" in path.name
        ]
        self.assertEqual(leftovers, [])


class GenerateDerivativesCommandTest(GalleryTestCase):
    def test_command_backfills_missing_variants(self):
        photo = Photo.objects.create(image=build_test_image(filename="cmd.png"))
        Photo.objects.filter(pk=photo.pk).update(optimized_image="", thumbnail="")
        out = StringIO()

        call_command("generate_derivatives", stdout=out)

        photo.refresh_from_db()
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))
        self.assertIn("Processed: 1", out.getvalue())
