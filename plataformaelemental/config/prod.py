"""
Production-ready configuration.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # type: ignore[name-defined]
if "app.espacioelementos.cl" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("app.espacioelementos.cl")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # type: ignore[name-defined]

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
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Alternativa futura PostgreSQL:
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.environ["POSTGRES_DB"],
#         "USER": os.environ["POSTGRES_USER"],
#         "PASSWORD": os.environ["POSTGRES_PASSWORD"],
#         "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
#         "PORT": os.environ.get("POSTGRES_PORT", "5432"),
#     }
# }
