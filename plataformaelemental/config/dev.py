"""
Local development configuration.
"""

from .base import *  # noqa: F401,F403

DEBUG = True

# Accept every host locally to ease testing through tunnels or containers.
ALLOWED_HOSTS = ["*", "app.espacioelementos.cl"]

# Use the console backend so emails are printed to stdout during development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
