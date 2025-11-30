from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_photo, name='upload_photo'),
    path('all_photos.json', views.all_photos_json, name='all_photos_json'),
]