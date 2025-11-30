from django.db import models

class Photo(models.Model):
    image = models.ImageField(
        upload_to='photos/%Y/%m/%d/',
        verbose_name="Оригинальное изображение"
    )
    thumbnail = models.ImageField(
        upload_to='thumbnails/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name="Миниатюра"
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Описание для SEO"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Название/описание"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    def __str__(self):
        return self.title or self.image.name

    class Meta:
        verbose_name = "Фотография"
        verbose_name_plural = "Фотографии"
        ordering = ['-uploaded_at']