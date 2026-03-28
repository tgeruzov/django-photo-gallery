<h1 align="center">Django Photo Gallery</h1>

<p align="center">
  A modern Django + PostgreSQL photo gallery with infinite scroll, optimized images, and fullscreen lightbox experience.
</p>

<p align="center">
  <a href="https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml/badge.svg">
  </a>
  <a href="https://www.python.org/downloads/release/python-3110/">
    <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-2F6DB3?logo=python&logoColor=white">
  </a>
  <a href="https://www.djangoproject.com/">
    <img alt="Django 3.2" src="https://img.shields.io/badge/Django-3.2-0C4B33?logo=django&logoColor=white">
  </a>
  <a href="https://www.postgresql.org/">
    <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white">
  </a>
  <a href="LICENSE">
    <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-F2C94C">
  </a>
</p>

<p align="center">
  <a href="#at-a-glance">At a Glance</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#api-and-routes">API & Routes</a> •
  <a href="#project-layout">Project Layout</a> •
  <a href="#community">Community</a>
</p>

---

## At a Glance

| Capability | Details |
| --- | --- |
| Gallery UX | Masonry-style grid with lazy reveal and infinite scroll |
| Viewing | Fullscreen lightbox with keyboard and mobile swipe navigation |
| Upload | Multi-file upload for staff users with drag-and-drop |
| Image pipeline | Original + optimized + thumbnail generated on upload |
| Background jobs | Celery-ready derivative backfill with eager local fallback |
| API | Paginated JSON endpoint for full gallery data |
| Deployment | Docker Compose and local setup workflows |
| CI | GitHub Actions: pre-commit + migrate + Django tests |

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Django 3.2 |
| Database | PostgreSQL (Docker uses `postgres:16-alpine`) |
| Frontend | Vanilla JS + HTML + CSS |
| Image processing | Pillow |
| Static serving | WhiteNoise (enabled when `DEBUG=False`) |
| App server | Gunicorn |
| Background tasks | Celery + Redis (production profile) |

## Quick Start

### 1) Clone repository

```bash
git clone https://github.com/tgeruzov/django-photo-gallery.git
cd django-photo-gallery
```

### 2) Create environment file

```bash
# Linux / macOS
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

### 3) Run with Docker (recommended)

```bash
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000)

<details>
<summary><strong>Run locally (without Docker)</strong></summary>

```bash
python -m venv .venv
```

```bash
# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
</details>

### 4) Install developer tooling

```bash
pip install -r requirements-dev.txt
pre-commit install
```

### 5) Production-like profile

```bash
docker compose -f docker-compose.prod.yml up --build
```

This profile runs:

- Django with `DJANGO_ENV=prod`
- Gunicorn for the web app
- Celery worker for background jobs
- Redis as the broker/backend
- PostgreSQL for persistence
- Shared named volumes for `media/` and collected static files

For localhost smoke-testing this profile keeps `SECURE_SSL_REDIRECT=0` so the app remains reachable over plain HTTP. In a real deployment behind HTTPS, turn it back on.

## Environment Variables

Use `.env.example` as a base:

| Variable | Purpose |
| --- | --- |
| `DJANGO_ENV` | Selects `dev` or `prod` settings |
| `DEBUG` | Enables debug mode |
| `SECRET_KEY` | Django secret key |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for secure deployments |
| `TIME_ZONE` | Application and Celery timezone |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port |
| `DB_CONN_MAX_AGE` | Persistent DB connection lifetime in seconds |
| `MAX_UPLOAD_SIZE_MB` | Max upload size per file |
| `MAX_IMAGE_PIXELS` | Pixel safety guard for image parsing |
| `MAX_JSON_PAGE_SIZE` | Max `page_size` for JSON endpoint |
| `DELETE_ORIGINAL_AFTER_OPTIMIZE` | Deletes original after optimization if enabled |
| `ENABLE_BACKGROUND_TASKS` | Enables asynchronous derivative generation |
| `CELERY_TASK_ALWAYS_EAGER` | Executes Celery tasks inline when enabled |
| `CELERY_BROKER_URL` | Celery broker connection string |
| `CELERY_RESULT_BACKEND` | Celery result backend |
| `SECURE_SSL_REDIRECT` | Forces HTTPS redirects in production mode |
| `SECURE_HSTS_SECONDS` | HSTS max-age for secure deployments |
| `LOG_LEVEL` | Base log verbosity |

## API and Routes

| Route | Method | Description |
| --- | --- | --- |
| `/` | GET | Main gallery page (supports AJAX pagination via `?page=`) |
| `/upload/` | GET, POST | Staff-only multi-file upload page |
| `/all_photos.json` | GET | Paginated JSON API (`page`, `page_size`) |
| `/admin/` | GET | Django admin |

### Example: JSON response

```json
{
  "photos": [
    {
      "id": 1,
      "url": "/media/thumbnails/2026/02/25/image.webp",
      "full_url": "/media/optimized/2026/02/25/image.webp",
      "title": "My photo"
    }
  ],
  "page": 1,
  "page_size": 100,
  "has_next": true,
  "total": 240
}
```

## Project Layout

```text
django-photo-gallery/
├── config/                  # Django config, split settings, Celery wiring
├── gallery/                 # Gallery app (models, views, forms, utils)
├── static/                  # CSS, JS, icons
├── .github/workflows/       # CI pipeline
├── docker-compose.yml
├── docker-compose.prod.yml
├── pyproject.toml
├── .pre-commit-config.yaml
├── requirements.txt
├── requirements-dev.txt
└── manage.py
```

## Production Checklist

- Set `DJANGO_ENV=prod`
- Set `DEBUG=False`
- Configure strict `ALLOWED_HOSTS`
- Configure `CSRF_TRUSTED_ORIGINS`
- Use strong `SECRET_KEY`
- Apply secure PostgreSQL credentials from environment
- Run `python manage.py collectstatic --noinput`
- Run a Celery worker with Redis
- Configure media storage and backup policy
- Keep HTTPS enabled for secure cookies/HSTS behavior

## Community

- [Contributing Guide](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## License

Released under the MIT License. See [LICENSE](LICENSE).
