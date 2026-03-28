from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gallery", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="photo",
            name="optimized_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="optimized/%Y/%m/%d/",
                verbose_name="Оптимизированное изображение",
            ),
        ),
        migrations.AlterField(
            model_name="photo",
            name="alt_text",
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name="Альтернативный текст (для SEO и доступности)",
            ),
        ),
        migrations.AlterField(
            model_name="photo",
            name="title",
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name="Заголовок/Описание",
            ),
        ),
    ]
