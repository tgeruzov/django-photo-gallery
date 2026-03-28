from django.db import models


class Photo(models.Model):
    image = models.ImageField(upload_to="photos/%Y/%m/%d/", verbose_name="Оригинальное изображение")
    optimized_image = models.ImageField(
        upload_to="optimized/%Y/%m/%d/",
        null=True,
        blank=True,
        verbose_name="Оптимизированное изображение",
    )
    thumbnail = models.ImageField(
        upload_to="thumbnails/%Y/%m/%d/", null=True, blank=True, verbose_name="Миниатюра"
    )
    alt_text = models.CharField(
        max_length=255, blank=True, verbose_name="Альтернативный текст (для SEO и доступности)"
    )
    title = models.CharField(max_length=200, blank=True, verbose_name="Заголовок/Описание")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    @property
    def has_complete_variants(self):
        return bool(self.optimized_image and self.thumbnail)

    def __str__(self):
        if self.title:
            return self.title
        if self.image:
            return self.image.name
        return f"Photo #{self.pk or 'new'}"

    class Meta:
        verbose_name = "Фотография"
        verbose_name_plural = "Фотографии"
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["-uploaded_at"], name="gallery_photo_up_idx"),
        ]
