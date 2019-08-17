from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ExtrasConfig(AppConfig):
    name = "extras"

    def ready(self):

        import extras.signals

        # Check that we can connect to the configured Redis database if webhooks are enabled.
        if settings.WEBHOOKS_ENABLED:
            try:
                import redis
            except ImportError:
                raise ImproperlyConfigured(
                    "WEBHOOKS_ENABLED is True but the redis Python package is not installed. (Try 'pip install "
                    "redis'.)"
                )
            try:
                rs = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DATABASE,
                    password=settings.REDIS_PASSWORD or None,
                    ssl=settings.REDIS_SSL,
                )
                rs.ping()
            except redis.exceptions.ConnectionError:
                raise ImproperlyConfigured(
                    "Unable to connect to the Redis database. Check that the Redis configuration has been defined in "
                    "configuration.py."
                )
