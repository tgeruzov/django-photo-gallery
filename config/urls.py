from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.shortcuts import render
from django.urls import path
from django.views.generic import RedirectView

from gallery import views
from gallery.seo import RootSitemap
from gallery.throttle import throttled_login

# Подбор пароля к админке упирается в лимит попыток
admin.site.login = throttled_login(admin.site.login)

urlpatterns = [
    path("", views.index, name="index"),
    path("manage/", views.manage, name="manage"),
    path("manage/photos/", views.manage_photos, name="manage_photos"),
    path("manage/photos/reorder/", views.manage_reorder, name="manage_reorder"),
    path("manage/photos/delete/", views.manage_delete, name="manage_delete"),
    path("manage/upload/", views.upload_photo, name="upload_photo"),
    # Старый адрес загрузки из закладок
    path("upload/", RedirectView.as_view(pattern_name="upload_photo", permanent=False)),
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
    # В режиме разработки Django показывает техническую страницу ошибки,
    # поэтому оформленные страницы доступны по отдельным адресам
    urlpatterns += [
        path("404/", lambda request: render(request, "404.html", status=404)),
        path("500/", lambda request: render(request, "500.html", status=500)),
    ]
