FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN DEBUG=0 SECRET_KEY=collectstatic python manage.py collectstatic --noinput

# Приложение работает не от root: писать ему нужно только в media/
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/media \
    && chown app:app /app/media
USER app

EXPOSE 8000

# Продакшен-запуск; docker-compose.yml для разработки заменяет его на runserver
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
