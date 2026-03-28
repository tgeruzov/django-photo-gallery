import logging

from django.contrib import messages
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET

from .forms import PhotoUploadForm
from .models import Photo
from .constants import AJAX_HEADER, AJAX_VALUE
from .image_utils import ImageProcessingError
from .services import save_uploaded_photo

logger = logging.getLogger(__name__)

def is_ajax(request):
    return request.META.get(AJAX_HEADER) == AJAX_VALUE or request.headers.get('X-Requested-With') == AJAX_VALUE


def serialize_photo(photo):
    display_image = photo.thumbnail or photo.optimized_image or photo.image
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

    width = None
    height = None
    if display_image:
        try:
            width = display_image.width
            height = display_image.height
        except (ValueError, FileNotFoundError, OSError):
            width = None
            height = None

    return {
        'id': photo.id,
        'url': preview_url,
        'full_url': full_url,
        'title': str(photo),
        'width': width,
        'height': height,
    }

def index(request):
    photos_list = Photo.objects.all().order_by('-uploaded_at')
    paginator = Paginator(photos_list, 12)
    page_number = request.GET.get('page', 1)

    try:
        photos_page = paginator.page(page_number)
    except PageNotAnInteger:
        photos_page = paginator.page(1)
    except EmptyPage:
        if is_ajax(request):
            return JsonResponse({'photos': [], 'has_next': False})
        photos_page = paginator.page(paginator.num_pages)

    if is_ajax(request):
        photos_data = []
        for photo in photos_page:
            serialized = serialize_photo(photo)
            if serialized:
                photos_data.append(serialized)
        return JsonResponse({
            'photos': photos_data,
            'has_next': photos_page.has_next(),
            'page': photos_page.number,
        })

    return render(request, 'gallery/index.html', {'photos_page': photos_page})

@staff_member_required
def upload_photo(request):
    form = PhotoUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if not form.is_valid():
            validation_errors = {field: [str(error) for error in errs] for field, errs in form.errors.items()}
            if is_ajax(request):
                return JsonResponse({
                    'success': False,
                    'error': 'Ошибки валидации',
                    'details': validation_errors,
                }, status=400)
            messages.error(request, 'Исправьте ошибки формы и попробуйте снова.')
            return render(request, 'gallery/upload.html', {'form': form}, status=400)

        files = form.cleaned_data.get('files', [])
        uploaded_count = 0
        errors = []

        for file in files:
            try:
                save_uploaded_photo(file)
                uploaded_count += 1
            except ImageProcessingError as exc:
                logger.warning("Ошибка обработки %s: %s", file.name, exc)
                errors.append(f"{file.name}: {exc}")
            except Exception as exc:
                logger.exception("Непредвиденная ошибка обработки %s: %s", file.name, exc)
                errors.append(f"{file.name}: внутренняя ошибка обработки")

        if uploaded_count == 0:
            if is_ajax(request):
                return JsonResponse({
                    'success': False,
                    'error': 'Не удалось загрузить ни одного файла',
                    'errors': errors,
                }, status=400)
            messages.error(request, 'Не удалось загрузить ни одного фото.')
            for error in errors:
                messages.error(request, error)
            return render(request, 'gallery/upload.html', {'form': PhotoUploadForm()}, status=400)

        msg = f'Загружено {uploaded_count} фото'
        if errors:
            msg += f" (с ошибками: {len(errors)})"

        if is_ajax(request):
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('index'),
                'message': msg,
                'errors': errors,
            })

        if errors:
            messages.warning(request, msg)
            for error in errors:
                messages.warning(request, error)
        else:
            messages.success(request, msg)
        return redirect(reverse('index'))

    return render(request, 'gallery/upload.html', {'form': form})

@require_GET
def all_photos_json(request):
    photos = Photo.objects.all().order_by('-uploaded_at')
    max_page_size = max(1, int(getattr(settings, 'MAX_JSON_PAGE_SIZE', 200)))

    try:
        page_size = int(request.GET.get('page_size', max_page_size))
    except (TypeError, ValueError):
        page_size = max_page_size
    page_size = max(1, min(page_size, max_page_size))

    paginator = Paginator(photos, page_size)
    page_number = request.GET.get('page', 1)

    try:
        photos_page = paginator.page(page_number)
    except PageNotAnInteger:
        photos_page = paginator.page(1)
    except EmptyPage:
        return JsonResponse({
            'photos': [],
            'page': paginator.num_pages if paginator.num_pages else 1,
            'page_size': page_size,
            'has_next': False,
            'total': paginator.count,
        })

    data = []
    for photo in photos_page:
        serialized = serialize_photo(photo)
        if serialized:
            data.append(serialized)

    return JsonResponse({
        'photos': data,
        'page': photos_page.number,
        'page_size': page_size,
        'has_next': photos_page.has_next(),
        'total': paginator.count,
    })
