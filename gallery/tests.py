import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Photo
from .services import ensure_photo_derivatives_by_id, save_uploaded_photo


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
            STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
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
        photo = save_uploaded_photo(build_test_image(filename="service.png"))

        self.assertTrue(bool(photo.image))
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

    @override_settings(DELETE_ORIGINAL_AFTER_OPTIMIZE=True)
    def test_save_uploaded_photo_can_delete_original_after_optimization(self):
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

    def test_upload_requires_login(self):
        response = self.client.get(reverse("upload_photo"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_upload(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("upload_photo"))
        self.assertEqual(response.status_code, 200)

    def test_staff_ajax_upload_success_creates_variants(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(
            reverse("upload_photo"),
            {"files": [build_test_image(filename="valid.png")]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        photo = Photo.objects.get()
        self.assertTrue(bool(photo.image))
        self.assertTrue(bool(photo.optimized_image))
        self.assertTrue(bool(photo.thumbnail))

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
        self.assertEqual(Photo.objects.count(), 0)

    def test_staff_ajax_upload_rejects_empty_submission(self):
        self.client.login(username="admin", password="pass")
        response = self.client.post(reverse("upload_photo"), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["success"])

    def test_index_ajax_out_of_range_returns_empty(self):
        response = self.client.get(reverse("index") + "?page=999", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["photos"], [])
        self.assertFalse(payload["has_next"])

    def test_all_photos_json_supports_pagination(self):
        Photo.objects.bulk_create([Photo(image=f"photos/p{i}.jpg", title=f"p{i}") for i in range(25)])
        response = self.client.get(reverse("all_photos_json") + "?page=1&page_size=10")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["photos"]), 10)
        self.assertTrue(payload["has_next"])
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 10)

    def test_all_photos_json_includes_dimensions_for_real_images(self):
        Photo.objects.create(image=build_test_image(filename="dimensions.png"))
        response = self.client.get(reverse("all_photos_json"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["photos"]), 1)
        self.assertEqual(payload["photos"][0]["width"], 64)
        self.assertEqual(payload["photos"][0]["height"], 64)

    def test_all_photos_json_skips_broken_records(self):
        photo = Photo.objects.create(image=build_test_image(filename="broken.png"))
        Photo.objects.filter(pk=photo.pk).update(image="")
        response = self.client.get(reverse("all_photos_json"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["photos"], [])
