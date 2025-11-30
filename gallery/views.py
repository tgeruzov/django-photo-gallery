from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
import logging
import os
from io import BytesIO
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files.base import ContentFile
from PIL import Image
from .forms import PhotoUploadForm
from .models import Photo

logger = logging.getLogger(__name__)

# Бывает глючит на айфонах, потом разберусь
AJAX_HEADER = 'HTTP_X_REQUESTED_WITH'
AJAX_VALUE = 'XMLHttpRequest'

def is_ajax(request):
    return request.META.get(AJAX_HEADER) == AJAX_VALUE

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
            photos_data.append({
                'url': photo.thumbnail.url if photo.thumbnail else photo.image.url,
                'full_url': photo.image.url,
                'title': str(photo)
            })
        return JsonResponse({
            'photos': photos_data,
            'has_next': photos_page.has_next()
        })

    return render(request, 'gallery/index.html', {'photos_page': photos_page})

def save_optimized_and_thumbnail(uploaded_file):
    """
    Сохраняет оригинал, оптимизированную копию и миниатюру
    TODO: иногда падает на больших PNG, нужно фиксить
    """
    original = Photo()
    original.image.save(uploaded_file.name, uploaded_file)
    original.save()

    uploaded_file.seek(0)
    img = Image.open(uploaded_file).convert('RGB')

    def make_webp(img_source, size, quality, suffix):
        img_copy = img_source.copy()
        img_copy.thumbnail(size, Image.LANCZOS)
        buffer = BytesIO()
        base, _ = os.path.splitext(uploaded_file.name)
        name = f"{base}{suffix}.webp"
        img_copy.save(buffer, format='WEBP', quality=quality, method=6)
        return ContentFile(buffer.getvalue(), name=name)

    # Оптимизированная версия
    opt_content = make_webp(img, (2560, 2560), 95, '_optimized')
    
    # Миниатюра
    thumb_content = make_webp(img, (800, 800), 95, '_thumb')

    original.image.save(opt_content.name, opt_content)
    original.thumbnail.save(thumb_content.name, thumb_content)
    original.save()
    return original

@staff_member_required
def upload_photo(request):
    if request.method == 'POST':
        form = PhotoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('files')
            uploaded_count = 0
            errors = []

            for file in files:
                try:
                    save_optimized_and_thumbnail(file)
                    uploaded_count += 1
                except Exception as e:
                    logger.error(f"Ошибка обработки {file.name}: {e}")
                    errors.append(f"{file.name}: {e}")
                    continue

            msg = f'Загружено {uploaded_count} фото'
            if errors:
                msg += f" (с ошибками: {len(errors)})"

            if is_ajax(request):
                return JsonResponse({
                    'success': True,
                    'redirect_url': reverse('index'),
                    'message': msg,
                    'errors': errors
                })

            if uploaded_count > 0:
                request.session['upload_message'] = msg
            return redirect(reverse('index'))

        errors = {field: [str(e) for e in errs] for field, errs in form.errors.items()}
        if is_ajax(request):
            return JsonResponse({
                'success': False,
                'error': 'Ошибки валидации',
                'details': errors
            })

    form = PhotoUploadForm()
    return render(request, 'gallery/upload.html', {'form': form})

@require_GET
def all_photos_json(request):
    photos = Photo.objects.all().order_by('-uploaded_at')
    data = []
    for photo in photos:
        data.append({
            'id': photo.id,
            'url': photo.thumbnail.url if photo.thumbnail else photo.image.url,
            'full_url': photo.image.url,
            'title': str(photo)
        })
    return JsonResponse({'photos': data})