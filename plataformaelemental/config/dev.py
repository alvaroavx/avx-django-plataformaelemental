"""
Local development configuration.
"""

from .base import *  # noqa: F401,F403

DEBUG = True

# Accept every host locally to ease testing through tunnels or containers.
ALLOWED_HOSTS = ["*", "apps.avx.cl"]

# Use the console backend so emails are printed to stdout during development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Fallback SQLite local:
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

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
