import os
from django.test import TestCase
from django.urls import reverse
from .models import Photo
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from PIL import Image

class PhotoModelTest(TestCase):
    def test_photo_string_representation(self):
        photo = Photo.objects.create(
            image=SimpleUploadedFile("test.jpg", b"file"), 
            title="Test Photo"
        )
        self.assertEqual(str(photo), "Test Photo")
        
    def test_photo_without_title(self):
        photo = Photo.objects.create(image=SimpleUploadedFile("test2.jpg", b"file"))
        self.assertIn("test2", str(photo))

class GalleryViewsTest(TestCase):
    def test_index_page_loads(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)

    def test_upload_requires_login(self):
        response = self.client.get(reverse('upload_photo'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_upload(self):
        user = User.objects.create_user(username='admin', password='pass', is_staff=True)
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('upload_photo'))
        self.assertEqual(response.status_code, 200)