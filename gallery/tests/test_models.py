from gallery.models import Photo

from .base import GalleryTestCase, build_test_image


class PhotoModelTest(GalleryTestCase):
    def test_photo_string_representation(self):
        photo = Photo.objects.create(image=build_test_image(), title="Test Photo")
        self.assertEqual(str(photo), "Test Photo")

    def test_photo_without_title(self):
        photo = Photo.objects.create(image=build_test_image(filename="test2.png"))
        self.assertIn("test2", str(photo))
