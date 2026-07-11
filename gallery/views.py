import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import connections
from django.db.utils import OperationalError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .constants import AJAX_HEADER, AJAX_VALUE
from .forms import PhotoUploadForm
from .image_utils import ImageProcessingError
from .models import Photo
from .seo import (
    build_gallery_structured_data,
    build_seo_context,
    get_photo_label,
    get_primary_photo_url,
)
from .services import DuplicatePhotoError, save_uploaded_photo

logger = logging.getLogger(__name__)
NOINDEX_ROBOTS = "noindex, nofollow, noarchive"


def is_ajax(request):
    return (
        request.META.get(AJAX_HEADER) == AJAX_VALUE
        or request.headers.get("X-Requested-With") == AJAX_VALUE
    )


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
        "url": preview_url,
        "full_url": full_url,
        "title": photo.title or get_photo_label(photo),
        "alt_text": get_photo_label(photo),
        "width": width,
        "height": height,
    }


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

    context = {
        "photos_page": photos_page,
        "hero_title": gallery_title,
        "hero_description": (
            "Авторская коллекция travel, urban и lifestyle-снимков с акцентом на "
            "чистую подачу и удобный полноэкранный просмотр."
        ),
        "seo_structured_data": build_gallery_structured_data(
            request,
            photos,
            title=gallery_title,
            description=gallery_description,
        ),
    }
    context.update(
        build_seo_context(
            request,
            title=gallery_title,
            description=gallery_description,
            image_url=featured_image_url,
            image_alt=get_photo_label(featured_photo) if featured_photo else None,
        )
    )
    return context


def build_upload_context(request, form):
    context = {
        "form": form,
        "hero_title": "Загрузка фотографий",
        "hero_description": "Закрытая страница для пакетной публикации новых снимков в галерею.",
    }
    context.update(
        build_seo_context(
            request,
            title="Загрузка фотографий",
            description="Служебная закрытая страница для управления публикацией фотографий.",
            robots=NOINDEX_ROBOTS,
            canonical_path=reverse("upload_photo"),
        )
    )
    return context


def render_upload_page(request, form, *, status=200):
    response = render(
        request, "gallery/upload.html", build_upload_context(request, form), status=status
    )
    return with_x_robots_tag(response, NOINDEX_ROBOTS)


def index(request):
    photos_list = Photo.objects.all().order_by("-uploaded_at")
    paginator = Paginator(photos_list, 12)
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
        photos_page = paginator.page(paginator.num_pages)

    if is_ajax(request):
        photos_data = []
        for photo in photos_page:
            serialized = serialize_photo(photo)
            if serialized:
                photos_data.append(serialized)
        return with_x_robots_tag(
            JsonResponse(
                {
                    "photos": photos_data,
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
                return with_x_robots_tag(
                    JsonResponse(
                        {
                            "success": False,
                            "error": "Ошибки валидации",
                            "details": validation_errors,
                        },
                        status=400,
                    ),
                    NOINDEX_ROBOTS,
                )
            messages.error(request, "Исправьте ошибки формы и попробуйте снова.")
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

        if uploaded_count:
            msg = f"Загружено {uploaded_count} фото"
        else:
            msg = "Новых фото нет"
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
def all_photos_json(request):
    photos = Photo.objects.all().order_by("-uploaded_at")
    max_page_size = max(1, int(getattr(settings, "MAX_JSON_PAGE_SIZE", 200)))

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

    data = []
    for photo in photos_page:
        serialized = serialize_photo(photo)
        if serialized:
            data.append(serialized)

    return with_x_robots_tag(
        JsonResponse(
            {
                "photos": data,
                "page": photos_page.number,
                "page_size": page_size,
                "has_next": photos_page.has_next(),
                "total": paginator.count,
            }
        ),
        NOINDEX_ROBOTS,
    )


@require_GET
def healthz(request):
    """Проверка живости для контейнерных healthcheck-ов: приложение + БД."""
    try:
        connections["default"].cursor()
    except OperationalError:
        return with_x_robots_tag(JsonResponse({"status": "error"}, status=503), NOINDEX_ROBOTS)
    return with_x_robots_tag(JsonResponse({"status": "ok"}), NOINDEX_ROBOTS)


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /upload/",
        "Disallow: /all_photos.json",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
