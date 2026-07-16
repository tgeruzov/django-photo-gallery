# Деплой и обновление на shared-хостинге Timeweb

Сайт (tgeruzov.ru, arclume.ru) работает на виртуальном хостинге Timeweb под
**Apache + mod_wsgi**, база — **MySQL**. Это не Docker: gunicorn/Celery/Redis
здесь не используются. Профиль настроек — `DJANGO_ENV=shared`
(`config/settings/shared.py`).

Раскладка на сервере:

```
~/django/
├── venv/                 # виртуальное окружение (Python 3.10)
└── public_html/          # корень сайта (= BASE_DIR проекта)
    ├── config/ gallery/ … # код проекта
    ├── media/            # оригиналы и варианты фото (НЕ трогать при обновлении)
    ├── staticfiles/      # результат collectstatic (Apache отдаёт как /static/)
    ├── .env              # секреты (на сервере, в git не хранится)
    ├── .htaccess         # см. deploy/timeweb/.htaccess
    └── wsgi.py           # см. deploy/timeweb/wsgi.py
```

Команды выполняются в **веб-консоли панели** (раздел «SSH-консоль»). Всё, что
ниже — по одному блоку; проверяйте вывод перед следующим шагом.

---

## 0. Предусловия (один раз)

Python 3.10 должен быть выбран в настройках сайта (панель → Сайты → django →
«Настройки версий» → PHP 8.x + Python 3.10). Django 5.2 требует Python ≥ 3.10.

Проверить версию интерпретатора текущего venv:

```bash
~/django/venv/bin/python --version
```

Если это **не** 3.10 (сейчас сайт на Django 3.2 мог жить на более старом
Python) — venv нужно пересоздать на 3.10 (шаг 3).

---

## 1. Резервная копия (обязательно, до любых изменений)

```bash
cd ~/django/public_html
TS=$(date +%Y%m%d-%H%M%S)

# База данных (пароль возьмите из .env; -p без пробела запросит его интерактивно)
mysqldump -h localhost -u co66275_djangophotogallery -p \
  co66275_djangophotogallery > ~/backup-db-$TS.sql

# Код + .env + собранная статика (media отдельно — он большой, копируем при желании)
tar czf ~/backup-code-$TS.tgz --exclude=media config gallery templates static \
  staticfiles .env .htaccess wsgi.py manage.py

ls -lh ~/backup-*$TS*
```

Также сделайте резервную копию через панель → «Резервные копии» (полный снапшот
аккаунта) — это самый надёжный откат.

---

## 2. Обновление кода

Как код попадает на сервер, зависит от того, был ли он выложен через git.

```bash
cd ~/django/public_html
git status          # если это git-репозиторий
```

**Если git есть:**

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

**Если git нет** (код заливали по FTP): загрузите содержимое ветки `main`
через файловый менеджер / FTP поверх `public_html`, НЕ удаляя `media/`,
`staticfiles/`, `.env`. Каталог `config/settings/` должен заменить старый
одиночный `config/settings_shared.py` (его можно удалить после проверки).

---

## 3. Виртуальное окружение и зависимости

Если venv уже на Python 3.10 — просто обновите пакеты:

```bash
cd ~/django
venv/bin/pip install --upgrade pip
venv/bin/pip install -r public_html/deploy/timeweb/requirements-shared.txt
```

Если нужно пересоздать venv на 3.10 (имя интерпретатора уточните: `python3.10`):

```bash
cd ~/django
mv venv venv.old
python3.10 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r public_html/deploy/timeweb/requirements-shared.txt
# убедитесь, что в venv/bin есть activate_this.py; если нет — wsgi.py это учитывает
```

---

## 4. Настройки окружения и точки входа

1. Обновите `public_html/.env` по образцу `deploy/timeweb/.env.shared.example`:
   поставьте `DJANGO_ENV=shared`, `DB_ENGINE=mysql`, реальные `DB_*`, длинный
   `SECRET_KEY`, домены в `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`.
2. Замените `public_html/wsgi.py` содержимым `deploy/timeweb/wsgi.py`.
3. Сверьте `public_html/.htaccess` с `deploy/timeweb/.htaccess`.

---

## 5. Миграции и статика

```bash
cd ~/django/public_html
export DJANGO_ENV=shared
../venv/bin/python manage.py check --deploy
../venv/bin/python manage.py migrate
../venv/bin/python manage.py collectstatic --noinput
```

`check --deploy` не должен ругаться на критичное; предупреждения по HSTS
допустимы (включим позже). При апгрейде с Django 3.2 миграции применятся
поверх существующей MySQL-базы — данные (фото, пользователи) сохраняются.

---

## 6. Перезапуск и проверка

mod_wsgi перечитывает код при «touch» wsgi-файла:

```bash
touch ~/django/public_html/wsgi.py
```

Затем проверьте:

```bash
curl -sSI https://tgeruzov.ru/ | head -n 20
tail -n 40 ~/django/error_log
```

Ожидаем `HTTP/2 200`. Откройте в браузере https://tgeruzov.ru/ (главная),
`/upload/` (после входа в админку) и `/admin/`. Если вход в админку не
работает или CSRF ругается — в `.env` поставьте `USE_FORWARDED_PROTO=1` и
снова `touch wsgi.py`.

---

## 7. Откат

```bash
cd ~/django/public_html
# код:
git reset --hard <прежний_коммит>        # или распакуйте backup-code-*.tgz
# база:
mysql -h localhost -u co66275_djangophotogallery -p \
  co66275_djangophotogallery < ~/backup-db-<TS>.sql
touch wsgi.py
```

Либо восстановите снапшот аккаунта из панели «Резервные копии».

---

## Заметки по совместимости

- `config/settings_shared.py` (старый одиночный модуль) больше не нужен — его
  заменяет `config/settings/shared.py`. Перед удалением сверьте, не было ли в
  старом файле хостоспецифичных строк (нестандартные пути, `FORCE_SCRIPT_NAME`,
  доп. `ALLOWED_HOSTS`) — при наличии перенесите их в `.env` или `shared.py`.
- Статику раздаёт Apache (правило `/static/ → /staticfiles/` в `.htaccess`),
  поэтому whitenoise и хешированные имена файлов в этом профиле отключены.
- Генерация превью идёт синхронно в запросе (Celery недоступен); для тяжёлых
  фото это заметно — держите `MAX_UPLOAD_SIZE_MB` небольшим.
