from django.db import migrations

VARIANT_FIELDS = (
    ("thumbnail", "thumbnail_width", "thumbnail_height"),
    ("optimized_image", "optimized_width", "optimized_height"),
)


def backfill_dimensions(apps, schema_editor):
    Photo = apps.get_model("gallery", "Photo")
    for photo in Photo.objects.all().iterator():
        update_fields = []
        for file_field, width_field, height_field in VARIANT_FIELDS:
            file = getattr(photo, file_field)
            if not file or getattr(photo, width_field):
                continue
            try:
                width, height = file.width, file.height
            except (ValueError, OSError):
                continue
            setattr(photo, width_field, width)
            setattr(photo, height_field, height)
            update_fields.extend([width_field, height_field])
        if update_fields:
            photo.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("gallery", "0006_photo_variant_dimensions"),
    ]

    operations = [
        migrations.RunPython(backfill_dimensions, migrations.RunPython.noop),
    ]
