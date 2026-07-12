from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gallery", "0002_add_optimized_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="photo",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="photos/%Y/%m/%d/",
                verbose_name="Оригинальное изображение",
            ),
        ),
    ]
