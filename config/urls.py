from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic import RedirectView

from gallery import views
from gallery.seo import RootSitemap

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload_photo, name="upload_photo"),
    path("all_photos.json", views.all_photos_json, name="all_photos_json"),
    path("healthz", views.healthz, name="healthz"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": {"root": RootSitemap}}, name="sitemap"),
    path(
        "favicon.ico",
        RedirectView.as_view(url=f"{settings.STATIC_URL}icon/favicon-dark.ico", permanent=False),
    ),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
