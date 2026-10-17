# Команды разработки. Без make (например, в Windows) те же команды
# можно запускать напрямую: они перечислены в README, раздел "Разработка".

COMPOSE ?= docker compose
IMAGE ?= django-photo-gallery

.PHONY: help install dev down build start test check lint format audit

help: ## Список команд
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-8s %s\n", $$1, $$2}'

install: ## Инструменты разработки локально: линтер, coverage, pip-audit
	pip install -r requirements-dev.txt

dev: ## Галерея с базой на localhost:8000, правки кода подхватываются сами
	$(COMPOSE) up --build

down: ## Остановить контейнеры, база и фото сохраняются
	$(COMPOSE) down

build: ## Собрать образ для сервера
	docker build -t $(IMAGE) .

start: build ## Запустить образ для сервера с настройками из .env
	docker run --rm -p 8000:8000 --env-file .env $(IMAGE)

test: ## Тесты в контейнере, база поднимается сама
	$(COMPOSE) run --rm web python manage.py test

check: ## Проверки Django и миграции, которые забыли создать
	$(COMPOSE) run --rm web sh -c "python manage.py check && python manage.py makemigrations --check --dry-run"

lint: ## Линтер и формат Python, синтаксис JS (после make install)
	ruff check .
	ruff format --check .
	node --check static/js/script.js
	node --check static/js/manage.js

format: ## Отформатировать Python-код
	ruff format .
	ruff check --fix .

audit: ## Известные уязвимости в зависимостях
	pip-audit -r requirements.txt
