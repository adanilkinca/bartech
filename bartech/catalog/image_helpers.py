from django.conf import settings


FALLBACK_PUBLIC_ID = 'no-photo-master'


def display_image_url(image_field):
    """Return an assigned image URL, or the configured Cloudinary fallback."""
    if image_field:
        return image_field.url
    if getattr(settings, 'CLOUDINARY_STORAGE', None):
        return image_field.storage.url(FALLBACK_PUBLIC_ID)
    return None