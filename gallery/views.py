import json
import logging

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.core.validators import FileExtensionValidator
from django.db import connections, transaction
from django.db.models import Q
from django.db.utils import DatabaseError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET, require_POST

from .models import Photo
from .seo import (
    build_gallery_structured_data,
    build_seo_context,
    get_primary_photo_file,
    get_primary_photo_url,
)
from .services import (
    ALLOWED_IMAGE_EXTENSIONS,
    DuplicatePhotoError,
    ImageProcessingError,
    save_uploaded_photo,
)
from .validators import validate_file_size, validate_image_type

logger = logging.getLogger(__name__)
NOINDEX_ROBOTS = "noindex, nofollow, noarchive"
FEED_PAGE_SIZE = 12
MAX_JSON_PAGE_SIZE = 200


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        # Диалог выбора файлов сразу фильтрует по допустимым форматам
        super().__init__({"accept": "image/jpeg,image/png,image/webp", **(attrs or {})})


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if not data:
            if self.required:
                raise ValidationError(self.error_messages["required"], code="required")
            return []
        if isinstance(data, list | tuple):
            result = [single_file_clean(d, initial) for d in data]
            return result
        return [single_file_clean(data, initial)]


class PhotoUploadForm(forms.Form):
    files = MultipleFileField(
        label="Выберите файлы",
        required=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
                message="Недопустимое расширение файла. Разрешены: %(allowed_extensions)s",
            ),
            validate_file_size,
            validate_image_type,
        ],
    )


def is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def serialize_photo(photo):
    display_image = photo.display_file
    full_image = photo.optimized_image or photo.image

    if not full_image:
        return None

    try:
        full_url = full_image.url
    except ValueError:
        return None

    try:
        preview_url = display_image.url if display_image else full_url
    except ValueError:
        preview_url = full_url

    width, height = photo.display_dimensions

    return {
        "id": photo.id,
        "position": photo.position,
        "url": preview_url,
        "full_url": full_url,
        "medium_url": photo.medium_url,
        "alt_text": photo.display_label,
        "width": width,
        "height": height,
    }


def serialize_photos(photos):
    return [data for data in map(serialize_photo, photos) if data]


def with_x_robots_tag(response, value):
    response["X-Robots-Tag"] = value
    return response


def build_index_context(request, photos_page):
    photos = list(photos_page.object_list)
    total_count = photos_page.paginator.count
    gallery_title = "Фотогалерея Тимура Герузова"
    gallery_description = (
        "Авторская онлайн-фотогалерея Тимура Герузова с полноэкранным просмотром, "
        "быстрой загрузкой и тщательно подготовленными изображениями."
    )
    if total_count:
        gallery_description = (
            f"{gallery_description} В коллекции уже опубликовано {total_count} снимков."
        )

    featured_photo = next(
        (photo for photo in photos if get_primary_photo_url(request, photo)), None
    )
    featured_image_url = get_primary_photo_url(request, featured_photo) if featured_photo else None
    featured_image_alt = featured_photo.display_label if featured_photo else None
    featured_width = featured_height = None
    if featured_photo:
        featured_width, featured_height = featured_photo.file_dimensions(
            get_primary_photo_file(featured_photo)
        )

    # Canonical собирается из номера страницы, а не из запроса: ?page=abc,
    # ?page=1 и метки вроде utm_source не плодят копии главной.
    canonical_path = reverse("index")
    if photos_page.number > 1:
        canonical_path += f"?page={photos_page.number}"

    context = {
        "photos_page": photos_page,
        # Hero-баннер на главной убран - заголовок остаётся скрытым <h1>
        # (page_heading) ради валидного outline документа и SEO.
        "page_heading": gallery_title,
        "seo_structured_data": build_gallery_structured_data(
            request,
            photos,
            title=gallery_title,
            description=gallery_description,
            canonical_path=canonical_path,
        ),
    }
    context.update(
        build_seo_context(
            request,
            title=gallery_title,
            description=gallery_description,
            canonical_path=canonical_path,
            image_url=featured_image_url,
            image_alt=featured_image_alt,
            image_width=featured_width,
            image_height=featured_height,
        )
    )
    return context


def build_manage_context(request, *, section, title):
    """Общее для разделов управления: вкладки, счётчик фото, noindex."""
    context = {
        "page_heading": title,
        "manage_section": section,
        "manage_photo_count": Photo.objects.count(),
    }
    context.update(
        build_seo_context(
            request,
            title=f"{title} - Управление",
            description="Служебная закрытая страница для управления галереей.",
            robots=NOINDEX_ROBOTS,
            canonical_path=request.path,
        )
    )
    return context


def build_upload_context(request, form):
    context = build_manage_context(request, section="upload", title="Загрузка")
    context.update({"form": form, "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB})
    return context


def render_upload_page(request, form, *, status=200):
    response = render(
        request, "gallery/upload.html", build_upload_context(request, form), status=status
    )
    return with_x_robots_tag(response, NOINDEX_ROBOTS)


def resolve_feed_cursor(after, after_pos):
    """Позиция курсора (position, id) или None, если её не восстановить.

    Позиция берётся из запроса: курсор не ломается, если фото, от которого
    листали, успели удалить. Поиск по pk - фолбэк для старых клиентов.
    """
    try:
        cursor_id = int(after)
    except (TypeError, ValueError):
        return None

    try:
        return int(after_pos), cursor_id
    except (TypeError, ValueError):
        pass

    cursor = Photo.objects.filter(pk=cursor_id).values_list("position", flat=True).first()
    return (cursor, cursor_id) if cursor is not None else None


def feed_after_response(request, photos_list, after, after_pos=None):
    """Keyset-пагинация ленты по (position, id) вместо OFFSET."""
    cursor = resolve_feed_cursor(after, after_pos)
    if cursor is None:
        return with_x_robots_tag(
            JsonResponse({"photos": [], "has_next": False}),
            NOINDEX_ROBOTS,
        )
    cursor_pos, cursor_id = cursor

    window = list(
        photos_list.filter(Q(position__gt=cursor_pos) | Q(position=cursor_pos, id__lt=cursor_id))[
            : FEED_PAGE_SIZE + 1
        ]
    )
    has_next = len(window) > FEED_PAGE_SIZE
    return with_x_robots_tag(
        JsonResponse({"photos": serialize_photos(window[:FEED_PAGE_SIZE]), "has_next": has_next}),
        NOINDEX_ROBOTS,
    )


def index(request):
    # Явный tie-break по id - обязателен для корректного keyset-курсора
    photos_list = Photo.objects.all().order_by("position", "-id")

    if is_ajax(request) and request.GET.get("after") is not None:
        return feed_after_response(
            request, photos_list, request.GET.get("after"), request.GET.get("after_pos")
        )

    paginator = Paginator(photos_list, FEED_PAGE_SIZE)
    page_number = request.GET.get("page", 1)

    try:
        photos_page = paginator.page(page_number)
    except PageNotAnInteger:
        photos_page = paginator.page(1)
    except EmptyPage:
        if is_ajax(request):
            return with_x_robots_tag(
                JsonResponse({"photos": [], "has_next": False}),
                NOINDEX_ROBOTS,
            )
        # Молчаливая отдача последней страницы плодила бесконечные
        # URL-дубликаты со статусом 200 для краулеров.
        raise Http404("Страница вне диапазона") from None

    if is_ajax(request):
        return with_x_robots_tag(
            JsonResponse(
                {
                    "photos": serialize_photos(photos_page),
                    "has_next": photos_page.has_next(),
                    "page": photos_page.number,
                }
            ),
            NOINDEX_ROBOTS,
        )

    return render(request, "gallery/index.html", build_index_context(request, photos_page))


@staff_member_required
def upload_photo(request):
    form = PhotoUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if not form.is_valid():
            validation_errors = {
                field: [str(error) for error in errs] for field, errs in form.errors.items()
            }
            if is_ajax(request):
                # errors - плоский список причин: его показывает страница загрузки
                return with_x_robots_tag(
                    JsonResponse(
                        {
                            "success": False,
                            "error": "Ошибки валидации",
                            "errors": [msg for msgs in validation_errors.values() for msg in msgs],
                            "details": validation_errors,
                        },
                        status=400,
                    ),
                    NOINDEX_ROBOTS,
                )
            # Без дублирующего message - детали уже выводит form.errors
            return render_upload_page(request, form, status=400)

        files = form.cleaned_data.get("files", [])
        uploaded_count = 0
        errors = []
        duplicates = []

        for file in files:
            try:
                save_uploaded_photo(file)
                uploaded_count += 1
            except DuplicatePhotoError as exc:
                logger.info("Пропущен дубликат %s: %s", file.name, exc)
                duplicates.append(f"{file.name}: {exc}")
            except ImageProcessingError as exc:
                logger.warning("Ошибка обработки %s: %s", file.name, exc)
                errors.append(f"{file.name}: {exc}")
            except Exception as exc:
                logger.exception("Непредвиденная ошибка обработки %s: %s", file.name, exc)
                errors.append(f"{file.name}: внутренняя ошибка обработки")

        if uploaded_count == 0 and errors:
            if is_ajax(request):
                return with_x_robots_tag(
                    JsonResponse(
                        {
                            "success": False,
                            "error": "Не удалось загрузить ни одного файла",
                            "errors": errors,
                            "duplicates": duplicates,
                        },
                        status=400,
                    ),
                    NOINDEX_ROBOTS,
                )
            messages.error(request, "Не удалось загрузить ни одного фото.")
            for error in errors:
                messages.error(request, error)
            return render_upload_page(request, form, status=400)

        msg = f"Загружено {uploaded_count} фото" if uploaded_count else "Новых фото нет"
        if duplicates:
            msg += f" (пропущено дубликатов: {len(duplicates)})"
        if errors:
            msg += f" (с ошибками: {len(errors)})"

        if is_ajax(request):
            return with_x_robots_tag(
                JsonResponse(
                    {
                        "success": True,
                        "redirect_url": reverse("index"),
                        "message": msg,
                        "errors": errors,
                        "duplicates": duplicates,
                    }
                ),
                NOINDEX_ROBOTS,
            )

        if errors:
            messages.warning(request, msg)
            for error in errors:
                messages.warning(request, error)
        else:
            messages.success(request, msg)
        for duplicate in duplicates:
            messages.info(request, duplicate)
        return redirect(reverse("index"))

    return render_upload_page(request, form)


@require_GET
@cache_page(60)
def all_photos_json(request):
    # tie-break по id: без него фото с одинаковой позицией прыгают между страницами
    photos = Photo.objects.all().order_by("position", "-id")
    max_page_size = MAX_JSON_PAGE_SIZE

    try:
        page_size = int(request.GET.get("page_size", max_page_size))
    except (TypeError, ValueError):
        page_size = max_page_size
    page_size = max(1, min(page_size, max_page_size))

    paginator = Paginator(photos, page_size)
    page_number = request.GET.get("page", 1)

    try:
        photos_page = paginator.page(page_number)
    except PageNotAnInteger:
        photos_page = paginator.page(1)
    except EmptyPage:
        return with_x_robots_tag(
            JsonResponse(
                {
                    "photos": [],
                    "page": paginator.num_pages if paginator.num_pages else 1,
                    "page_size": page_size,
                    "has_next": False,
                    "total": paginator.count,
                }
            ),
            NOINDEX_ROBOTS,
        )

    return with_x_robots_tag(
        JsonResponse(
            {
                "photos": serialize_photos(photos_page),
                "page": photos_page.number,
                "page_size": page_size,
                "has_next": photos_page.has_next(),
                "total": paginator.count,
            }
        ),
        NOINDEX_ROBOTS,
    )


@staff_member_required
def manage(request):
    return redirect("manage_photos")


@staff_member_required
def manage_photos(request):
    context = build_manage_context(request, section="photos", title="Фото")
    context["photos"] = Photo.objects.order_by("position", "-id")
    response = render(request, "gallery/manage_photos.html", context)
    return with_x_robots_tag(response, NOINDEX_ROBOTS)


def read_photo_ids(request):
    """Список id из JSON-тела {"ids": [...]} или None, если он некорректен."""
    try:
        ids = json.loads(request.body).get("ids")
    except (ValueError, AttributeError):
        return None
    if not isinstance(ids, list) or not all(
        isinstance(pk, int) and not isinstance(pk, bool) for pk in ids
    ):
        return None
    if len(set(ids)) != len(ids):
        return None
    return ids


def bad_ids_response():
    return JsonResponse({"success": False, "error": "Некорректный список фото"}, status=400)


@staff_member_required
@require_POST
def manage_reorder(request):
    """Сохраняет порядок: позиции 0..n-1 в порядке переданных id.

    Фото, которых нет в списке (загружены в другой вкладке, пока открыт
    раздел), сохраняют свои позиции: у новых они отрицательные, то есть выше всех.
    """
    ids = read_photo_ids(request)
    if ids is None:
        return bad_ids_response()
    with transaction.atomic():
        existing = set(Photo.objects.filter(id__in=ids).values_list("id", flat=True))
        photos = [Photo(id=pk, position=index) for index, pk in enumerate(ids) if pk in existing]
        Photo.objects.bulk_update(photos, ["position"])
    return with_x_robots_tag(JsonResponse({"success": True, "saved": len(photos)}), NOINDEX_ROBOTS)


@staff_member_required
@require_POST
def manage_delete(request):
    """Удаляет фото вместе с файлами: их убирает django-cleanup после коммита."""
    ids = read_photo_ids(request)
    if ids is None or not ids:
        return bad_ids_response()
    _, per_model = Photo.objects.filter(id__in=ids).delete()
    deleted = per_model.get(Photo._meta.label, 0)
    logger.info("Удалено фото: %s", deleted)
    return with_x_robots_tag(
        JsonResponse({"success": True, "deleted": deleted, "total": Photo.objects.count()}),
        NOINDEX_ROBOTS,
    )


@require_GET
def healthz(request):
    """Проверка живости для контейнерных healthcheck-ов: приложение + БД."""
    # Настоящий запрос: на переиспользованном соединении (CONN_MAX_AGE)
    # одно открытие курсора до базы не доходит и не заметит её падения.
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return with_x_robots_tag(JsonResponse({"status": "error"}, status=503), NOINDEX_ROBOTS)
    return with_x_robots_tag(JsonResponse({"status": "ok"}), NOINDEX_ROBOTS)


@require_GET
@cache_page(60)
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /upload/",
        "Disallow: /manage/",
        "Disallow: /all_photos.json",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
