from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from gallery.forms import validate_file_size, validate_image_type

from .base import build_test_image


class FormValidatorsTest(TestCase):
    def test_validate_image_type_accepts_webp_signature(self):
        webp = SimpleUploadedFile(
            "x.webp", b"RIFF\x24\x00\x00\x00WEBPVP8 ", content_type="image/webp"
        )
        validate_image_type(webp)  # не должен бросить

    def test_validate_image_type_accepts_png_signature(self):
        validate_image_type(build_test_image(filename="real.png"))

    def test_validate_image_type_rejects_unknown_signature(self):
        fake = SimpleUploadedFile("fake.jpg", b"GIF89a not allowed", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            validate_image_type(fake)

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_validate_file_size_allows_exact_limit(self):
        exact = SimpleUploadedFile("exact.jpg", b"x" * (1024 * 1024), content_type="image/jpeg")
        validate_file_size(exact)  # ровно на границе — проходит

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_validate_file_size_rejects_over_limit(self):
        over = SimpleUploadedFile("over.jpg", b"x" * (1024 * 1024 + 1), content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            validate_file_size(over)
