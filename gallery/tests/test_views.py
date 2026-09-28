from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from gallery.models import Photo

from .base import GalleryTestCase, build_test_image


class GalleryViewsTest(GalleryTestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(username="admin", password="pass", is_staff=True)

    def test_favicon_route_redirects_to_static_icon(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/static/icon/favicon-dark.ico", response["Location"])

    def test_index_page_loads(self):
        response = self.client.get(reverse("gallery:index"))
        self.assertEqual(response.status_code, 200)

    def test_index_page_includes_seo_metadata_and_structured_data(self):
        Photo.objects.create(
            image=build_test_image(filename="seo.png"),
            title="Main gallery hero shot",
            alt_text="Вечерняя панорама города",
        )

        response = self.client.get(reverse("gallery:index"))
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

        response = self.client.get(reverse("gallery:index"))

        self.assertEqual(response.status_code, 200)

    def test_structured_data_escapes_script_close(self):
        Photo.objects.create(
            image=build_test_image(filename="xss.png"),
            title="</script><script>alert(1)</script>",
        )

        response = self.client.get(reverse("gallery:index"))

        self.assertNotContains(response, "</script><script>alert(1)</script>")
        self.assertContains(response, "<\\/script><script>alert(1)<\\/script>")

    def test_upload_requires_login(self):
        response = self.client.get(reverse("gallery:upload_photo"))
        self.assertEqual(response.status_code, 302)

    def test_upload_post_rejected_for_non_staff(self):
        User.objects.create_user(username="visitor", password="pass")
        self.client.login(username="visitor", password="pass")

        response = self.client.post(
            reverse("gallery:upload_photo"),
            {"files": [build_test_image(filename="sneaky.png")]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Photo.objects.count(), 0)

    def test_all_photos_json_clamps_garbage_page_size(self):
        Photo.objects.create(image=build_test_image(filename="clamp.png"))

        negative = self.client.get(reverse("gallery:all_photos_json") + "?page_size=-5")
        self.assertEqual(negative.status_code, 200)
        self.assertEqual(negative.json()["page_size"], 1)

        garbage = self.client.get(reverse("gallery:all_photos_json") + "?page_size=abc")
        self.assertEqual(garbage.status_code, 200)
        self.assertEqual(garbage.json()["page_size"], 200)

    def test_staff_can_upload(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("gallery:upload_photo"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertContains(response, 'content="noindex, nofollow, noarchive"')

    def test_staff_ajax_upload_success_creates_variants(self):
        self.client.login(username="admin", password="pass")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("gallery:upload_photo"),
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
                reverse("gallery:upload_photo"),
                {"files": [build_test_image(filename="first.png")]},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("gallery:upload_photo"),
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
            reverse("gallery:upload_photo"),
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
            reverse("gallery:upload_photo"), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")

    def test_index_out_of_range_page_returns_404(self):
        response = self.client.get(reverse("gallery:index") + "?page=999")
        self.assertEqual(response.status_code, 404)

    def test_paginated_page_declares_self_canonical(self):
        Photo.objects.bulk_create(
            [Photo(image=f"photos/c{i}.jpg", title=f"c{i}") for i in range(13)]
        )

        response = self.client.get(reverse("gallery:index") + "?page=2")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="canonical" href="http://testserver/?page=2"')

    def test_index_ajax_out_of_range_returns_empty(self):
        response = self.client.get(
            reverse("gallery:index") + "?page=999", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        payload = response.json()
        self.assertEqual(payload["photos"], [])
        self.assertFalse(payload["has_next"])

    def test_index_ajax_supports_keyset_cursor(self):
        Photo.objects.bulk_create(
            [Photo(image=f"photos/k{i}.jpg", title=f"k{i}") for i in range(15)]
        )
        first_page = self.client.get(
            reverse("gallery:index"), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        ).json()
        self.assertEqual(len(first_page["photos"]), 12)
        last_id = first_page["photos"][-1]["id"]

        second_page = self.client.get(
            reverse("gallery:index") + f"?after={last_id}",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        ).json()

        self.assertEqual(len(second_page["photos"]), 3)
        self.assertFalse(second_page["has_next"])
        first_ids = {photo["id"] for photo in first_page["photos"]}
        second_ids = {photo["id"] for photo in second_page["photos"]}
        self.assertFalse(first_ids & second_ids)

    def test_index_ajax_invalid_cursor_returns_empty(self):
        response = self.client.get(
            reverse("gallery:index") + "?after=not-a-number",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["photos"], [])
        self.assertFalse(payload["has_next"])

    def test_all_photos_json_supports_pagination(self):
        Photo.objects.bulk_create(
            [Photo(image=f"photos/p{i}.jpg", title=f"p{i}") for i in range(25)]
        )
        response = self.client.get(reverse("gallery:all_photos_json") + "?page=1&page_size=10")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["photos"]), 10)
        self.assertTrue(payload["has_next"])
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 10)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")

    def test_all_photos_json_includes_dimensions_for_real_images(self):
        Photo.objects.create(image=build_test_image(filename="dimensions.png"))
        response = self.client.get(reverse("gallery:all_photos_json"))
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

        response = self.client.get(reverse("gallery:all_photos_json"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["photos"][0]["alt_text"], "Ночной городской skyline")
        self.assertEqual(payload["photos"][0]["title"], "Skyline")

    def test_all_photos_json_skips_broken_records(self):
        photo = Photo.objects.create(image=build_test_image(filename="broken.png"))
        Photo.objects.filter(pk=photo.pk).update(image="")
        response = self.client.get(reverse("gallery:all_photos_json"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["photos"], [])

    def test_404_uses_custom_template(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "В галерею", status_code=404)

    def test_healthz_reports_ok(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

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

    def test_keyset_cursor_survives_deleted_cursor_photo(self):
        Photo.objects.bulk_create(
            [Photo(image=f"photos/d{i}.jpg", title=f"d{i}") for i in range(15)]
        )
        first_page = self.client.get(
            reverse("gallery:index"), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        ).json()
        cursor = first_page["photos"][-1]
        Photo.objects.filter(pk=cursor["id"]).delete()

        second_page = self.client.get(
            reverse("gallery:index"),
            {"after": cursor["id"], "after_ts": cursor["uploaded_at"]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        ).json()

        self.assertEqual(len(second_page["photos"]), 3)
        self.assertFalse(second_page["has_next"])

    def test_cards_expose_cursor_timestamp(self):
        photo = Photo.objects.create(image=build_test_image(filename="ts.png"))

        response = self.client.get(reverse("gallery:index"))

        self.assertContains(response, f'data-ts="{photo.uploaded_at.isoformat()}"')

    def test_all_photos_json_breaks_timestamp_ties_by_id(self):
        Photo.objects.bulk_create(
            [Photo(image=f"photos/t{i}.jpg", title=f"t{i}") for i in range(6)]
        )
        same_time = Photo.objects.first().uploaded_at
        Photo.objects.update(uploaded_at=same_time)

        pages = [
            self.client.get(
                reverse("gallery:all_photos_json"), {"page": page, "page_size": 2}
            ).json()["photos"]
            for page in (1, 2, 3)
        ]

        ids = [photo["id"] for page in pages for photo in page]
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.assertEqual(len(set(ids)), 6)
