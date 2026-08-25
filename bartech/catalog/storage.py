import time

import cloudinary
import cloudinary.api
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.conf import settings


class VersionedMediaCloudinaryStorage(MediaCloudinaryStorage):
    """Deliver current Cloudinary asset versions while keeping public IDs stable."""

    _version_cache = {}

    def _get_url(self, name):
        name = self._prepend_prefix(name)
        resource_type = self._get_resource_type(name)
        version = self._get_asset_version(name, resource_type)
        resource = cloudinary.CloudinaryResource(
            name,
            version=version,
            default_resource_type=resource_type,
        )
        return resource.url

    @classmethod
    def _get_asset_version(cls, name, resource_type):
        now = time.monotonic()
        cached = cls._version_cache.get((resource_type, name))
        cache_ttl = getattr(settings, 'CLOUDINARY_VERSION_CACHE_TTL', 300)
        if cached and now - cached[0] < cache_ttl:
            return cached[1]
        try:
            resource = cloudinary.api.resource(name, resource_type=resource_type, type='upload')
            version = resource.get('version')
        except Exception:
            version = None
        cls._version_cache[(resource_type, name)] = (now, version)
        return version