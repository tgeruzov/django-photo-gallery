param(
    [string]$DumpFile = "data_dump.json",
    [switch]$Docker
)

$ErrorActionPreference = "Stop"

if (!(Test-Path "db.sqlite3")) {
    Write-Error "Файл db.sqlite3 не найден. Нечего переносить."
    exit 1
}

if ($Docker) {
    Write-Host "Запуск PostgreSQL (Docker)..."
    docker compose up -d db | Out-Null

    Write-Host "Дамп данных из SQLite в $DumpFile (Docker)..."
    docker compose run --rm `
        -e DB_ENGINE=sqlite3 `
        -e DB_NAME= `
        -e DB_USER= `
        -e DB_PASSWORD= `
        -e DB_HOST= `
        -e DB_PORT= `
        web python manage.py migrate | Out-Null
    docker compose run --rm `
        -e DB_ENGINE=sqlite3 `
        -e DB_NAME= `
        -e DB_USER= `
        -e DB_PASSWORD= `
        -e DB_HOST= `
        -e DB_PORT= `
        web python manage.py dumpdata --exclude contenttypes --exclude auth.permission --indent 2 --output $DumpFile | Out-Null

    Write-Host "Загрузка данных в PostgreSQL (Docker)..."
    docker compose run --rm web python manage.py migrate | Out-Null
    docker compose run --rm web python manage.py loaddata $DumpFile

    Write-Host "Готово."
    exit 0
}

Write-Host "Дамп данных из SQLite в $DumpFile (локально)..."
$env:DB_NAME = ""
$env:DB_USER = ""
$env:DB_PASSWORD = ""
$env:DB_HOST = ""
$env:DB_PORT = ""
$env:DB_ENGINE = "sqlite3"

python manage.py migrate | Out-Null
python manage.py dumpdata --exclude contenttypes --exclude auth.permission --indent 2 --output $DumpFile

Write-Host "Загрузка данных в PostgreSQL (локально)..."
Remove-Item Env:DB_NAME -ErrorAction SilentlyContinue
Remove-Item Env:DB_USER -ErrorAction SilentlyContinue
Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:DB_HOST -ErrorAction SilentlyContinue
Remove-Item Env:DB_PORT -ErrorAction SilentlyContinue
Remove-Item Env:DB_ENGINE -ErrorAction SilentlyContinue

python manage.py migrate | Out-Null
python manage.py loaddata $DumpFile

Write-Host "Готово."
