"""
Compatibility wrapper.

The project uses the ``plataformaelemental.config`` package to expose settings
per execution environment (development, production, etc). Import everything
from the package so that legacy references to ``plataformaelemental.settings``
keep working.
"""

from .config import *  # noqa: F401,F403
