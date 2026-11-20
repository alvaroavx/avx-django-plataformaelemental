"""
Expose the environment specific settings module as ``plataformaelemental.config``.
"""

from __future__ import annotations

import os
from importlib import import_module

_ENV_CHOICES = {
    "dev": "dev",
    "development": "dev",
    "local": "dev",
    "prod": "prod",
    "production": "prod",
}

ENVIRONMENT = os.environ.get("DJANGO_ENV", "dev").lower()
_resolved_module = _ENV_CHOICES.get(ENVIRONMENT, "dev")

_settings = import_module(f"plataformaelemental.config.{_resolved_module}")

for setting in dir(_settings):
    if setting.isupper():
        globals()[setting] = getattr(_settings, setting)

__all__ = [setting for setting in globals() if setting.isupper()]
