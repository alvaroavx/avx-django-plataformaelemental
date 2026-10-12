"""Envío de un mes a la API v1 de Cuadratura (ADR 0023).

Elemental se adapta al contrato genérico `cuadratura-operations-v1` que define
Cuadratura. El lote queda en revisión allá: una persona lo confirma en Cuadratura.

Seguridad (ADR 0006 de Cuadratura):
- token Bearer más firma Ed25519 de cada request con la llave privada de Elemental;
- solo HTTPS fuera de DEBUG y sin seguir redirecciones.

Bloqueo del mes:
- se registra un intento EN_CURSO, que ya bloquea el mes, antes de leer los datos y
  de llamar a la API, para que nadie edite pagos mientras se envían;
- si el POST salió y no hubo respuesta válida, el intento queda INCIERTO: el mes
  sigue bloqueado y un reintento manda el mismo contenido (mismo `batch_id`).
"""

import base64
import hashlib
import json
import secrets
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.models import AuditLog
from auditoria.services import registrar_auditoria
from finanzas.models import MESES_ES, EnvioCuadratura, ultimo_envio_cuadratura
from personas.models import Organizacion

from .cuadratura_v1 import prepare_month

CONTRACT_VERSION = "cuadratura-operations-v1"
MOTIVOS_NO_BLOQUEANTES = {"payment_reversed"}
ESTADOS_ACEPTADOS = {"VALIDATED", "COMMITTED"}


class EnvioNoTransmitido(Exception):
    """Falló antes de enviar el lote: Cuadratura no recibió datos."""


def _normalizar_rut(valor):
    return "".join(caracter for caracter in (valor or "").upper() if caracter.isalnum())


def _huella(documento):
    estable = {clave: valor for clave, valor in documento.items() if clave not in {"generated_at", "batch_id"}}
    return hashlib.sha256(
        json.dumps(estable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def construir_documento(preparacion):
    """Traduce la preparación del mes al contrato genérico de Cuadratura.

    `batch_id` se deriva del contenido: el mismo mes sin cambios produce la misma
    llave y Cuadratura lo reconoce como reenvío en vez de crear otro lote.
    """
    operaciones = [
        {
            "external_id": operacion["external_id"],
            "operation_date": operacion["operation_date"],
            "service_period": operacion["service_period"],
            "detail": operacion["detail"],
            "customer_name": operacion["beneficiary"]["display_name"],
            "tax": operacion["tax"],
            "payments": [
                {
                    "external_id": pago["external_id"],
                    "payment_date": pago["payment_date"],
                    "amount": pago["amount"],
                    "reference": pago["reference"],
                }
                for pago in operacion["payments"]
            ],
        }
        for operacion in preparacion["operations"]
    ]
    documento = {
        "contract_version": CONTRACT_VERSION,
        "batch_id": "",
        "generated_at": preparacion["generated_at"],
        "period": preparacion["selection"]["period"],
        "taxpayer": {
            "tax_id": preparacion["expected_taxpayer"]["tax_id"],
            "legal_name": preparacion["expected_taxpayer"]["legal_name"],
        },
        "source": {
            "organization_id": preparacion["source_organization"]["external_id"],
            "name": preparacion["source_organization"]["name"],
        },
        "operations": operaciones,
        "excluded_records": [
            {"external_id": registro["external_id"], "reasons": registro["reasons"]}
            for registro in preparacion["pending_records"]
        ],
        "summary": {
            "operations": len(operaciones),
            "payments": sum(len(operacion["payments"]) for operacion in operaciones),
            "total_amount": sum(operacion["tax"]["total"] for operacion in operaciones),
        },
    }
    documento["batch_id"] = _huella(documento)
    return documento


def _llave_privada():
    ruta = settings.CUADRATURA_API_PRIVATE_KEY_FILE
    if not ruta:
        return None
    return load_pem_private_key(Path(ruta).read_bytes(), password=None)


def problemas_configuracion():
    problemas = []
    if not settings.CUADRATURA_API_URL or not settings.CUADRATURA_API_TOKEN:
        problemas.append(
            "La integración con Cuadratura no está configurada (CUADRATURA_API_URL y CUADRATURA_API_TOKEN)."
        )
        return problemas
    if not settings.CUADRATURA_API_URL.startswith("https://") and not settings.DEBUG:
        problemas.append("CUADRATURA_API_URL debe usar https:// para no exponer el token.")
    if settings.CUADRATURA_API_PRIVATE_KEY_FILE:
        try:
            _llave_privada()
        except (OSError, ValueError, TypeError):
            problemas.append("No se pudo leer la llave privada de CUADRATURA_API_PRIVATE_KEY_FILE.")
    elif not settings.DEBUG:
        problemas.append("Falta CUADRATURA_API_PRIVATE_KEY_FILE: Cuadratura exige firmar cada envío.")
    return problemas


def _en_curso_vencido(envio):
    limite = timedelta(seconds=2 * settings.CUADRATURA_API_TIMEOUT + 60)
    return envio.estado == EnvioCuadratura.Estado.EN_CURSO and envio.creado_en < timezone.now() - limite


def estado_envio(*, organizacion, anio, mes, preparacion, hoy=None):
    """Indica si el mes puede enviarse y, si no, por qué."""
    periodo = date(anio, mes, 1)
    hoy = hoy or timezone.localdate()
    envios = EnvioCuadratura.objects.filter(organizacion=organizacion, periodo=periodo).select_related(
        "enviado_por"
    )
    ultimo = envios.first()
    enviado = envios.filter(estado=EnvioCuadratura.Estado.ENVIADO).first()
    motivos = []
    if enviado:
        motivos.append("Este mes ya fue enviado a Cuadratura y quedó bloqueado.")
    elif ultimo and ultimo.estado == EnvioCuadratura.Estado.EN_CURSO and not _en_curso_vencido(ultimo):
        motivos.append("Hay un envío en curso para este mes.")
    else:
        motivos.extend(problemas_configuracion())
        if periodo >= hoy.replace(day=1):
            motivos.append("Solo se pueden enviar meses terminados.")
        bloqueantes = [
            registro
            for registro in preparacion["pending_records"]
            if set(registro["reasons"]) - MOTIVOS_NO_BLOQUEANTES
        ]
        if bloqueantes:
            motivos.append(
                f"Hay {len(bloqueantes)} pago(s) pendiente(s) de aclaración. Resuélvelos antes de enviar: "
                "después del envío el mes queda bloqueado y ya no podrían corregirse."
            )
        if not preparacion["operations"]:
            motivos.append("No hay operaciones para enviar en este mes.")
    return {
        "enviado": enviado,
        "incierto": ultimo if ultimo and ultimo.estado == EnvioCuadratura.Estado.INCIERTO else None,
        "intentos": list(envios[:10]),
        "motivos": motivos,
        "puede_enviar": not motivos,
    }


def _url_revision_segura(valor):
    """Solo enlaces al mismo host de Cuadratura y por HTTPS (o HTTP en DEBUG)."""
    destino, base = urlsplit(str(valor or "")), urlsplit(settings.CUADRATURA_API_URL)
    esquemas = {"https", "http"} if settings.DEBUG else {"https"}
    if destino.scheme in esquemas and destino.netloc == base.netloc:
        return destino.geturl()[:500]
    return ""


def _cabeceras(metodo, url, cuerpo=b""):
    cabeceras = {"Authorization": f"Bearer {settings.CUADRATURA_API_TOKEN}", "Accept": "application/json"}
    llave = _llave_privada()
    if llave is None:
        return cabeceras
    partes = urlsplit(url)
    ruta = partes.path + (f"?{partes.query}" if partes.query else "")
    marca, nonce = str(int(time.time())), secrets.token_urlsafe(18)
    mensaje = "\n".join([metodo, ruta, marca, nonce, hashlib.sha256(cuerpo).hexdigest()]).encode()
    cabeceras.update({
        "X-Cuadratura-Timestamp": marca,
        "X-Cuadratura-Nonce": nonce,
        "X-Cuadratura-Signature": base64.b64encode(llave.sign(mensaje)).decode(),
    })
    return cabeceras


def _resultado_lote(envio, lote):
    envio.lote_cuadratura = str(lote.get("id", ""))[:64]
    envio.estado_cuadratura = str(lote.get("status", ""))[:20]
    envio.url_revision = _url_revision_segura(lote.get("links", {}).get("review", ""))
    envio.respuesta = lote
    if envio.estado_cuadratura in ESTADOS_ACEPTADOS:
        envio.estado = EnvioCuadratura.Estado.ENVIADO
    else:
        envio.estado = EnvioCuadratura.Estado.RECHAZADO
        envio.detalle_error = "; ".join(lote.get("errors") or []) or "Cuadratura bloqueó el lote."


def _mensaje_error(respuesta):
    try:
        return respuesta.json().get("error", {}).get("message") or f"HTTP {respuesta.status_code}"
    except (ValueError, AttributeError):
        return f"HTTP {respuesta.status_code}"


def _destino(sesion, organizacion):
    """Busca la organización destino por RUT en el descubrimiento de la API."""
    url = f"{settings.CUADRATURA_API_URL}/api/v1/"
    try:
        raiz = sesion.get(
            url, headers=_cabeceras("GET", url), timeout=settings.CUADRATURA_API_TIMEOUT, allow_redirects=False
        )
        datos = raiz.json() if raiz.status_code == 200 else None
    except (requests.RequestException, ValueError) as exc:
        raise EnvioNoTransmitido(f"No fue posible comunicarse con Cuadratura ({exc.__class__.__name__}).") from exc
    if datos is None:
        raise EnvioNoTransmitido(f"Cuadratura rechazó la conexión: {_mensaje_error(raiz)}")
    rut = _normalizar_rut(organizacion.rut)
    destino = next(
        (org for org in datos.get("organizations", []) if _normalizar_rut(org.get("tax_id")) == rut), None
    )
    if destino is None:
        raise EnvioNoTransmitido(
            f"Cuadratura no tiene habilitada para Elemental una organización con RUT {organizacion.rut}."
        )
    return destino["id"]


def _transmitir(envio, documento, organizacion, sesion):
    """Hace el envío y deja en `envio` el estado resultante."""
    try:
        destino = _destino(sesion, organizacion)
    except EnvioNoTransmitido as exc:
        envio.estado = EnvioCuadratura.Estado.FALLIDO
        envio.detalle_error = str(exc)
        return
    url = f"{settings.CUADRATURA_API_URL}/api/v1/organizations/{destino}/periods/{documento['period']}/batches/"
    cuerpo = json.dumps(documento, ensure_ascii=False).encode("utf-8")
    try:
        respuesta = sesion.post(
            url,
            data=cuerpo,
            headers={**_cabeceras("POST", url, cuerpo), "Content-Type": "application/json"},
            timeout=settings.CUADRATURA_API_TIMEOUT,
            allow_redirects=False,
        )
    except requests.ConnectTimeout:
        envio.estado = EnvioCuadratura.Estado.FALLIDO
        envio.detalle_error = "Cuadratura no respondió al conectar; no se enviaron datos."
        return
    except requests.RequestException as exc:
        envio.estado = EnvioCuadratura.Estado.INCIERTO
        envio.detalle_error = (
            f"Se envió el lote pero no hubo respuesta ({exc.__class__.__name__}). "
            "El mes queda bloqueado hasta reintentar."
        )
        return
    try:
        cuerpo_respuesta = respuesta.json()
    except ValueError:
        cuerpo_respuesta = None
    if respuesta.status_code in (200, 201) and isinstance(cuerpo_respuesta, dict) and isinstance(
        cuerpo_respuesta.get("batch"), dict
    ):
        _resultado_lote(envio, cuerpo_respuesta["batch"])
    elif 400 <= respuesta.status_code < 500 and respuesta.status_code != 429:
        envio.estado = EnvioCuadratura.Estado.RECHAZADO
        envio.respuesta = cuerpo_respuesta if isinstance(cuerpo_respuesta, dict) else {}
        envio.detalle_error = _mensaje_error(respuesta)
    else:
        envio.estado = EnvioCuadratura.Estado.INCIERTO
        envio.respuesta = cuerpo_respuesta if isinstance(cuerpo_respuesta, dict) else {}
        envio.detalle_error = (
            f"Cuadratura respondió HTTP {respuesta.status_code}. El mes queda bloqueado hasta reintentar."
        )


def _registrar_inicio(*, organizacion, periodo, usuario):
    """Crea el intento EN_CURSO (que bloquea el mes) serializado por organización."""
    try:
        with transaction.atomic():
            Organizacion.objects.select_for_update().get(pk=organizacion.pk)
            ultimo = ultimo_envio_cuadratura(organizacion.pk, periodo)
            if ultimo and _en_curso_vencido(ultimo):
                ultimo.estado = EnvioCuadratura.Estado.INCIERTO
                ultimo.detalle_error = "El envío se interrumpió sin respuesta."
                ultimo.save(update_fields=["estado", "detalle_error", "actualizado_en"])
            return EnvioCuadratura.objects.create(
                organizacion=organizacion,
                periodo=periodo,
                estado=EnvioCuadratura.Estado.EN_CURSO,
                enviado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
                contrato=CONTRACT_VERSION,
            )
    except IntegrityError as exc:
        raise ValidationError("Este mes ya fue enviado o tiene un envío en curso.") from exc


def enviar_mes(*, organizacion, anio, mes, usuario, sesion=None):
    """Envía el mes a Cuadratura y registra el intento. Devuelve el EnvioCuadratura."""
    periodo = date(anio, mes, 1)
    estado = estado_envio(
        organizacion=organizacion,
        anio=anio,
        mes=mes,
        preparacion=prepare_month(organization=organizacion, year=anio, month=mes),
    )
    if not estado["puede_enviar"]:
        raise ValidationError(estado["motivos"][0])
    envio = _registrar_inicio(organizacion=organizacion, periodo=periodo, usuario=usuario)
    # Con el mes ya bloqueado, la lectura es estable: nadie puede editar sus pagos.
    preparacion = prepare_month(organization=organizacion, year=anio, month=mes)
    documento = construir_documento(preparacion)
    envio.batch_id = documento["batch_id"]
    envio.operaciones = documento["summary"]["operations"]
    envio.monto_total = documento["summary"]["total_amount"]
    _transmitir(envio, documento, organizacion, sesion or requests.Session())
    with transaction.atomic():
        envio.save()
        registrar_auditoria(
            usuario=usuario,
            accion=AuditLog.ACCION_CAMBIAR_ESTADO,
            dominio="finanzas",
            objeto=envio,
            organizacion=organizacion,
            resumen=f"Envío de {MESES_ES[mes - 1]} {anio} a Cuadratura: {envio.get_estado_display()}",
            metadata={
                "periodo": f"{anio:04d}-{mes:02d}",
                "estado": envio.estado,
                "batch_id": envio.batch_id,
                "lote_cuadratura": envio.lote_cuadratura,
                "estado_cuadratura": envio.estado_cuadratura,
                "operaciones": envio.operaciones,
                "monto_total": envio.monto_total,
            },
        )
    return envio
