# Django Photo Gallery

Современная веб-галерея для демонстрации фотографий, созданная на Django. Проект включает адаптивный дизайн, систему загрузки изображений и удобный просмотр.

## ✨ Возможности

- **📱 Адаптивный интерфейс** — Оптимальное отображение на всех устройствах
- **🎨 Темная/светлая тема** — Автоматическое определение системной темы с возможностью переключения
- **🖼️ Умная галерея** — Ленивая загрузка, infinite scroll, полноэкранный просмотр
- **📤 Загрузка изображений** — Drag & Drop интерфейс для администраторов
- **⚡ Автоматическая оптимизация** — Конвертация в WebP, создание миниатюр
- **🔒 Административная зона** — Управление контентом через Django Admin

## 🛠 Технологии

- **Backend**: Django 3.2
- **Frontend**: Vanilla JavaScript, CSS3, HTML5
- **База данных**: PostgreSQL
- **Обработка изображений**: Pillow
- **Статические файлы**: WhiteNoise
- **Деплой**: Gunicorn

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.8 или выше
- pip (менеджер пакетов Python)
- PostgreSQL 14+ (или Docker для запуска Postgres в контейнере)

### Установка и запуск

1. **Клонируйте репозиторий**

   ```bash
   git clone https://github.com/tgeruzov/django-photo-gallery.git
   cd django-photo-gallery
   ```

2. **Создайте `.env`**

   ```bash
   # Linux/Mac
   cp .env.example .env

   # Windows PowerShell
   Copy-Item .env.example .env
   ```

3. **Запуск через Docker (рекомендуется)**

   ```bash
   docker compose up --build
   ```

   Приложение будет доступно на `http://localhost:8000`.

4. **Локальный запуск (без Docker)**

   ```bash
   python -m venv .venv

   # Активация для Windows:
   .venv\Scripts\activate

   # Активация для Linux/Mac:
   source .venv/bin/activate
   ```

   # Установите зависимости
   pip install -r requirements.txt

   # Убедитесь, что PostgreSQL запущен и доступен по DB_HOST/DB_PORT из .env
   python manage.py migrate

   # Опционально
   python manage.py createsuperuser

   # Запуск сервера
   python manage.py runserver
   ```

## 📁 Структура проекта

```text
django-photo-gallery/
├── config/                 # Настройки Django проекта
│   ├── settings.py        # Конфигурация
│   ├── urls.py           # Главные URL-ы
│   └── wsgi.py           # WSGI конфигурация
├── gallery/               # Основное приложение
│   ├── models.py         # Модели базы данных
│   ├── views.py          # Представления
│   ├── forms.py          # Формы загрузки
│   ├── tasks.py          # Обработка изображений
│   └── templates/        # HTML шаблоны
├── static/               # Статические файлы
│   ├── css/styles.css    # Стили
│   └── js/script.js      # JavaScript
├── manage.py             # Скрипт управления Django
└── requirements.txt      # Зависимости проекта
```

## 👨‍💼 Административные функции

Для доступа к функциям администрирования:

- Войдите как суперпользователь
- Перейдите на `/upload` для загрузки изображений
- Используйте `/admin` для полного управления контентом

### Возможности администратора:

- Множественная загрузка изображений
- Автоматическое создание миниатюр
- Оптимизация изображений
- Управление метаданными фотографий

## 🎨 Кастомизация

### Настройка размеров изображений

Отредактируйте `gallery/constants.py`:

```python
THUMBNAIL_SIZE = (800, 800)           # Размер миниатюр
OPTIMIZED_IMAGE_SIZE = (2560, 2560)   # Оптимизированные изображения
```

### Изменение цветовой схемы

Настройте CSS переменные в `static/css/styles.css`:

```css
:root {
  --accent-color: #56b2da; /* Основной цвет */
  --bg-color: #1a1a1a; /* Фон темной темы */
  --text-color: #f7f7f7; /* Текст темной темы */
}
```

## 🌐 Деплой в продакшен

### Чеклист для продакшена

- Установить `DEBUG = False`
- Настроить `ALLOWED_HOSTS`
- Использовать переменные окружения для `SECRET_KEY`
- Настроить продакшен базу данных PostgreSQL
- Собрать статические файлы: `python manage.py collectstatic`
- Настроить хостинг медиафайлов

### Пример настроек для продакшена

```python
# config/settings.py
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# Безопасность
SECRET_KEY = os.environ.get('SECRET_KEY')
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# База данных PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': '5432',
    }
}
```

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. Подробнее см. в файле LICENSE.
