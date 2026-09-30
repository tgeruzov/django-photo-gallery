from django.conf import settings
from django.core.exceptions import ValidationError


def validate_file_size(uploaded_file):
    """Проверяет размер файла по MAX_UPLOAD_SIZE_MB."""
    limit_mb = settings.MAX_UPLOAD_SIZE_MB
    limit_bytes = limit_mb * 1024 * 1024
    if uploaded_file.size > limit_bytes:
        raise ValidationError(
            f"Файл слишком большой ({uploaded_file.size // 1024 // 1024}MB). Максимум: {limit_mb}MB"
        )


def validate_image_type(uploaded_file):
    """Проверяет тип изображения по сигнатурам файлов"""
    uploaded_file.seek(0)
    header = uploaded_file.read(12)  # Читаем первые байты
    uploaded_file.seek(0)

    # Сигнатуры форматов
    if header.startswith(b"\xff\xd8\xff"):
        return  # JPEG
    elif header.startswith(b"\x89PNG\r\n\x1a\n"):
        return  # PNG
    elif header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return  # WEBP

    raise ValidationError("Недопустимый формат файла. Разрешены только JPEG, PNG, WEBP.")
