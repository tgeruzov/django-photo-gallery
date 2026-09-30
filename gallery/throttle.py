"""Ограничение попыток входа в админку без сторонних пакетов.

Неудачные попытки считаются в кэше по паре логин + IP. За nginx у всех один
REMOTE_ADDR, и счётчик фактически идёт по логину: подбор пароля к admin
останавливается, хотя злоумышленник может ненадолго закрыть вход и владельцу.
Кэш по умолчанию живёт в памяти процесса, так что у каждого воркера Gunicorn
свой счётчик: это замедляет перебор, а не запрещает его полностью.
"""

import hashlib
from functools import wraps

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.core.cache import cache
from django.dispatch import receiver
from django.http import HttpResponse

LOGIN_ATTEMPTS_LIMIT = 5
LOGIN_BLOCK_SECONDS = 15 * 60


def attempts_key(request, username):
    raw = f"{(username or '').strip().lower()}|{request.META.get('REMOTE_ADDR', '')}"
    return "login-failures:" + hashlib.sha256(raw.encode()).hexdigest()


@receiver(user_login_failed)
def count_failed_login(sender, credentials, request=None, **kwargs):
    if request is None:
        return
    key = attempts_key(request, credentials.get("username"))
    cache.add(key, 0, LOGIN_BLOCK_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        # Ключ успел истечь между add и incr
        cache.set(key, 1, LOGIN_BLOCK_SECONDS)


@receiver(user_logged_in)
def reset_failed_logins(sender, request, user, **kwargs):
    if request is not None:
        cache.delete(attempts_key(request, user.get_username()))


def throttled_login(login_view):
    @wraps(login_view)
    def wrapper(request, *args, **kwargs):
        if request.method == "POST":
            key = attempts_key(request, request.POST.get("username"))
            if cache.get(key, 0) >= LOGIN_ATTEMPTS_LIMIT:
                return HttpResponse(
                    "Слишком много неудачных попыток входа. Попробуйте через 15 минут.",
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )
        return login_view(request, *args, **kwargs)

    return wrapper
