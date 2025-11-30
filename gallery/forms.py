import os
from django import forms
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.conf import settings

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
            return result
        return [single_file_clean(data, initial)] if data else []

def validate_file_size(uploaded_file):
    """Проверяет размер файла - максимум 100МБ"""
    limit_mb = 100
    limit_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_MB', limit_mb) * 1024 * 1024
    if uploaded_file.size > limit_bytes:
        raise ValidationError(f'Файл слишком большой ({uploaded_file.size // 1024 // 1024}MB). Максимум: {limit_mb}MB')

def validate_image_type(uploaded_file):
    """Проверяет тип изображения по сигнатурам файлов"""
    uploaded_file.seek(0)
    header = uploaded_file.read(12)  # Читаем первые байты
    uploaded_file.seek(0)
    
    # Сигнатуры форматов
    if header.startswith(b'\xff\xd8\xff'):
        return  # JPEG
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        return  # PNG
    elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return  # WEBP
    
    # Если не распознали по сигнатуре, проверяем расширение
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.webp']:
        return  # Доверяем расширению
    
    raise ValidationError('Недопустимый формат файла. Разрешены только JPEG, PNG, WEBP.')

class PhotoUploadForm(forms.Form):
    # TODO: добавить поддержку HEIC когда будет время
    ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']

    files = MultipleFileField(
        label='Выберите файлы',
        required=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
                message='Недопустимое расширение файла. Разрешены: %(allowed_extensions)s'
            ),
            validate_file_size,
            validate_image_type,
        ]
    )