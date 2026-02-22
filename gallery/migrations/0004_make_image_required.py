from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0003_make_image_optional'),
    ]

    operations = [
        migrations.AlterField(
            model_name='photo',
            name='image',
            field=models.ImageField(
                upload_to='photos/%Y/%m/%d/',
                verbose_name='Оригинальное изображение',
            ),
        ),
    ]
