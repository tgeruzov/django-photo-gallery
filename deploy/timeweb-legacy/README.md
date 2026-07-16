# Timeweb shared-hosting — визуальный редизайн на Django 3.2

Сервер `vh400.timeweb.ru` даёт максимум **Python 3.6**, поэтому запустить
современную версию проекта (Django 5.2, требует Python ≥ 3.10) там нельзя
(см. [../timeweb/DEPLOY.md](../timeweb/DEPLOY.md) и обсуждение в истории).

По решению владельца на живой сайт перенесён **только внешний вид**: новый
дизайн из `main` (glass-topbar, переработанный лайтбокс, empty-state,
доступность), адаптированный под работающий бэкенд Django 3.2. Движок,
зависимости, модели и миграции на хостинге НЕ менялись.

Здесь лежат ровно те файлы, что задеплоены в `~/django/public_html`, чтобы
редизайн можно было воспроизвести/откатить.

## Отличия от `main` (адаптация под старый бэкенд)

- `gallery/templates/gallery/base.html` — `{% url 'gallery:upload_photo' %}`
  → `{% url 'upload_photo' %}` (в проде нет namespace `gallery:`).
- `gallery/templates/gallery/partials/photo_cards.html` — источники карточки
  (`display`/`full`) вычисляются в шаблоне из `photo.thumbnail/optimized_image/
  image`, т.к. в старой модели нет `display_label`/`card_sources`/
  `display_dimensions`. `width`/`height` намеренно опущены (у старого бэкенда
  их чтение открывает файл и может уронить страницу, если файла нет).
- `static/script.js` — лента форсирует **offset-пагинацию** (`?page=N`), а не
  keyset-курсор `?after=<id>` из `main`: старый `index`-view умеет только
  offset. Остальной JS (лайтбокс, тема, анимации) без изменений.
- `gallery/views.py` — в `serialize_photo` возвращаются реальные
  `title`+`alt_text` (вместо `str(photo)`), чтобы у догруженных карточек не
  всплывали имена файлов вместо подписей. Единственная правка бэкенда,
  совместимая с Python 3.6 / Django 3.2.

`index.html` и `upload.html` взяты из `main` без изменений (несуществующие
SEO-переменные тихо отрендерятся пустыми, `page_heading|default` покрывает
отсутствие контекста).

## Как задеплоено

Файлы залиты в `public_html/{gallery/views.py, gallery/templates, static/…}`
и продублированы в `public_html/staticfiles/` (на сервере не задан
`STATICFILES_DIRS`, `collectstatic` для проектных ассетов не работает —
`.htaccess` отдаёт `/static/` напрямую из `staticfiles/`). После заливки —
`touch public_html/wsgi.py` для перезагрузки mod_wsgi.

Полный CSS (`static/css/styles.css`) и статические ассеты идентичны `main`
(`static/css/styles.css`, `static/icon/*`, `static/site.webmanifest`) — здесь
не дублируются, берутся из корня репозитория.

## Откат

На сервере есть бэкап до деплоя:
`~/backup-frontend-<timestamp>.tgz` (templates + views.py + static +
staticfiles). Откат: распаковать его в `public_html` и `touch wsgi.py`.
