import json
import re
import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import OperationalError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageCms

from .models import Photo
from .services import save_uploaded_photo
from .throttle import LOGIN_ATTEMPTS_LIMIT

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def image_bytes(color=(200, 30, 30), size=(1200, 800), fmt="JPEG", mode="RGB", **save_kwargs):
    buffer = BytesIO()
    Image.new(mode, size, color).save(buffer, fmt, **save_kwargs)
    return buffer.getvalue()


def upload(name="photo.jpg", content=None, content_type="image/jpeg"):
    return SimpleUploadedFile(name, content or image_bytes(), content_type)


class MediaTestCase(TestCase):
    """Файлы тестов пишутся во временную папку, а не в media/ проекта."""

    def setUp(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)
        cache.clear()

    def make_admin(self):
        user = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.client.force_login(user)
        return user


class UploadTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.make_admin()

    def test_upload_builds_all_variants_with_dimensions(self):
        response = self.client.post(reverse("upload_photo"), {"files": upload()}, **AJAX)

        self.assertEqual(response.status_code, 200)
        photo = Photo.objects.get()
        self.assertTrue(photo.has_all_variants)
        self.assertEqual((photo.thumbnail_width, photo.thumbnail_height), (800, 533))
        self.assertEqual((photo.optimized_width, photo.optimized_height), (1200, 800))

    def test_duplicate_is_skipped(self):
        content = image_bytes()
        self.client.post(reverse("upload_photo"), {"files": upload(content=content)}, **AJAX)
        response = self.client.post(
            reverse("upload_photo"), {"files": upload("again.jpg", content)}, **AJAX
        )

        self.assertEqual(response.json()["duplicates"], ["again.jpg: такое фото уже загружено"])
        self.assertEqual(Photo.objects.count(), 1)

    def test_invalid_file_reports_reason_in_errors(self):
        response = self.client.post(
            reverse("upload_photo"), {"files": upload("x.jpg", b"GIF89a not a jpeg")}, **AJAX
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["errors"],
            ["Недопустимый формат файла. Разрешены только JPEG, PNG, WEBP."],
        )

    def test_icc_profile_is_kept_in_variants(self):
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        self.client.post(
            reverse("upload_photo"),
            {"files": upload(content=image_bytes(icc_profile=icc))},
            **AJAX,
        )

        photo = Photo.objects.get()
        for field in (photo.optimized_image, photo.medium_image, photo.thumbnail):
            with Image.open(field.path) as variant:
                self.assertEqual(variant.info.get("icc_profile"), icc)

    def test_cmyk_profile_is_not_attached_to_rgb_variants(self):
        content = image_bytes((0, 255, 255, 0), mode="CMYK")
        self.client.post(reverse("upload_photo"), {"files": upload(content=content)}, **AJAX)

        with Image.open(Photo.objects.get().thumbnail.path) as thumbnail:
            self.assertIsNone(thumbnail.info.get("icc_profile"))
            self.assertEqual(thumbnail.convert("RGB").getpixel((5, 5)), (255, 0, 0))

    def test_16_bit_png_keeps_its_brightness(self):
        content = image_bytes(40000, size=(600, 400), fmt="PNG", mode="I;16")
        self.client.post(
            reverse("upload_photo"),
            {"files": upload("gray.png", content, "image/png")},
            **AJAX,
        )

        with Image.open(Photo.objects.get().thumbnail.path) as thumbnail:
            red, green, blue = thumbnail.convert("RGB").getpixel((5, 5))
        self.assertAlmostEqual(red, 40000 // 256, delta=2)
        self.assertEqual(red, green)
        self.assertEqual(green, blue)

    def test_original_gets_random_name(self):
        self.client.post(reverse("upload_photo"), {"files": upload("IMG_1234.JPG")}, **AJAX)

        name = Photo.objects.get().image.name
        self.assertNotIn("IMG_1234", name)
        self.assertRegex(name, r"^photos/\d{4}/\d{2}/\d{2}/[0-9a-f]{32}\.jpg$")

    def test_upload_page_requires_staff(self):
        self.client.logout()
        response = self.client.get(reverse("upload_photo"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])


class AdminTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.make_admin()

    def change_url(self, photo):
        return reverse("admin:gallery_photo_change", args=[photo.pk])

    def test_replacing_original_rebuilds_variants_and_hash(self):
        photo = save_uploaded_photo(upload(content=image_bytes((200, 30, 30))))
        old_hash = photo.content_hash

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.change_url(photo),
                {
                    "title": "",
                    "alt_text": "",
                    "image": upload("blue.jpg", image_bytes((0, 0, 255))),
                },
            )

        self.assertEqual(response.status_code, 302)
        photo.refresh_from_db()
        self.assertNotEqual(photo.content_hash, old_hash)
        with Image.open(photo.thumbnail.path) as thumbnail:
            red, _, blue = thumbnail.convert("RGB").getpixel((5, 5))
        self.assertGreater(blue, 200)
        self.assertLess(red, 30)

    def test_added_photo_gets_hash_and_duplicates_are_rejected(self):
        content = image_bytes((0, 200, 0))
        add_url = reverse("admin:gallery_photo_add")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                add_url, {"title": "", "alt_text": "", "image": upload("a.jpg", content)}
            )
        response = self.client.post(
            add_url, {"title": "", "alt_text": "", "image": upload("b.jpg", content)}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Такое фото уже есть в галерее.")
        photo = Photo.objects.get()
        self.assertIsNotNone(photo.content_hash)
        self.assertTrue(photo.has_all_variants)

    def test_title_is_editable_without_original(self):
        with self.settings(DELETE_ORIGINAL_AFTER_OPTIMIZE=True):
            photo = save_uploaded_photo(upload())
        photo.refresh_from_db()
        self.assertFalse(photo.image)

        response = self.client.post(self.change_url(photo), {"title": "Закат", "alt_text": ""})

        self.assertEqual(response.status_code, 302)
        photo.refresh_from_db()
        self.assertEqual(photo.title, "Закат")

    def test_failed_variants_do_not_break_the_save(self):
        add_url = reverse("admin:gallery_photo_add")
        # assertLogs снаружи: колбэки on_commit выполняются на выходе из capture
        with (
            self.assertLogs("gallery.admin", level="ERROR"),
            mock.patch("gallery.admin.ensure_photo_derivatives_by_id", side_effect=OSError("disk")),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(add_url, {"title": "", "alt_text": "", "image": upload()})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Photo.objects.count(), 1)


class LoginThrottleTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")

    def login(self, password):
        return self.client.post(reverse("admin:login"), {"username": "admin", "password": password})

    def test_login_is_blocked_after_repeated_failures(self):
        for _ in range(LOGIN_ATTEMPTS_LIMIT):
            self.assertEqual(self.login("wrong").status_code, 200)

        self.assertEqual(self.login("admin-pass-123").status_code, 429)

    def test_successful_login_resets_the_counter(self):
        for _ in range(LOGIN_ATTEMPTS_LIMIT - 1):
            self.login("wrong")
        self.assertEqual(self.login("admin-pass-123").status_code, 302)
        self.client.logout()

        for _ in range(LOGIN_ATTEMPTS_LIMIT - 1):
            self.login("wrong")
        self.assertEqual(self.login("admin-pass-123").status_code, 302)


class GalleryPageTests(MediaTestCase):
    def canonical(self, url):
        html = self.client.get(url).content.decode()
        return re.search(r'rel="canonical" href="([^"]+)"', html).group(1)

    def test_canonical_ignores_junk_query(self):
        self.assertEqual(self.canonical("/?page=abc"), "http://testserver/")
        self.assertEqual(self.canonical("/?page=1&utm_source=x"), "http://testserver/")

    def test_canonical_keeps_real_page_number(self):
        for index in range(13):
            save_uploaded_photo(upload(f"{index}.jpg", image_bytes((index * 10, 0, 0))))

        self.assertEqual(self.canonical("/?page=2"), "http://testserver/?page=2")
        self.assertEqual(self.client.get("/?page=3").status_code, 404)

    def test_structured_data_escapes_script_end(self):
        photo = save_uploaded_photo(upload())
        photo.title = "</script><script>alert(1)</script>"
        photo.save()

        html = self.client.get("/").content.decode()
        payload = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        ).group(1)
        self.assertNotIn("</script", payload)
        self.assertEqual(json.loads(payload)["@graph"][1]["image"][0]["name"], photo.title)

    def test_feed_continues_after_cursor(self):
        photos = [
            save_uploaded_photo(upload(f"{index}.jpg", image_bytes((index * 10, 0, 0))))
            for index in range(15)
        ]
        newest_first = photos[::-1]
        cursor = newest_first[11]

        response = self.client.get(
            "/",
            {"after": cursor.pk, "after_ts": cursor.uploaded_at.isoformat()},
            **AJAX,
        )

        data = response.json()
        self.assertEqual([item["id"] for item in data["photos"]], [p.pk for p in newest_first[12:]])
        self.assertFalse(data["has_next"])

    def test_bad_cursor_returns_empty_feed(self):
        response = self.client.get("/", {"after": "zzz"}, **AJAX)

        self.assertEqual(response.json(), {"photos": [], "has_next": False})


class ServiceEndpointTests(TestCase):
    def test_healthz_ok(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.json(), {"status": "ok"})

    def test_healthz_reports_database_failure(self):
        with mock.patch("gallery.views.connections") as connections:
            connections.__getitem__.return_value.cursor.side_effect = OperationalError("down")
            response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 503)

    def test_robots_and_sitemap(self):
        self.assertContains(self.client.get("/robots.txt"), "Disallow: /upload/")
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 200)

    def test_error_pages_render(self):
        from django.views.defaults import server_error

        self.assertEqual(self.client.get("/missing/").status_code, 404)
        self.assertEqual(server_error(RequestFactory().get("/")).status_code, 500)
