from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Photo


class RootSitemap(Sitemap):
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return ["index"]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return Photo.objects.order_by("-uploaded_at").values_list("uploaded_at", flat=True).first()


sitemaps = {
    "root": RootSitemap,
}
