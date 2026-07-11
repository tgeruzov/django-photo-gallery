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
    # Размеры вариантов денормализованы, чтобы не открывать файлы из storage
    # на каждый запрос. Заполняются сервисным слоем при генерации вариантов.
    # Намеренно НЕ через width_field/height_field: их post_init-хук читает файл
    # с диска для строк с пустыми размерами и падает, если файл пропал.
    optimized_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    optimized_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    thumbnail_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    thumbnail_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    alt_text = models.CharField(
        max_length=255, blank=True, verbose_name="Альтернативный текст (для SEO и доступности)"
    )
    title = models.CharField(max_length=200, blank=True, verbose_name="Заголовок/Описание")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    @property
    def has_complete_variants(self):
        return bool(self.optimized_image and self.thumbnail)

    def file_dimensions(self, file_field):
        """Размеры файла: из колонок БД, для оригинала — осторожно с диска."""
        if not file_field:
            return None, None
        field_name = file_field.field.name
        if field_name == "thumbnail" and self.thumbnail_width and self.thumbnail_height:
            return self.thumbnail_width, self.thumbnail_height
        if field_name == "optimized_image" and self.optimized_width and self.optimized_height:
            return self.optimized_width, self.optimized_height
        try:
            return file_field.width, file_field.height
        except (ValueError, OSError):
            return None, None

    @property
    def display_file(self):
        return self.thumbnail or self.optimized_image or self.image

    @property
    def display_dimensions(self):
        return self.file_dimensions(self.display_file)

    @property
    def display_label(self):
        return self.alt_text or self.title or (f"Фотография {self.pk}" if self.pk else "Фотография")

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
