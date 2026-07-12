FROM python:3.11-slim

# Запуск образа без compose не должен молча стартовать на dev-настройках;
# dev-компоуз переопределяет DJANGO_ENV явно.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=prod

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app

USER app

EXPOSE 8000

# shell-форма ради ${GUNICORN_WORKERS:-3}; --max-requests страхует от
# утечек памяти Pillow, access-лог уходит в stdout
CMD gunicorn config.wsgi:application --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} --timeout 120 \
    --max-requests 500 --max-requests-jitter 50 --access-logfile -
