# Django Photo Gallery

[English version](README.md)

[![CI](https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml/badge.svg)](https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/Python-3.11-2F6DB3?logo=python&logoColor=white)
![Django 5.2](https://img.shields.io/badge/Django-5.2-0C4B33?logo=django&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
[![MIT License](https://img.shields.io/badge/License-MIT-F2C94C)](LICENSE)

Персональная фотогалерея на Django: сетка с бесконечной прокруткой, полноэкранный просмотр и страница загрузки для staff. Загруженные фото конвертируются в WEBP-миниатюры и оптимизированные полноразмерные версии.

<p align="center">
  <img src="docs/image.png" alt="Галерея" width="32%">
  <img src="docs/upload-preview.png" alt="Страница загрузки" width="32%">
  <img src="docs/lightbox-preview.jpg" alt="Просмотр фото" width="32%">
</p>

## Возможности

- Masonry-сетка с keyset-пагинацией и ленивой загрузкой
- Лайтбокс с навигацией с клавиатуры и свайпами
- Пакетная загрузка для staff с проверкой формата, размера и дубликатов (SHA-256)
- Миниатюры и оптимизированные версии генерирует Celery, без воркера обработка идёт синхронно
- SEO: canonical, Open Graph, JSON-LD, sitemap, robots.txt

## Как обрабатывается загрузка

1. Staff загружает один или несколько файлов JPEG, PNG или WEBP.
2. Форма проверяет расширение, сигнатуру файла и размер; дубликаты по хешу содержимого пропускаются.
3. Сохраняется оригинал, после коммита задача строит миниатюру (800px) и оптимизированную версию (2560px).
4. В сетке показываются миниатюры, в лайтбоксе оптимизированные версии.

Фото, оставшиеся без вариантов (упал воркер, потерялась очередь), подбирает периодическая задача Celery beat или команда `python manage.py generate_derivatives`.

## Запуск

### Docker

```bash
cp .env.example .env
docker compose up --build
```

Приложение откроется на http://localhost:8000.

### Локально через Python

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
cp .env.example .env           # DJANGO_ENV=dev; DB_ENGINE=sqlite, если нет локального PostgreSQL
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Без `DJANGO_ENV` проект стартует в режиме `prod` и не поднимется без сильного `SECRET_KEY`.

### Продакшен-профиль

```bash
docker compose -f docker-compose.prod.yml up --build
```

Сервисы: PostgreSQL, Redis, Django под Gunicorn, Celery worker с beat, nginx для статики и медиа, ежедневные бэкапы через `pg_dump`. В профиле стоит `SECURE_SSL_REDIRECT=0`, чтобы он работал по HTTP на localhost; за HTTPS-прокси его нужно включить.

## Маршруты

| Маршрут | Назначение |
| --- | --- |
| `/` | Галерея |
| `/upload/` | Загрузка фото (только staff) |
| `/all_photos.json` | Пагинированный JSON API |
| `/admin/` | Админка Django |
| `/healthz` | Проверка живости (приложение и БД) |

Пример ответа `/all_photos.json`:

```json
{
  "photos": [
    {
      "id": 1,
      "uploaded_at": "2026-02-25T18:04:12.345678+00:00",
      "url": "/media/thumbnails/2026/02/25/image_thumb.webp",
      "full_url": "/media/optimized/2026/02/25/image_optimized.webp",
      "title": "Моё фото",
      "alt_text": "Моё фото",
      "width": 800,
      "height": 533
    }
  ],
  "page": 1,
  "page_size": 200,
  "has_next": true,
  "total": 240
}
```

## Настройки

Все переменные с комментариями перечислены в [.env.example](.env.example). Основные:

- Приложение: `DJANGO_ENV`, `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- База данных: `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Изображения: `MAX_UPLOAD_SIZE_MB`, `MAX_IMAGE_PIXELS`, `DELETE_ORIGINAL_AFTER_OPTIMIZE`
- Фоновые задачи: `ENABLE_BACKGROUND_TASKS`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`

## Разработка

```bash
pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
DJANGO_ENV=test python manage.py test
```

CI (GitHub Actions) запускает pre-commit (Ruff), pip-audit, `check --deploy`, миграции и тесты на PostgreSQL.

## Чеклист для продакшена

- `DJANGO_ENV=prod`, `DEBUG=0`
- Сильный случайный `SECRET_KEY` и недефолтный `DB_PASSWORD`
- `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` под свой домен
- HTTPS и `SECURE_SSL_REDIRECT=1`
- Redis и Celery worker или `generate_derivatives` по cron
- Бэкапы `media/` и базы данных

## Лицензия

MIT, см. [LICENSE](LICENSE).
