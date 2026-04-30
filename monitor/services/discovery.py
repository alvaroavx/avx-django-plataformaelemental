import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from django.utils import timezone

from monitor.models import ConfiguracionMonitor, DiscoverySitio, Sitio


MAX_HTML_BYTES = 262_144
MAX_ERROR_CHARS = 500


class _HTMLResumenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._en_titulo = False
        self._titulo_partes = []
        self.meta_description = ""

    @property
    def titulo(self) -> str:
        return " ".join("".join(self._titulo_partes).split())[:255]

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self._en_titulo = True
            return
        if tag.lower() != "meta":
            return

        atributos = {nombre.lower(): valor for nombre, valor in attrs if nombre and valor}
        if atributos.get("name", "").lower() == "description":
            self.meta_description = atributos.get("content", "")[:1000]

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._en_titulo = False

    def handle_data(self, data):
        if self._en_titulo:
            self._titulo_partes.append(data)


class _SinRedirecciones(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _leer_resumen_html(contenido: bytes, charset: str | None) -> tuple[str, str]:
    parser = _HTMLResumenParser()
    texto = contenido.decode(charset or "utf-8", errors="replace")
    parser.feed(texto)
    return parser.titulo, parser.meta_description


def _resolver_configuracion(sitio: Sitio) -> dict:
    global_config = ConfiguracionMonitor.actual()
    configuracion_sitio = getattr(sitio, "configuracion", None)
    if not configuracion_sitio:
        return {
            "timeout": global_config.timeout_segundos,
            "seguir_redirecciones": global_config.seguir_redirecciones,
            "user_agent": global_config.user_agent,
        }

    return {
        "timeout": configuracion_sitio.timeout_resuelto(global_config),
        "seguir_redirecciones": configuracion_sitio.seguir_redirecciones_resuelto(global_config),
        "user_agent": global_config.user_agent,
    }


def ejecutar_discovery_inicial(sitio: Sitio) -> DiscoverySitio:
    configuracion = _resolver_configuracion(sitio)
    request = Request(sitio.url, headers={"User-Agent": configuracion["user_agent"]})
    opener = None
    if not configuracion["seguir_redirecciones"]:
        opener = build_opener(_SinRedirecciones())

    inicio = time.monotonic()
    datos = {
        "estado_http": None,
        "url_final": "",
        "titulo": "",
        "meta_description": "",
        "ssl_valido": None,
        "tiempo_respuesta_ms": None,
        "error": "",
    }

    try:
        respuesta = (
            opener.open(request, timeout=configuracion["timeout"])
            if opener
            else urlopen(request, timeout=configuracion["timeout"])
        )
        with respuesta:
            contenido = respuesta.read(MAX_HTML_BYTES)
            datos["estado_http"] = respuesta.getcode()
            datos["url_final"] = respuesta.geturl()
            datos["tiempo_respuesta_ms"] = int((time.monotonic() - inicio) * 1000)
            datos["ssl_valido"] = datos["url_final"].startswith("https://")
            titulo, meta_description = _leer_resumen_html(
                contenido,
                respuesta.headers.get_content_charset(),
            )
            datos["titulo"] = titulo
            datos["meta_description"] = meta_description
    except HTTPError as exc:
        datos["estado_http"] = exc.code
        datos["url_final"] = exc.url
        datos["tiempo_respuesta_ms"] = int((time.monotonic() - inicio) * 1000)
        datos["ssl_valido"] = exc.url.startswith("https://") if exc.url else None
        datos["error"] = f"HTTP {exc.code}: {exc.reason}"[:MAX_ERROR_CHARS]
    except (URLError, TimeoutError, socket.timeout, ssl.SSLError, OSError) as exc:
        datos["tiempo_respuesta_ms"] = int((time.monotonic() - inicio) * 1000)
        datos["error"] = str(exc)[:MAX_ERROR_CHARS]

    discovery = DiscoverySitio.objects.create(sitio=sitio, **datos)
    sitio.ultimo_check_en = timezone.now()
    if datos["estado_http"] and 200 <= datos["estado_http"] < 400 and not datos["error"]:
        sitio.ultimo_estado = Sitio.ESTADO_ACTIVO
    elif datos["estado_http"] and 300 <= datos["estado_http"] < 400:
        sitio.ultimo_estado = Sitio.ESTADO_ADVERTENCIA
    else:
        sitio.ultimo_estado = Sitio.ESTADO_ERROR
    sitio.save(update_fields=["ultimo_estado", "ultimo_check_en", "dominio", "actualizado_en"])
    return discovery
