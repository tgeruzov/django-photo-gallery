# Timeweb Shared Hosting Deployment Guide

This project is now adapted for Timeweb virtual hosting with Apache + `mod_wsgi`.
The deployment target is a shared hosting account, not a VPS:

- no Docker
- no Celery / Redis
- no `systemd`
- no custom Nginx
- no long-running background workers

The application processes photo derivatives synchronously inside the current web
request and can optionally backfill missing files through a small cron batch.

## What Changed For Shared Hosting

### Runtime

- Removed mandatory `Celery` imports from the Django startup path.
- Derivative generation now runs inline through `gallery.tasks.schedule_photo_derivatives()`.
- Added `process_photo_derivatives` management command for small cron batches.

### Shared-hosting configuration

- Added [`config/settings_shared.py`](../config/settings_shared.py) with MySQL-first settings and SQLite fallback.
- Added [`.env.shared.example`](../.env.shared.example) with all shared-hosting variables.
- Added root [`wsgi.py`](../wsgi.py) for Timeweb `mod_wsgi`.
- Added root [`.htaccess`](../.htaccess) for Apache rewrite handling.
- Added [`requirements-shared.txt`](../requirements-shared.txt) with shared-safe dependencies.

## Directory Layout On Timeweb

Timeweb documents the common layout as a site directory containing `public_html`
and a sibling virtual environment. Keep that structure:

```text
/home/u/<user>/<site>/
├── public_html/        # project files from this repository
│   ├── manage.py
│   ├── wsgi.py
│   ├── .htaccess
│   ├── config/
│   ├── gallery/
│   ├── static/         # source static files kept in repo
│   ├── staticfiles/    # collectstatic output
│   └── media/          # user uploads
├── venv/
└── data/               # optional SQLite location, outside public_html
```

## Files To Upload

Upload the repository contents into `public_html/`.

Critical files for shared hosting:

- `wsgi.py`
- `.htaccess`
- `config/settings_shared.py`
- `.env` created from `.env.shared.example`

Do not use these VPS-only assets on shared hosting:

- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `deploy/timeweb/*.service`
- `deploy/timeweb/nginx.conf`
- `scripts/run_web.sh`
- `scripts/run_worker.sh`

They can stay in the repository, but they are not used by the shared-hosting deployment.

## 1. Create The Python Environment

Connect over SSH or open the Timeweb web console, then create the virtualenv one
level above `public_html`:

```bash
cd ~/site
python3 -m venv venv
. venv/bin/activate
python -m pip install --upgrade pip
pip install -r public_html/requirements-shared.txt
```

Some Timeweb shared accounts do not ship `python3 -m venv` or `pip` out of the box.
If the command above fails, bootstrap `pip` and use `virtualenv` instead:

```bash
cd ~
curl -fsSLo get-pip.py https://bootstrap.pypa.io/pip/3.6/get-pip.py
python3 get-pip.py --user
python3 -m virtualenv -p /usr/bin/python3 ~/site/venv
. ~/site/venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r ~/site/public_html/requirements-shared.txt
```

If you already have a Python 3 virtual environment, reuse it.

## 2. Configure Environment Variables

Inside `public_html/`, create `.env` from the shared example:

```bash
cd ~/site/public_html
cp .env.shared.example .env
```

Minimum required variables:

- `DJANGO_ENV=shared`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DB_ENGINE=mysql` with MySQL credentials

Recommended MySQL configuration:

```env
DJANGO_ENV=shared
DEBUG=0
SECRET_KEY=<long-random-secret>
ALLOWED_HOSTS=example.ru,www.example.ru
CSRF_TRUSTED_ORIGINS=https://example.ru,https://www.example.ru
DB_ENGINE=mysql
DB_NAME=example_db
DB_USER=example_db
DB_PASSWORD=<password>
DB_HOST=127.0.0.1
DB_PORT=3306
DB_CHARSET=utf8mb4
```

SQLite fallback is supported, but only if you explicitly switch:

```env
DB_ENGINE=sqlite
SQLITE_PATH=/home/u/<user>/site/data/db.sqlite3
```

## 3. Database Choice

### Preferred: MySQL

Use a MySQL database created through the Timeweb panel:

1. Open the database section in the hosting panel.
2. Create a MySQL database and user.
3. Put the credentials into `.env`.
4. Run migrations.

### Fallback: SQLite

SQLite is supported for small or temporary deployments, but it is slower on
Timeweb `mod_wsgi` than MySQL. If you use it:

- keep the `.sqlite3` file outside `public_html`
- install `pysqlite3-binary` from `requirements-shared.txt`
- keep upload and admin traffic low

The provided root `wsgi.py` automatically swaps `sqlite3` to `pysqlite3` when
`DB_ENGINE=sqlite`, which matches Timeweb's workaround for slow SQLite on Python
3.10 + `mod_wsgi`.

## 4. Run Django Release Commands

From `public_html/` inside the activated virtualenv:

```bash
export DJANGO_ENV=shared
python manage.py migrate --settings=config.settings_shared
python manage.py collectstatic --noinput --settings=config.settings_shared
python manage.py check --deploy --settings=config.settings_shared
```

If you use `.env`, the explicit `export DJANGO_ENV=shared` is optional, but it
helps avoid mistakes during the first deploy.

## 5. Apache / mod_wsgi Entry Point

Timeweb runs Python apps through Apache `mod_wsgi`, so the root files must be in
`public_html/`:

- `wsgi.py`
- `.htaccess`

### `wsgi.py`

The root `wsgi.py` does four things:

1. Activates the virtualenv from `../venv/bin/activate_this.py` by default.
2. Adds `public_html` to `sys.path`.
3. Switches SQLite to `pysqlite3` when needed.
4. Starts Django with `config.settings_shared`.

The default Timeweb layout works without extra Apache environment variables as
long as the virtualenv is stored in `../venv`.

### `.htaccess`

The root `.htaccess`:

- enables WSGI handling for `.py`
- routes application requests into `wsgi.py`
- rewrites `/static/...` to collected assets in `/staticfiles/...`

This keeps Django's `STATIC_URL=/static/` while still allowing `collectstatic`
to write into `public_html/staticfiles/`.

## 6. Static And Media Files

### Static files

Shared profile uses:

- `STATIC_URL=/static/`
- `STATIC_ROOT=<project>/staticfiles`

After each deploy:

```bash
python manage.py collectstatic --noinput --settings=config.settings_shared
```

Apache serves requests for `/static/...` through `.htaccess`, which rewrites them
to `/staticfiles/...`.

### Media files

Shared profile uses:

- `MEDIA_URL=/media/`
- `MEDIA_ROOT=<project>/media`

Uploads are stored directly in `public_html/media/` so Apache can serve them as
ordinary files.

Create the directory once if it does not exist:

```bash
mkdir -p media
```

## 7. Optional Cron Jobs In Timeweb Panel

Timeweb cron jobs are configured only through the hosting panel, not through
`crontab -e`.

Recommended jobs:

### Clear expired Django sessions once per day

- Interpreter: `Python`
- Script/command:

```bash
/home/u/<user>/site/venv/bin/python /home/u/<user>/site/public_html/manage.py clearsessions --settings=config.settings_shared
```

### Backfill missing thumbnails/optimized files in small batches every 15 minutes

Use this only if you import photos outside the normal upload flow or need a
repair path for old records.

```bash
/home/u/<user>/site/venv/bin/python /home/u/<user>/site/public_html/manage.py process_photo_derivatives --limit 10 --settings=config.settings_shared
```

Why the limit matters:

- it keeps CPU spikes short
- it avoids long blocking jobs on shared hosting
- it makes retries safe

## 8. Performance Notes For Shared Hosting

The shared profile is intentionally conservative:

- uploads are processed synchronously
- no queue worker is required
- `FILE_UPLOAD_MAX_MEMORY_MB` defaults to `2`
- `MAX_UPLOAD_SIZE_MB` defaults to `100`
- `MAX_IMAGE_PIXELS` defaults to `60000000`
- `MAX_JSON_PAGE_SIZE` defaults to `100`

If your hosting plan is small, keep those defaults unless you have a measured
reason to increase them.

## 9. Degraded / Changed Features Compared To VPS

- No asynchronous task queue: photo derivative generation is inline.
- No Redis broker or result backend.
- No worker auto-retries outside the current request/cron run.
- No Gunicorn/Nginx stack; only Apache `mod_wsgi`.
- Large bulk uploads are less tolerant than on a VPS because the same Apache
  worker also performs image processing.

In practice, this means:

- normal admin uploads still work
- each upload request takes longer because thumbnails and optimized files are built immediately
- if you expect long-running or CPU-heavy jobs, shared hosting is the wrong target

## 10. Deployment Checklist

Verify all items after the first deploy:

1. `https://your-domain/health/` returns `{"status":"ok"}`.
2. `https://your-domain/admin/` opens without `DisallowedHost`.
3. Static files load on the admin login page.
4. Uploading a test image creates:
   - original file
   - optimized file
   - thumbnail
5. Uploaded images open from the public gallery.
6. `python manage.py check --deploy --settings=config.settings_shared` finishes without fatal errors.
7. If using MySQL, `python manage.py dbshell --settings=config.settings_shared` or a test query succeeds.
8. If using SQLite, the file lives outside `public_html`.
9. Cron email reports are configured in Timeweb if you enabled cron jobs.

## References

The shared-hosting decisions above follow Timeweb's current Python and Django documentation:

- [Python hosting overview](https://timeweb.com/ru/services/hosting/python/)
- [Django on virtual hosting](https://timeweb.com/ru/docs/virtualnyj-hosting/prilozheniya-i-frejmvorki/django/)
- [Cron on virtual hosting](https://timeweb.com/ru/docs/virtualnyj-hosting/planirovshchik-zadanij-cron/)
