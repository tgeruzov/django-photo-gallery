import json

from django.conf import settings


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
    return request.build_absolute_uri(path or request.path)


def get_photo_label(photo):
    return photo.alt_text or photo.title or (f"Фотография {photo.pk}" if photo.pk else "Фотография")


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
    og_type="website",
):
    site_name = get_site_name()
    clean_title = (title or site_name).strip()
    if clean_title == site_name:
        seo_title = site_name
    else:
        seo_title = f"{clean_title} | {site_name}"

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
            "name": photo.title or get_photo_label(photo),
            "description": get_photo_label(photo),
        }

        image_file = get_primary_photo_file(photo)
        try:
            image_object["width"] = image_file.width
            image_object["height"] = image_file.height
        except (AttributeError, FileNotFoundError, OSError, ValueError):
            pass

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

    return json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": graph,
        },
        ensure_ascii=False,
    )
