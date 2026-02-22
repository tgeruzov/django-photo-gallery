# Django Photo Gallery (PostgreSQL)

[![CI](https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml/badge.svg)](https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Django 3.2](https://img.shields.io/badge/django-3.2-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

A production-ready **Django photo gallery** with **PostgreSQL**, image optimization, thumbnails, infinite scroll, and fullscreen lightbox view.
This repository is configured for GitHub CI and community collaboration.

## SEO Keywords

`django photo gallery`, `django image gallery`, `postgresql django project`, `webp image optimization`, `infinite scroll gallery`, `lightbox viewer`, `photo upload app`

## Features

- Responsive masonry-style gallery layout
- Infinite scroll with JSON pagination
- Fullscreen lightbox with keyboard and mobile gestures
- Multi-file upload for staff users
- Automatic image optimization and thumbnail generation
- Dark/light theme toggle
- PostgreSQL-only backend setup
- Docker and local development flows

## Tech Stack

- Backend: Django 3.2
- Database: PostgreSQL
- Frontend: Vanilla JS, HTML, CSS
- Image processing: Pillow
- Static files: WhiteNoise
- App server: Gunicorn

## Quick Start

### Requirements

- Python 3.8+
- PostgreSQL 14+ (or Docker)
- pip

### 1. Clone the repository

```bash
git clone https://github.com/tgeruzov/django-photo-gallery.git
cd django-photo-gallery
```

### 2. Create environment file

```bash
# Linux/Mac
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

### 3. Run with Docker (recommended)

```bash
docker compose up --build
```

App will be available at `http://localhost:8000`.

### 4. Run locally (without Docker)

```bash
python -m venv .venv
```

```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # optional
python manage.py runserver
```

## Environment Variables

Use `.env.example` as a template:

- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `MAX_UPLOAD_SIZE_MB`
- `MAX_IMAGE_PIXELS`
- `MAX_JSON_PAGE_SIZE`
- `DELETE_ORIGINAL_AFTER_OPTIMIZE`

## Main Routes

- `/` - gallery index
- `/upload/` - multi-file upload page (staff only)
- `/all_photos.json` - paginated JSON endpoint for all photos
- `/admin/` - Django admin

## Project Structure

```text
django-photo-gallery/
├── config/
├── gallery/
├── static/
├── .github/workflows/
├── manage.py
├── docker-compose.yml
└── requirements.txt
```

## Production Notes

- Set `DEBUG=False`
- Configure `ALLOWED_HOSTS`
- Set a secure `SECRET_KEY`
- Use PostgreSQL credentials from environment
- Run `python manage.py collectstatic`
- Configure media storage and backup policy

## Community and Collaboration

- Contributing guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
- Code of Conduct: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)

## License

Distributed under MIT License. See [`LICENSE`](LICENSE).
