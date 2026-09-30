import os
import uuid

from django.db import models
from django.utils import timezone


def original_upload_to(instance, filename):
    """Оригинал хранится под случайным именем.

    В нём остаётся EXIF, иногда с координатами съёмки, а имя вида IMG_1234.jpg
    легко угадать по адресу в /media/.
    """
    extension = os.path.splitext(filename)[1].lower()
    return timezone.now().strftime("photos/%Y/%m/%d/") + f"{uuid.uuid4().hex}{extension}"


class Photo(models.Model):
    image = models.ImageField(upload_to=original_upload_to, verbose_name="Оригинальное изображение")
    optimized_image = models.ImageField(
        upload_to="optimized/%Y/%m/%d/",
        null=True,
        blank=True,
        verbose_name="Оптимизированное изображение",
    )
    thumbnail = models.ImageField(
        upload_to="thumbnails/%Y/%m/%d/", null=True, blank=True, verbose_name="Миниатюра"
    )
    # Версия для лайтбокса на телефонах: 2560px там избыточны
    medium_image = models.ImageField(
        upload_to="medium/%Y/%m/%d/", null=True, blank=True, verbose_name="Средняя версия"
    )
    # Размеры вариантов денормализованы, чтобы не открывать файлы из storage
    # на каждый запрос. Заполняются сервисным слоем при генерации вариантов.
    # Намеренно НЕ через width_field/height_field: их post_init-хук читает файл
    # с диска для строк с пустыми размерами и падает, если файл пропал.
    optimized_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    optimized_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    thumbnail_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    thumbnail_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    medium_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    medium_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    # SHA-256 оригинала для мягкой дедупликации повторных загрузок.
    # null (а не "") - чтобы unique не конфликтовал на строках без хеша.
    content_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        verbose_name="SHA-256 оригинала",
    )
    alt_text = models.CharField(
        max_length=255, blank=True, verbose_name="Альтернативный текст (для SEO и доступности)"
    )
    title = models.CharField(max_length=200, blank=True, verbose_name="Заголовок/Описание")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    class Meta:
        verbose_name = "Фотография"
        verbose_name_plural = "Фотографии"
        ordering = ["-uploaded_at", "-id"]
        indexes = [
            # Совпадает с сортировкой ленты и keyset-курсором (uploaded_at, id)
            models.Index(fields=["-uploaded_at", "-id"], name="gallery_photo_up_id_idx"),
        ]

    def __str__(self):
        if self.title:
            return self.title
        if self.image:
            return self.image.name
        return f"Photo #{self.pk or 'new'}"

    def file_dimensions(self, file_field):
        """Размеры файла: из колонок БД, для оригинала - осторожно с диска."""
        if not file_field:
            return None, None
        field_name = file_field.field.name
        if field_name == "thumbnail" and self.thumbnail_width and self.thumbnail_height:
            return self.thumbnail_width, self.thumbnail_height
        if field_name == "optimized_image" and self.optimized_width and self.optimized_height:
            return self.optimized_width, self.optimized_height
        if field_name == "medium_image" and self.medium_width and self.medium_height:
            return self.medium_width, self.medium_height
        try:
            return file_field.width, file_field.height
        except (ValueError, OSError):
            return None, None

    @property
    def display_file(self):
        return self.thumbnail or self.optimized_image or self.image

    @property
    def card_sources(self):
        """(превью, полный файл) для карточки или None, если показывать нечего."""
        display = self.display_file
        full = self.optimized_image or self.image
        if display and full:
            return (display, full)
        return None

    @property
    def display_dimensions(self):
        return self.file_dimensions(self.display_file)

    @property
    def has_all_variants(self):
        return bool(self.optimized_image and self.medium_image and self.thumbnail)

    @property
    def display_ratio(self):
        """Ширина к высоте превью для раскладки сетки; 1, если размер неизвестен."""
        width, height = self.display_dimensions
        return round(width / height, 4) if width and height else 1

    @property
    def medium_url(self):
        try:
            return self.medium_image.url if self.medium_image else ""
        except ValueError:
            return ""

    @property
    def display_label(self):
        return self.alt_text or self.title or (f"Фотография {self.pk}" if self.pk else "Фотография")
