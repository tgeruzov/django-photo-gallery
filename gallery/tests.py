import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Photo
from .services import (
    DuplicatePhotoError,
    ensure_photo_derivatives_by_id,
    save_uploaded_photo,
)
from .tasks import schedule_photo_derivatives


def build_test_image(filename="test.png", size=(64, 64), color=(255, 0, 0)):
    stream = BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG")
    return SimpleUploadedFile(filename, stream.getvalue(), content_type="image/png")


class GalleryTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media_root = tempfile.mkdtemp(prefix="gallery-test-media-")
        cls._settings_override = override_settings(
            MEDIA_ROOT=cls._temp_media_root,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        )
        cls._settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._settings_override.disable()
        shutil.rmtree(cls._temp_media_root, ignore_errors=True)
        super().tearDownClass()


class PhotoModelTest(GalleryTestCase):
    def test_photo_string_representation(self):
        photo = Photo.objects.create(image=build_test_image(), title="Test Photo")
        self.assertEqual(str(photo), "Test Photo")

    def test_photo_without_title(self):
        photo = Photo.objects.create(image=build_test_image(filename="test2.png"))
        self.assertIn("test2", str(photo))


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

        with patch.object(Photo, "save", side_effect=RuntimeError("db unavailable")):
            with self.assertRaises(RuntimeError):
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
        with patch("gallery.signals.schedule_photo_derivatives") as schedule_mock:
            with self.captureOnCommitCallbacks(execute=True):
                photo = Photo.objects.create(image=build_test_image(filename="queued.png"))

        schedule_mock.assert_called_once_with(photo.pk)


class GalleryViewsTest(GalleryTestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(username="admin", password="pass", is_staff=True)

    def test_favicon_route_redirects_to_static_icon(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/static/icon/favicon-dark.ico", response["Location"])

    def test_index_page_loads(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)

    def test_index_page_includes_seo_metadata_and_structured_data(self):
        Photo.objects.create(
            image=build_test_image(filename="seo.png"),
            title="Main gallery hero shot",
            alt_text="Вечерняя панорама города",
        )

        response = self.client.get(reverse("index"))
        content = response.content.decode()

        self.assertIn('<link rel="canonical" href="http://testserver/" />', content)
        self.assertIn('name="description"', content)
        self.assertIn('property="og:title"', content)
        self.assertIn('property="og:image"', content)
        self.assertIn('"@type": "ImageGallery"', content)
        self.assertIn("Вечерняя панорама города", content)
        self.assertContains(response, "Фотогалерея Тимура Герузова")

    def test_index_survives_missing_thumbnail_file(self):
        photo = Photo.objects.create(image=build_test_image(filename="orphan.png"))
        Photo.objects.filter(pk=photo.pk).update(thumbnail="thumbnails/gone/missing.webp")

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)

    def test_structured_data_escapes_script_close(self):
        Photo.objects.create(
            image=build_test_image(filename="xss.png"),
            title="</script><script>alert(1)</script>",
        )

        response = self.client.get(reverse("index"))

        self.assertNotContains(response, "</script><script>alert(1)</script>")
        self.assertContains(response, "<\\/script><script>alert(1)<\\/script>")

    def test_upload_requires_login(self):
        response = self.client.get(reverse("upload_photo"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_upload(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("upload_photo"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertContains(response, 'content="noindex, nofollow, noarchive"')

    def test_staff_ajax_upload_success_creates_variants(self):
        self.client.login(username="admin", password="pass")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("upload_photo"),
                {"files": [build_test_image(filename="valid.png")]},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        photo = Photo.objects.get()
        self.assertTrue(bool(photo.image))
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    def test_staff_ajax_upload_skips_duplicates_idempotently(self):
        self.client.login(username="admin", password="pass")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("upload_photo"),
                {"files": [build_test_image(filename="first.png")]},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("upload_photo"),
                {"files": [build_test_image(filename="retry.png")]},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["duplicates"]), 1)
        self.assertEqual(Photo.objects.count(), 1)

    def test_staff_ajax_upload_rejects_invalid_file(self):
        self.client.login(username="admin", password="pass")
        bad_file = SimpleUploadedFile("fake.jpg", b"not-an-image", content_type="image/jpeg")
        response = self.client.post(
            reverse("upload_photo"),
            {"files": [bad_file]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertEqual(Photo.objects.count(), 0)

    def test_staff_ajax_upload_rejects_empty_submission(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(
            reverse("upload_photo"), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")

    def test_index_ajax_out_of_range_returns_empty(self):
        response = self.client.get(
            reverse("index") + "?page=999", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        payload = response.json()
        self.assertEqual(payload["photos"], [])
        self.assertFalse(payload["has_next"])

    def test_all_photos_json_supports_pagination(self):
        Photo.objects.bulk_create(
            [Photo(image=f"photos/p{i}.jpg", title=f"p{i}") for i in range(25)]
        )
        response = self.client.get(reverse("all_photos_json") + "?page=1&page_size=10")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["photos"]), 10)
        self.assertTrue(payload["has_next"])
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 10)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")

    def test_all_photos_json_includes_dimensions_for_real_images(self):
        Photo.objects.create(image=build_test_image(filename="dimensions.png"))
        response = self.client.get(reverse("all_photos_json"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["photos"]), 1)
        self.assertEqual(payload["photos"][0]["width"], 64)
        self.assertEqual(payload["photos"][0]["height"], 64)

    def test_all_photos_json_exposes_alt_text_for_dynamic_cards(self):
        Photo.objects.create(
            image=build_test_image(filename="alt-text.png"),
            title="Skyline",
            alt_text="Ночной городской skyline",
        )

        response = self.client.get(reverse("all_photos_json"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["photos"][0]["alt_text"], "Ночной городской skyline")
        self.assertEqual(payload["photos"][0]["title"], "Skyline")

    def test_all_photos_json_skips_broken_records(self):
        photo = Photo.objects.create(image=build_test_image(filename="broken.png"))
        Photo.objects.filter(pk=photo.pk).update(image="")
        response = self.client.get(reverse("all_photos_json"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["photos"], [])

    def test_robots_txt_advertises_sitemap_and_blocks_internal_routes(self):
        response = self.client.get(reverse("robots_txt"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("User-agent: *", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /upload/", content)
        self.assertIn("Disallow: /all_photos.json", content)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", content)

    def test_sitemap_lists_homepage(self):
        response = self.client.get(reverse("sitemap"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("<loc>http://testserver/</loc>", content)
