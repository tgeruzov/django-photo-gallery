from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Photo
from .tasks import create_thumbnail_for_photo

@receiver(post_save, sender=Photo)
def create_thumbnail_on_save(sender, instance, created, **kwargs):
    if created and not instance.thumbnail:
        create_thumbnail_for_photo(instance.id)