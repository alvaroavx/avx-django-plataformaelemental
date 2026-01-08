"""
Production-ready configuration.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # type: ignore[name-defined]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # type: ignore[name-defined]

# Make sure Django knows when it is running behind a load balancer or proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

