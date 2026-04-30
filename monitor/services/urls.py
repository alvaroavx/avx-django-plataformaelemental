from urllib.parse import urlparse, urlunparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def normalizar_url(valor: str) -> str:
    url = (valor or "").strip()
    if not url:
        raise ValidationError("Ingresa una URL.")

    if "://" not in url:
        url = f"https://{url}"

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Ingresa una URL http o https valida.")

    normalizada = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "",
            "",
            parsed.query,
            "",
        )
    )
    try:
        URLValidator(schemes=["http", "https"])(normalizada)
    except ValidationError as exc:
        raise ValidationError("Ingresa una URL valida.") from exc
    return normalizada


def obtener_dominio(url: str) -> str:
    return urlparse(url).netloc.lower()
