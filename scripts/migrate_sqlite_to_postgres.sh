#!/usr/bin/env bash
set -euo pipefail

DUMP_FILE="${1:-data_dump.json}"
USE_DOCKER="${USE_DOCKER:-0}"

if [[ ! -f "db.sqlite3" ]]; then
  echo "Файл db.sqlite3 не найден. Нечего переносить."
  exit 1
fi

if [[ "$USE_DOCKER" == "1" ]]; then
  echo "Запуск PostgreSQL (Docker)..."
  docker compose up -d db >/dev/null

  echo "Дамп данных из SQLite в $DUMP_FILE (Docker)..."
  docker compose run --rm \
    -e DB_ENGINE=sqlite3 \
    -e DB_NAME= \
    -e DB_USER= \
    -e DB_PASSWORD= \
    -e DB_HOST= \
    -e DB_PORT= \
    web python manage.py migrate >/dev/null
  docker compose run --rm \
    -e DB_ENGINE=sqlite3 \
    -e DB_NAME= \
    -e DB_USER= \
    -e DB_PASSWORD= \
    -e DB_HOST= \
    -e DB_PORT= \
    web python manage.py dumpdata --exclude contenttypes --exclude auth.permission --indent 2 --output "$DUMP_FILE" >/dev/null

  echo "Загрузка данных в PostgreSQL (Docker)..."
  docker compose run --rm web python manage.py migrate >/dev/null
  docker compose run --rm web python manage.py loaddata "$DUMP_FILE"

  echo "Готово."
  exit 0
fi

echo "Дамп данных из SQLite в $DUMP_FILE (локально)..."
export DB_NAME=""
export DB_USER=""
export DB_PASSWORD=""
export DB_HOST=""
export DB_PORT=""
export DB_ENGINE="sqlite3"

python manage.py migrate >/dev/null
python manage.py dumpdata --exclude contenttypes --exclude auth.permission --indent 2 --output "$DUMP_FILE"

echo "Загрузка данных в PostgreSQL (локально)..."
unset DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT DB_ENGINE

python manage.py migrate >/dev/null
python manage.py loaddata "$DUMP_FILE"

echo "Готово."
