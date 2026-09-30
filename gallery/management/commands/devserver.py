"""runserver для разработки, который сам применяет миграции.

Обычный runserver подхватывает новый код без перезапуска контейнера, а
миграции применяются только при старте: после обновления код обращается к
новым полям, которых в базе ещё нет. Эта команда применяет недостающие
миграции перед каждым запуском и перезапуском сервера, а перед запросом
сверяет файлы migrations/ проекта: новый файл миграции перезапуска не
вызывает, его автоперезагрузчик Django не замечает.
"""

import threading
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunserverCommand,
)
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor


def project_migration_dirs():
    base_dir = Path(settings.BASE_DIR).resolve()
    for app_config in apps.get_app_configs():
        migrations_dir = Path(app_config.path).resolve() / "migrations"
        if migrations_dir.is_dir() and base_dir in migrations_dir.parents:
            yield migrations_dir


def migrations_fingerprint():
    """Имена и время изменения файлов миграций: дешёво, можно на каждый запрос."""
    return tuple(
        sorted(
            (str(path), path.stat().st_mtime_ns)
            for migrations_dir in project_migration_dirs()
            for path in migrations_dir.glob("*.py")
        )
    )


def pending_migrations():
    executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


class Command(RunserverCommand):
    help = "Сервер разработки, который сам применяет новые миграции."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fingerprint = None
        self.migrate_lock = threading.Lock()

    def inner_run(self, *args, **options):
        self.apply_migrations()
        super().inner_run(*args, **options)

    def get_handler(self, *args, **options):
        handler = super().get_handler(*args, **options)

        def application(environ, start_response):
            self.apply_migrations_if_changed()
            return handler(environ, start_response)

        return application

    def apply_migrations_if_changed(self):
        if migrations_fingerprint() != self.fingerprint:
            self.apply_migrations()

    def apply_migrations(self):
        # runserver многопоточный: миграции применяет один запрос, остальные ждут
        with self.migrate_lock:
            fingerprint = migrations_fingerprint()
            if fingerprint == self.fingerprint:
                return
            try:
                if pending_migrations():
                    call_command("migrate", interactive=False)
                self.fingerprint = fingerprint
            except Exception as exc:
                # Сломанная миграция не роняет сервер: ошибка видна в логе,
                # а после исправления файла следующий запрос попробует снова
                self.stderr.write(f"Миграции не применились: {exc}")
            finally:
                # Запрос идёт в своём потоке: соединение миграций не должно висеть
                connections.close_all()
