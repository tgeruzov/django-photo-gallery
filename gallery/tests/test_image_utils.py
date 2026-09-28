from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from PIL import Image

from gallery.image_utils import (
    ImageProcessingError,
    build_thumbnail_content,
    open_image_from_file,
)

from .base import build_test_image


class ImageUtilsTest(TestCase):
    def test_decompression_bomb_raises_processing_error(self):
        with (
            patch.object(Image, "MAX_IMAGE_PIXELS", 10),
            self.assertRaises(ImageProcessingError),
        ):
            open_image_from_file(BytesIO(build_test_image().read()))

    def test_exif_orientation_is_applied(self):
        stream = BytesIO()
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation: Rotate 90 CW
        Image.new("RGB", (40, 20), (0, 0, 255)).save(stream, format="JPEG", exif=exif)
        stream.seek(0)

        opened = open_image_from_file(stream)

        self.assertEqual(opened.size, (20, 40))

    def test_mirrored_exif_orientation_is_applied(self):
        stream = BytesIO()
        exif = Image.Exif()
        exif[0x0112] = 5  # Mirror horizontal + rotate 270 CW
        Image.new("RGB", (40, 20), (0, 255, 0)).save(stream, format="JPEG", exif=exif)
        stream.seek(0)

        opened = open_image_from_file(stream)

        self.assertEqual(opened.size, (20, 40))

    def test_rgba_png_keeps_alpha_in_webp_thumbnail(self):
        stream = BytesIO()
        Image.new("RGBA", (32, 32), (255, 0, 0, 128)).save(stream, format="PNG")
        stream.seek(0)

        opened = open_image_from_file(stream)
        self.assertEqual(opened.mode, "RGBA")

        content = build_thumbnail_content(opened, "alpha.png")
        thumbnail = Image.open(BytesIO(content.read()))
        self.assertIn(thumbnail.mode, ("RGBA", "P"))
