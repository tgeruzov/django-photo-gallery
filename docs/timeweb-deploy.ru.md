# Гайд по деплою на Timeweb Shared Hosting

Язык:
- [English](timeweb-deploy.md)
- [Русский](timeweb-deploy.ru.md)

Этот проект адаптирован для виртуального хостинга Timeweb с Apache + `mod_wsgi`.
Целевая среда здесь именно shared hosting, а не VPS:

- без Docker
- без Celery / Redis
- без `systemd`
- без кастомного Nginx
- без долгоживущих background workers

Производные версии изображений обрабатываются синхронно в текущем веб-запросе.
При необходимости можно отдельно догонять пропущенные файлы небольшими cron-пачками.

## Что изменилось для shared hosting

### Runtime

- Убраны обязательные `Celery`-импорты из стартового пути Django.
- Генерация производных теперь выполняется inline через `gallery.tasks.schedule_photo_derivatives()`.
- Добавлена management command `process_photo_derivatives` для небольших cron-пачек.

### Конфигурация под shared hosting

- Добавлен [`config/settings_shared.py`](../config/settings_shared.py) с MySQL-first настройкой и SQLite fallback.
- Добавлен [`.env.shared.example`](../.env.shared.example) со всеми переменными для shared hosting.
- Добавлен корневой [`wsgi.py`](../wsgi.py) для Timeweb `mod_wsgi`.
- Добавлен корневой [`.htaccess`](../.htaccess) для Apache rewrite handling.
- Добавлен [`requirements-shared.txt`](../requirements-shared.txt) с безопасным набором зависимостей для shared hosting.

## Структура директорий на Timeweb

Timeweb рекомендует держать сайт как каталог с `public_html` и соседним виртуальным окружением.
Используй именно такую структуру:

```text
/home/u/<user>/<site>/
├── public_html/        # файлы проекта из этого репозитория
│   ├── manage.py
│   ├── wsgi.py
│   ├── .htaccess
│   ├── config/
│   ├── gallery/
│   ├── static/         # исходные static-файлы из репозитория
│   ├── staticfiles/    # результат collectstatic
│   └── media/          # пользовательские загрузки
├── venv/
└── data/               # опциональное место для SQLite, вне public_html
```

## Какие файлы загружать

Загружай содержимое репозитория в `public_html/`.

Критичные файлы для shared hosting:

- `wsgi.py`
- `.htaccess`
- `config/settings_shared.py`
- `.env`, созданный из `.env.shared.example`

Не используй на shared hosting эти VPS-only артефакты:

- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `deploy/timeweb/*.service`
- `deploy/timeweb/nginx.conf`
- `scripts/run_web.sh`
- `scripts/run_worker.sh`

Они могут оставаться в репозитории, но в shared-hosting деплое не используются.

## 1. Создание Python-окружения

Подключись по SSH или открой веб-консоль Timeweb, затем создай virtualenv на уровень выше `public_html`:

```bash
cd ~/site
python3 -m venv venv
. venv/bin/activate
python -m pip install --upgrade pip
pip install -r public_html/requirements-shared.txt
```

На некоторых shared-аккаунтах Timeweb `python3 -m venv` или `pip` из коробки могут отсутствовать.
Если команда выше не работает, сначала подними `pip`, затем используй `virtualenv`:

```bash
cd ~
curl -fsSLo get-pip.py https://bootstrap.pypa.io/pip/3.6/get-pip.py
python3 get-pip.py --user
python3 -m virtualenv -p /usr/bin/python3 ~/site/venv
. ~/site/venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r ~/site/public_html/requirements-shared.txt
```

Если виртуальное окружение под Python 3 у тебя уже есть, просто переиспользуй его.

## 2. Настройка переменных окружения

Внутри `public_html/` создай `.env` из shared-примера:

```bash
cd ~/site/public_html
cp .env.shared.example .env
```

Минимально обязательные переменные:

- `DJANGO_ENV=shared`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DB_ENGINE=mysql` вместе с MySQL credentials

Рекомендуемая MySQL-конфигурация:

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

SQLite fallback тоже поддержан, но только если ты явно на него переключаешься:

```env
DB_ENGINE=sqlite
SQLITE_PATH=/home/u/<user>/site/data/db.sqlite3
```

## 3. Выбор базы данных

### Предпочтительно: MySQL

Используй MySQL-базу, созданную через панель Timeweb:

1. Открой раздел баз данных в панели хостинга.
2. Создай MySQL-базу и пользователя.
3. Внеси креды в `.env`.
4. Прогони миграции.

### Fallback: SQLite

SQLite поддержан для маленьких или временных инсталляций, но на Timeweb `mod_wsgi` он работает медленнее MySQL. Если используешь его:

- держи `.sqlite3` файл вне `public_html`
- устанавливай `pysqlite3-binary` из `requirements-shared.txt`
- не нагружай upload/admin-heavy трафиком

Корневой `wsgi.py` автоматически подменяет `sqlite3` на `pysqlite3`, когда
`DB_ENGINE=sqlite`, что повторяет Timeweb workaround для медленного SQLite на Python
3.10 + `mod_wsgi`.

## 4. Запуск release-команд Django

Из `public_html/` внутри активированного virtualenv:

```bash
export DJANGO_ENV=shared
python manage.py migrate --settings=config.settings_shared
python manage.py collectstatic --noinput --settings=config.settings_shared
python manage.py check --deploy --settings=config.settings_shared
```

Если ты используешь `.env`, явный `export DJANGO_ENV=shared` формально не обязателен,
но на первом деплое он помогает избежать случайных ошибок.

## 5. Apache / mod_wsgi entry point

Timeweb запускает Python-приложения через Apache `mod_wsgi`, поэтому корневые файлы должны лежать в
`public_html/`:

- `wsgi.py`
- `.htaccess`

### `wsgi.py`

Корневой `wsgi.py` делает четыре вещи:

1. Активирует virtualenv из `../venv/bin/activate_this.py` по умолчанию.
2. Добавляет `public_html` в `sys.path`.
3. Переключает SQLite на `pysqlite3`, если это нужно.
4. Запускает Django с `config.settings_shared`.

Стандартная структура Timeweb работает без дополнительных Apache environment variables,
если virtualenv лежит в `../venv`.

### `.htaccess`

Корневой `.htaccess`:

- включает WSGI-обработку для `.py`
- маршрутизирует запросы приложения в `wsgi.py`
- переписывает `/static/...` на собранные ассеты в `/staticfiles/...`

Это позволяет оставить `STATIC_URL=/static/`, но при этом складывать `collectstatic`
вывод в `public_html/staticfiles/`.

## 6. Static и media файлы

### Static files

Shared-профиль использует:

- `STATIC_URL=/static/`
- `STATIC_ROOT=<project>/staticfiles`

После каждого деплоя выполняй:

```bash
python manage.py collectstatic --noinput --settings=config.settings_shared
```

Apache обслуживает `/static/...` через `.htaccess`, который переписывает их
на `/staticfiles/...`.

### Media files

Shared-профиль использует:

- `MEDIA_URL=/media/`
- `MEDIA_ROOT=<project>/media`

Загрузки сохраняются напрямую в `public_html/media/`, чтобы Apache мог отдавать их как обычные файлы.

Создай директорию один раз, если её ещё нет:

```bash
mkdir -p media
```

## 7. Опциональные cron jobs в панели Timeweb

Cron в Timeweb настраивается только через панель хостинга, а не через `crontab -e`.

Рекомендуемые задания:

### Очистка устаревших Django sessions раз в день

- Interpreter: `Python`
- Script/command:

```bash
/home/u/<user>/site/venv/bin/python /home/u/<user>/site/public_html/manage.py clearsessions --settings=config.settings_shared
```

### Догон недостающих thumbnail/optimized файлов маленькими пачками каждые 15 минут

Используй это только если фотографии импортируются вне обычного upload flow
или нужен repair path для старых записей.

```bash
/home/u/<user>/site/venv/bin/python /home/u/<user>/site/public_html/manage.py process_photo_derivatives --limit 10 --settings=config.settings_shared
```

Почему важен `limit`:

- он держит CPU-всплески короткими
- не даёт запускать длинные блокирующие задания на shared hosting
- делает повторы безопасными

## 8. Performance notes для shared hosting

Shared-профиль специально сделан консервативным:

- загрузки обрабатываются синхронно
- queue worker не нужен
- `FILE_UPLOAD_MAX_MEMORY_MB` по умолчанию `2`
- `MAX_UPLOAD_SIZE_MB` по умолчанию `100`
- `MAX_IMAGE_PIXELS` по умолчанию `60000000`
- `MAX_JSON_PAGE_SIZE` по умолчанию `100`

Если у тебя небольшой тариф, лучше оставить эти дефолты, если нет измеримой причины их поднимать.

## 9. Какие фичи деградируют по сравнению с VPS

- Нет асинхронной очереди задач: генерация производных фото идёт inline.
- Нет Redis broker и result backend.
- Нет worker auto-retries вне текущего запроса/cron run.
- Нет Gunicorn/Nginx-стека, только Apache `mod_wsgi`.
- Массовые тяжёлые загрузки переносятся хуже, чем на VPS, потому что тот же Apache worker ещё и обрабатывает изображения.

На практике это означает:

- обычные загрузки из админского сценария продолжают работать
- каждый upload request длится дольше, потому что thumbnail и optimized файлы строятся сразу
- если тебе нужны долгие CPU-heavy задачи, shared hosting здесь не лучшая цель

## 10. Чеклист деплоя

После первого деплоя проверь всё по списку:

1. `https://your-domain/health/` возвращает `{"status":"ok"}`.
2. `https://your-domain/admin/` открывается без `DisallowedHost`.
3. Static-файлы грузятся на странице логина в админку.
4. Загрузка тестовой картинки создаёт:
   - оригинальный файл
   - optimized файл
   - thumbnail
5. Загруженные изображения открываются из публичной галереи.
6. `python manage.py check --deploy --settings=config.settings_shared` завершается без фатальных ошибок.
7. Если используется MySQL, `python manage.py dbshell --settings=config.settings_shared` или тестовый запрос отрабатывает успешно.
8. Если используется SQLite, файл находится вне `public_html`.
9. Если cron включён, в Timeweb настроены email-уведомления о сбоях.

## References

Решения для shared-hosting профиля выше опираются на актуальную документацию Timeweb по Python и Django:

- [Python hosting overview](https://timeweb.com/ru/services/hosting/python/)
- [Django on virtual hosting](https://timeweb.com/ru/docs/virtualnyj-hosting/prilozheniya-i-frejmvorki/django/)
- [Cron on virtual hosting](https://timeweb.com/ru/docs/virtualnyj-hosting/planirovshchik-zadanij-cron/)
