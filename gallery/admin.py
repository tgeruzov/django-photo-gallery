import logging

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.html import format_html

from .models import Photo
from .services import clear_variants, compute_upload_hash, ensure_photo_derivatives_by_id
from .validators import validate_file_size, validate_image_type

logger = logging.getLogger(__name__)


class PhotoAdminForm(forms.ModelForm):
    """Новый оригинал в админке проходит те же проверки, что и на странице загрузки."""

    class Meta:
        model = Photo
        fields = ("title", "alt_text", "image")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # С DELETE_ORIGINAL_AFTER_OPTIMIZE у фото нет оригинала,
        # а заголовок и alt всё равно должны редактироваться
        if self.instance.pk:
            self.fields["image"].required = False

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if "image" not in self.changed_data or not image:
            return image
        validate_file_size(image)
        validate_image_type(image)
        content_hash = compute_upload_hash(image)
        duplicates = Photo.objects.filter(content_hash=content_hash)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError("Такое фото уже есть в галерее.")
        self.content_hash = content_hash
        return image


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    form = PhotoAdminForm
    list_display = (
        "id",
        "title_or_filename",
        "has_original_image",
        "has_optimized_image",
        "has_thumbnail_image",
        "uploaded_at",
        "preview",
    )
    date_hierarchy = "uploaded_at"
    search_fields = ("title", "alt_text", "image", "optimized_image", "thumbnail")
    ordering = ("position", "-id")
    # Версии строит только сервис: загруженная руками миниатюра
    # разошлась бы с оригиналом и с размерами в базе
    readonly_fields = ("optimized_image", "medium_image", "thumbnail", "uploaded_at", "preview")
    actions = ("generate_missing_derivatives",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "alt_text",
                    "image",
                    "optimized_image",
                    "medium_image",
                    "thumbnail",
                    "uploaded_at",
                    "preview",
                )
            },
        ),
    )

    @admin.display(description="Фото")
    def title_or_filename(self, obj):
        return obj.title or obj.image.name or f"Photo #{obj.pk}"

    @admin.display(boolean=True, description="Original")
    def has_original_image(self, obj):
        return bool(obj.image)

    @admin.display(boolean=True, description="Optimized")
    def has_optimized_image(self, obj):
        return bool(obj.optimized_image)

    @admin.display(boolean=True, description="Thumbnail")
    def has_thumbnail_image(self, obj):
        return bool(obj.thumbnail)

    @admin.display(description="Preview")
    def preview(self, obj):
        image = obj.thumbnail or obj.optimized_image or obj.image
        if not image:
            return "No preview"
        try:
            image_url = image.url
        except (ValueError, OSError):
            return "No preview"
        return format_html(
            '<img src="{}" alt="{}" style="max-height: 96px; border-radius: 6px;" />',
            image_url,
            obj.title or obj.alt_text or f"Photo {obj.pk}",
        )

    def save_model(self, request, obj, form, change):
        if not change:
            # Как и при обычной загрузке, новое фото встаёт первым в ленте
            obj.position = Photo.top_position()
        image_changed = "image" in form.changed_data and bool(obj.image)
        if image_changed:
            obj.content_hash = getattr(form, "content_hash", None)
            # Старые версии показывали бы прежний снимок
            clear_variants(obj)
        super().save_model(request, obj, form, change)
        # Фото, добавленное или заменённое через админку, тоже получает превью
        transaction.on_commit(lambda: self.build_derivatives(request, obj.pk))

    def build_derivatives(self, request, photo_id):
        # Запись уже сохранена: сбой обработки - предупреждение, а не страница 500
        try:
            ensure_photo_derivatives_by_id(photo_id)
        except Exception:
            logger.exception("Не удалось построить версии фото %s", photo_id)
            self.message_user(
                request,
                "Фото сохранено, но версии не построились. "
                "Выберите действие Generate missing derivatives, чтобы повторить.",
                level=messages.WARNING,
            )

    @admin.action(description="Generate missing derivatives")
    def generate_missing_derivatives(self, request, queryset):
        processed = skipped = failed = 0
        for photo_id in queryset.values_list("id", flat=True):
            try:
                if ensure_photo_derivatives_by_id(photo_id):
                    processed += 1
                else:
                    skipped += 1
            except Exception:
                logger.exception("Не удалось построить версии фото %s", photo_id)
                failed += 1
        self.message_user(
            request,
            f"Derivatives: processed={processed}, skipped={skipped}, failed={failed}.",
            level=messages.WARNING if failed else messages.INFO,
        )
