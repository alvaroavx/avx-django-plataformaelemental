"""
Local development configuration.
"""

from .base import *  # noqa: F401,F403

DEBUG = True

# Accept every host locally to ease testing through tunnels or containers.
ALLOWED_HOSTS = ["*", "app.espacioelementos.cl"]

# Use the console backend so emails are printed to stdout during development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "plataforma_elemental_dev"),
        "USER": os.environ.get("POSTGRES_USER", "plataforma_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
