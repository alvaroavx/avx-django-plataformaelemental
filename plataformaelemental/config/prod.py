"""
Production-ready configuration.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # type: ignore[name-defined]
if "apps.espacioelementos.cl" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("apps.espacioelementos.cl")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # type: ignore[name-defined]
if "https://apps.espacioelementos.cl" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://apps.espacioelementos.cl")

# Make sure Django knows when it is running behind a load balancer or proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "elemental_sessionid")
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", "7200"))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)  # type: ignore[name-defined]
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)  # type: ignore[name-defined]
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)  # type: ignore[name-defined]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.environ["POSTGRES_PORT"],
    }
}

# Los nombres con hash evitan que navegadores y proxies conserven CSS o JS de
# una versión anterior después de collectstatic, incluida la app de Profesor.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

# Los archivos publicados por Django deben ser legibles por el servidor web,
# aunque el usuario de deploy y el de Nginx pertenezcan a grupos distintos.
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
