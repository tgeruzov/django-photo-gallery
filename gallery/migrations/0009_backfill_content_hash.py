import hashlib

from django.db import migrations


def backfill_content_hash(apps, schema_editor):
    Photo = apps.get_model("gallery", "Photo")
    seen = set()
    for photo in Photo.objects.exclude(image="").iterator():
        hasher = hashlib.sha256()
        try:
            with photo.image.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    hasher.update(chunk)
        except (OSError, ValueError):
            continue
        digest = hasher.hexdigest()
        # У уже существующих дубликатов хеш остаётся NULL,
        # чтобы не нарушить unique-констрейнт.
        if digest in seen:
            continue
        seen.add(digest)
        photo.content_hash = digest
        photo.save(update_fields=["content_hash"])


class Migration(migrations.Migration):
    dependencies = [
        ("gallery", "0008_photo_content_hash"),
    ]

    operations = [
        migrations.RunPython(backfill_content_hash, migrations.RunPython.noop),
    ]
