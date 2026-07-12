import contextlib
import json
import mimetypes

from django.conf import settings

# Python < 3.13 не знает webp из коробки
mimetypes.add_type("image/webp", ".webp")


def get_site_name():
    return getattr(settings, "SITE_NAME", "Timur Geruzov")


def get_default_meta_description():
    return getattr(
        settings,
        "DEFAULT_META_DESCRIPTION",
        (
            "Авторская фотогалерея Тимура Герузова с полноэкранным просмотром, "
            "оптимизированной загрузкой и акцентом на визуальную подачу."
        ),
    )


def get_site_locale():
    return getattr(settings, "SITE_LOCALE", "ru_RU")


def build_absolute_url(request, path=None):
    # Без path сохраняем query string (?page=N): страницы пагинации
    # объявляют self-canonical, а не копию главной (SE1).
    if path:
        return request.build_absolute_uri(path)
    return request.build_absolute_uri()


def get_primary_photo_file(photo):
    return photo.optimized_image or photo.image or photo.thumbnail


def get_primary_photo_url(request, photo):
    image = get_primary_photo_file(photo)
    if not image:
        return None
    try:
        return request.build_absolute_uri(image.url)
    except ValueError:
        return None


def build_seo_context(
    request,
    *,
    title=None,
    description=None,
    robots="index,follow,max-image-preview:large",
    canonical_path=None,
    image_url=None,
    image_alt=None,
    image_width=None,
    image_height=None,
    og_type="website",
):
    site_name = get_site_name()
    clean_title = (title or site_name).strip()
    seo_title = site_name if clean_title == site_name else f"{clean_title} | {site_name}"

    return {
        "seo_title": seo_title,
        "seo_description": (description or get_default_meta_description()).strip(),
        "seo_canonical_url": build_absolute_url(request, canonical_path),
        "seo_robots": robots,
        "seo_site_name": site_name,
        "seo_locale": get_site_locale(),
        "seo_og_type": og_type,
        "seo_twitter_card": "summary_large_image" if image_url else "summary",
        "seo_image_url": image_url,
        "seo_image_alt": image_alt,
        "seo_image_width": image_width,
        "seo_image_height": image_height,
        "seo_image_type": mimetypes.guess_type(image_url)[0] if image_url else None,
    }


def build_gallery_structured_data(request, photos, *, title, description):
    graph = [
        {
            "@type": "WebSite",
            "@id": f"{build_absolute_url(request)}#website",
            "name": get_site_name(),
            "url": build_absolute_url(request),
            "inLanguage": "ru",
            "description": description,
        }
    ]

    image_objects = []
    for photo in photos:
        image_url = get_primary_photo_url(request, photo)
        if not image_url:
            continue

        image_object = {
            "@type": "ImageObject",
            "contentUrl": image_url,
            "name": photo.title or photo.display_label,
            "description": photo.display_label,
        }

        image_file = get_primary_photo_file(photo)
        width, height = photo.file_dimensions(image_file)
        if width and height:
            image_object["width"] = width
            image_object["height"] = height

        # SE3: авторство и лицензирование — «паспорт» фото для Google Images
        site_name = get_site_name()
        image_object.update(
            {
                "creator": {"@type": "Person", "name": site_name},
                "copyrightNotice": f"© {site_name}",
                "creditText": site_name,
            }
        )
        if photo.thumbnail:
            with contextlib.suppress(ValueError):
                image_object["thumbnailUrl"] = request.build_absolute_uri(photo.thumbnail.url)

        image_objects.append(image_object)

    if image_objects:
        graph.append(
            {
                "@type": "ImageGallery",
                "@id": f"{build_absolute_url(request)}#gallery",
                "name": title,
                "url": build_absolute_url(request),
                "description": description,
                "image": image_objects,
            }
        )

    payload = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": graph,
        },
        ensure_ascii=False,
    )
    # json.dumps не экранирует "</" — без замены строка "</script>" в title/alt_text
    # закрыла бы JSON-LD-блок и исполнилась как HTML (stored XSS).
    return payload.replace("</", "<\\/")
