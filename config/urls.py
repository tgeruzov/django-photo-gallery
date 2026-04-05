from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import RedirectView

from gallery.sitemaps import sitemaps
from gallery.views import robots_txt

urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "favicon.ico",
        RedirectView.as_view(
            url=f"{settings.STATIC_URL}icon/favicon-dark.ico",
            permanent=False,
        ),
    ),
    path("admin/", admin.site.urls),
    path("", include("gallery.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
