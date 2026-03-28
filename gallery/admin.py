from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Photo
from .services import ensure_photo_derivatives_by_id


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title_or_filename",
        "has_original_image",
        "has_optimized_image",
        "has_thumbnail_image",
        "uploaded_at",
        "preview",
    )
    list_filter = ("uploaded_at",)
    search_fields = ("title", "alt_text", "image", "optimized_image", "thumbnail")
    ordering = ("-uploaded_at",)
    readonly_fields = ("uploaded_at", "preview")
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

    @admin.action(description="Generate missing derivatives")
    def generate_missing_derivatives(self, request, queryset):
        updated = 0
        for photo_id in queryset.values_list("id", flat=True):
            if ensure_photo_derivatives_by_id(photo_id):
                updated += 1

        self.message_user(
            request,
            f"Updated derivatives for {updated} photo(s).",
            level=messages.INFO,
        )
