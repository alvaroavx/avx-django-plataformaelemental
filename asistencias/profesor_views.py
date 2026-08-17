from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Prefetch, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_POST

from finanzas.models import LotePago, Payment, PaymentPlan, Transaction
from finanzas.services import confirmar_lote_pagos, crear_pago_operacional
from personas.models import Persona
from personas.search import filtrar_por_fragmentos

from .models import AlumnoDisciplina, SesionClase
from .profesor_contexto import (
    contexto_seleccion_profesor,
    exigir_contexto_mutable,
    filtrar_periodo,
    resolver_contexto_profesor,
)
from .profesor_forms import (
    AlumnoProfesorForm,
    PagoMasivoProfesorForm,
    PagoProfesorForm,
    SesionProfesorForm,
)
from .services import (
    cambiar_estado_sesion_profesor,
    crear_alumno_profesor,
    crear_sesion_profesor,
    liberar_sesion_profesor,
    sesion_en_alcance_profesor,
)


def _parametros_profesor(request, *, organizacion_id=None):
    parametros = {
        "organizacion": str(organizacion_id or request.GET.get("organizacion") or ""),
    }
    for nombre in ("periodo", "periodo_mes", "periodo_anio"):
        valor = request.GET.get(nombre)
        if valor not in (None, ""):
            parametros[nombre] = valor
    return {nombre: valor for nombre, valor in parametros.items() if valor != ""}


def _url_profesor(request, nombre_url, *, organizacion_id=None, **kwargs):
    url = reverse(nombre_url, kwargs=kwargs or None)
    query = urlencode(
        _parametros_profesor(
            request,
            organizacion_id=organizacion_id,
        )
    )
    return f"{url}?{query}" if query else url


def _contexto_seleccion_profesor(request):
    return contexto_seleccion_profesor(request)


def _contexto_profesor(request):
    return resolver_contexto_profesor(request)


def _alumnos_profesor(contexto):
    alumnos_operativos = AlumnoDisciplina.objects.operativas().filter(
        disciplina_id__in=contexto["disciplina_ids"],
        disciplina__organizacion_id__in=contexto["organizacion_ids"],
        alumno__activo=True,
        alumno__roles__organizacion_id=F("disciplina__organizacion_id"),
        alumno__roles__rol__codigo__iexact="ESTUDIANTE",
        alumno__roles__activo=True,
    ).values("alumno_id")
    return Persona.objects.filter(
        pk__in=alumnos_operativos,
        activo=True,
    ).distinct().order_by("apellidos", "nombres")


def _planes_profesor(contexto):
    exigir_contexto_mutable(contexto)
    return PaymentPlan.objects.filter(
        organizacion=contexto["organizacion_activa"],
        activo=True,
    ).order_by("-es_por_defecto", "nombre")


def _sesiones_profesor(contexto):
    return (
        SesionClase.objects.select_related("disciplina", "bloque")
        .prefetch_related("profesores")
        .filter(
            disciplina__organizacion_id__in=contexto["organizacion_ids"],
            disciplina_id__in=contexto["disciplina_ids"],
            profesores=contexto["profesor"],
        )
        .annotate(total_asistentes=Count("asistencias", distinct=True))
        .distinct()
    )


def _glosas_profesor(contexto):
    if contexto["periodo_todos"]:
        return []
    mes, anio = contexto["periodo_mes"], contexto["periodo_anio"]
    resumenes = (
        _sesiones_profesor(contexto)
        .filter(fecha__month=mes, fecha__year=anio, estado=SesionClase.Estado.COMPLETADA)
        .values("disciplina_id", "disciplina__nombre")
        .annotate(sesiones_realizadas=Count("id", distinct=True), asistentes=Count("asistencias"))
        .order_by("disciplina__nombre")
    )
    referencia = timezone.datetime(anio, mes, 1).date()
    periodo = f"{date_format(referencia, 'F').capitalize()}/{anio}"
    return [
        {
            **item,
            "texto": (
                f"Ejecución del taller de {item['disciplina__nombre']} - {periodo} - "
                f"{item['sesiones_realizadas']} sesiones / {item['asistentes']} asistentes"
            ),
        }
        for item in resumenes
    ]


@login_required
def inicio(request):
    if not request.GET.get("organizacion"):
        return render(
            request,
            "asistencias/profesor/seleccionar_organizacion.html",
            _contexto_seleccion_profesor(request),
        )
    contexto = _contexto_profesor(request)
    hoy = timezone.localdate()
    sesiones = filtrar_periodo(_sesiones_profesor(contexto), "fecha", contexto)
    sesiones_hoy = list(sesiones.filter(fecha=hoy).order_by("bloque__hora_inicio", "disciplina__nombre")[:3])
    proxima = sesiones.filter(fecha__gte=hoy).exclude(estado=SesionClase.Estado.CANCELADA).order_by(
        "fecha", "bloque__hora_inicio", "pk"
    ).first()
    if not proxima:
        proxima = sesiones.exclude(estado=SesionClase.Estado.CANCELADA).order_by("-fecha", "-pk").first()
    alumnos = list(_alumnos_profesor(contexto)[:3])
    pagos = list(
        filtrar_periodo(
            Payment.objects.select_related("persona", "disciplina", "disciplina__organizacion", "transaccion")
        .filter(
            organizacion_id__in=contexto["organizacion_ids"],
            disciplina__organizacion_id__in=contexto["organizacion_ids"],
            disciplina_id__in=contexto["disciplina_ids"],
            revertido_en__isnull=True,
        ), "fecha_pago", contexto)
        .order_by("-fecha_pago", "-pk")[:3]
    )
    contexto.update(
        {
            "sesiones_hoy": sesiones_hoy,
            "proxima_sesion": proxima,
            "fecha_hoy": hoy,
            "alumnos_resumen": alumnos,
            "pagos_resumen": pagos,
            "glosas": _glosas_profesor(contexto),
        }
    )
    return render(request, "asistencias/profesor/inicio.html", contexto)


@login_required
def sesiones(request):
    contexto = _contexto_profesor(request)
    hoy = timezone.localdate()
    qs = filtrar_periodo(_sesiones_profesor(contexto), "fecha", contexto)
    if contexto["periodo_todos"]:
        pagina = Paginator(qs.order_by("-fecha", "-pk"), 25).get_page(request.GET.get("pagina"))
        contexto.update({"historial_sesiones": pagina, "page_obj": pagina})
    else:
        qs = qs.order_by("fecha", "pk")
        contexto.update(
            {
                "sesiones_hoy": qs.filter(fecha=hoy),
                "sesiones_futuras": qs.filter(fecha__gt=hoy),
                "sesiones_historicas": qs.filter(fecha__lt=hoy).order_by("-fecha", "-pk"),
            }
        )
    return render(request, "asistencias/profesor/sesiones.html", contexto)


@login_required
def sesion_crear(request):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    form = SesionProfesorForm(
        request.POST or None,
        disciplinas=contexto["disciplinas_profesor"],
    )
    if request.method == "POST" and form.is_valid():
        try:
            sesion = crear_sesion_profesor(
                user=request.user,
                organizacion_id=contexto["organizacion_activa"].pk,
                disciplina=form.cleaned_data["disciplina"],
                fecha=form.cleaned_data["fecha"],
            )
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Sesión planificada correctamente.")
            return redirect(
                _url_profesor(
                    request,
                    "asistencias:sesion_detail",
                    organizacion_id=contexto["organizacion_activa"].pk,
                    pk=sesion.pk,
                )
            )
    contexto["form"] = form
    return render(request, "asistencias/profesor/formulario.html", contexto | {"titulo": "Crear sesión"})


@require_POST
@login_required
def sesion_liberar(request, pk):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    sesion = sesion_en_alcance_profesor(
        request.user,
        organizacion_id=contexto["organizacion_activa"].pk,
        sesion_id=pk,
    )
    if not sesion:
        raise Http404
    try:
        liberar_sesion_profesor(
            user=request.user,
            organizacion_id=contexto["organizacion_activa"].pk,
            sesion=sesion,
            motivo=request.POST.get("motivo"),
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Sesión liberada y auditada.")
    return redirect(_url_profesor(request, "profesor:sesiones"))


@require_POST
@login_required
def sesion_estado(request, pk):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    sesion = sesion_en_alcance_profesor(
        request.user,
        organizacion_id=contexto["organizacion_activa"].pk,
        sesion_id=pk,
    )
    if not sesion:
        raise Http404
    try:
        cambiar_estado_sesion_profesor(
            user=request.user,
            organizacion_id=contexto["organizacion_activa"].pk,
            sesion=sesion,
            estado=request.POST.get("estado"),
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Estado de sesión actualizado.")
    return redirect(_url_profesor(request, "asistencias:sesion_detail", pk=sesion.pk))


@login_required
def alumnos(request):
    contexto = _contexto_profesor(request)
    matriculas = AlumnoDisciplina.objects.operativas().filter(
        disciplina_id__in=contexto["disciplina_ids"],
    ).select_related("disciplina", "disciplina__organizacion")
    alumnos_qs = _alumnos_profesor(contexto).prefetch_related(
        Prefetch("disciplinas_asignadas", queryset=matriculas, to_attr="matriculas_profesor")
    )
    contexto["alumnos"] = alumnos_qs
    return render(request, "asistencias/profesor/alumnos.html", contexto)


@login_required
def alumno_crear(request):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    sesion_retorno = None
    sesion_retorno_id = request.GET.get("volver_sesion")
    if sesion_retorno_id:
        sesion_retorno = sesion_en_alcance_profesor(
            request.user,
            organizacion_id=contexto["organizacion_activa"].pk,
            sesion_id=sesion_retorno_id,
        )
        if not sesion_retorno:
            raise Http404
    inicial = {}
    if sesion_retorno:
        inicial["disciplina"] = sesion_retorno.disciplina
    form = AlumnoProfesorForm(
        request.POST or None,
        disciplinas=contexto["disciplinas_profesor"],
        initial=inicial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            crear_alumno_profesor(
                user=request.user,
                organizacion_id=contexto["organizacion_activa"].pk,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Alumno creado y asociado a tu clase.")
            if sesion_retorno:
                return redirect(
                    _url_profesor(request, "asistencias:sesion_detail", pk=sesion_retorno.pk)
                )
            return redirect(_url_profesor(request, "profesor:alumnos"))
    contexto["form"] = form
    return render(request, "asistencias/profesor/formulario.html", contexto | {"titulo": "Agregar alumno"})


@login_required
def pagos(request):
    contexto = _contexto_profesor(request)
    pagos_qs = (
        Payment.objects.select_related("persona", "disciplina", "plan", "transaccion")
        .filter(
            organizacion_id__in=contexto["organizacion_ids"],
            disciplina__organizacion_id__in=contexto["organizacion_ids"],
            disciplina_id__in=contexto["disciplina_ids"],
        )
        .order_by("-fecha_pago", "-pk")
    )
    pagos_qs = filtrar_periodo(pagos_qs, "fecha_pago", contexto)
    pagina = Paginator(pagos_qs, 25).get_page(request.GET.get("pagina"))
    contexto.update(
        {
            "pagos": pagina,
            "page_obj": pagina,
            "monto_total": pagos_qs.filter(revertido_en__isnull=True).aggregate(total=Sum("monto_total"))["total"] or 0,
            "monto_total_label": "Total histórico" if contexto["periodo_todos"] else "Total del período",
            "glosas": _glosas_profesor(contexto),
        }
    )
    return render(request, "asistencias/profesor/pagos.html", contexto)


@login_required
def pago_crear(request):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    form = PagoProfesorForm(
        request.POST or None,
        request.FILES or None,
        disciplinas=contexto["disciplinas_profesor"],
        alumnos=_alumnos_profesor(contexto),
        planes=_planes_profesor(contexto),
    )
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        pago = Payment(
            organizacion=contexto["organizacion_activa"],
            persona=datos["persona"],
            disciplina=datos["disciplina"],
            plan=datos.get("plan"),
            fecha_pago=datos["fecha_pago"],
            metodo_pago=datos["metodo_pago"],
            numero_comprobante=datos.get("numero_comprobante", ""),
            monto_referencia=datos["monto"],
            aplica_iva=False,
            clases_asignadas=datos.get("clases_asignadas") or 0,
            observaciones=datos["glosa"],
            respaldo=datos.get("respaldo"),
        )
        try:
            pago = crear_pago_operacional(
                pago=pago,
                usuario=request.user,
                origen="profesor_individual",
                clave_idempotencia=datos.get("clave_idempotencia"),
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
            messages.success(request, "Pago y transacción registrados correctamente.")
            return redirect(_url_profesor(request, "profesor:pago_detalle", pk=pago.pk))
    contexto["form"] = form
    return render(request, "asistencias/profesor/formulario.html", contexto | {"titulo": "Registrar pago"})


@login_required
def pago_detalle(request, pk):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    pago = get_object_or_404(
        Payment.objects.select_related("persona", "disciplina", "plan", "transaccion", "transaccion__categoria"),
        pk=pk,
        organizacion=contexto["organizacion_activa"],
        disciplina__organizacion=contexto["organizacion_activa"],
        disciplina_id__in=contexto["disciplina_ids"],
    )
    contexto["pago"] = pago
    return render(request, "asistencias/profesor/pago_detalle.html", contexto)


@require_GET
@login_required
def pago_masivo_alumnos(request):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    try:
        disciplina_id = int(request.GET.get("disciplina", ""))
    except ValueError:
        raise Http404
    if disciplina_id not in contexto["disciplina_ids"]:
        raise Http404
    termino = " ".join((request.GET.get("q") or "").split())
    alumnos_disciplina = AlumnoDisciplina.objects.operativas().filter(
        disciplina_id=disciplina_id,
    ).values("alumno_id")
    alumnos_qs = _alumnos_profesor(contexto).filter(pk__in=alumnos_disciplina)
    if termino:
        alumnos_qs = filtrar_por_fragmentos(
            alumnos_qs,
            termino,
            campos=("nombres", "apellidos", "email", "rut"),
            prefijo="alumno_pago_profesor",
        )
    return JsonResponse(
        {
            "ok": True,
            "resultados": [
                {"id": alumno.pk, "nombre": alumno.nombre_completo}
                for alumno in alumnos_qs.distinct()[:20]
            ],
        }
    )


def _filas_lote_profesor(contexto, datos):
    disciplina = datos["disciplina"]
    ids = datos["personas_seleccionadas"]
    alumnos = {alumno.pk: alumno for alumno in _alumnos_profesor(contexto).filter(pk__in=ids)}
    overrides = datos.get("filas_json") or {}
    filas = []
    errores = {}
    for indice, persona_id in enumerate(ids):
        persona = alumnos.get(persona_id)
        override = overrides.get(str(persona_id), {})
        try:
            monto = Decimal(str(override.get("monto", datos["monto"])))
            clases = int(override.get("clases_asignadas", datos.get("clases_asignadas") or 0))
            if monto <= 0 or clases < 0:
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            errores[persona_id] = "Monto o cantidad de clases inválidos."
            continue
        glosa = str(override.get("glosa", datos["glosa"])).strip()
        if not glosa:
            errores[persona_id] = "La glosa es obligatoria."
            continue
        duplicado = Payment.objects.filter(
            organizacion=contexto["organizacion_activa"],
            persona=persona,
            disciplina=disciplina,
            fecha_pago=datos["fecha_pago"],
            monto_total=monto,
            revertido_en__isnull=True,
        ).exists()
        if duplicado:
            errores[persona_id] = "Ya existe un pago equivalente para este alumno, clase y fecha."
            continue
        filas.append(
            {
                "persona_id": persona_id,
                "persona": persona,
                "disciplina_id": disciplina.pk,
                "plan_id": datos["plan"].pk if datos.get("plan") else None,
                "documento_tributario_id": None,
                "fecha_pago": datos["fecha_pago"],
                "metodo_pago": datos["metodo_pago"],
                "numero_comprobante": datos.get("numero_comprobante", ""),
                "aplica_iva": False,
                "monto_incluye_iva": False,
                "monto_referencia": monto,
                "clases_asignadas": clases,
                "observaciones": glosa,
                "clave_idempotencia": f"{datos['clave_idempotencia']}:{indice}:{persona_id}",
            }
        )
    return filas, errores


@login_required
def pago_masivo(request):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    form = PagoMasivoProfesorForm(
        request.POST or None,
        request.FILES or None,
        disciplinas=contexto["disciplinas_profesor"],
        alumnos=_alumnos_profesor(contexto),
        planes=_planes_profesor(contexto),
    )
    filas = []
    errores = {}
    preview = False
    if request.method == "POST" and form.is_valid():
        filas, errores = _filas_lote_profesor(contexto, form.cleaned_data)
        preview = True
        if request.POST.get("accion") == "confirmar" and not errores and len(filas) == len(
            form.cleaned_data["personas_seleccionadas"]
        ):
            lote, creado = confirmar_lote_pagos(
                usuario=request.user,
                organizacion_id=contexto["organizacion_activa"].pk,
                clave_idempotencia=form.cleaned_data["clave_idempotencia"],
                filas=filas,
                respaldo=form.cleaned_data.get("respaldo"),
                metadatos={
                    "origen": "profesor_masivo",
                    "disciplina_id": form.cleaned_data["disciplina"].pk,
                    "persona_ids": form.cleaned_data["personas_seleccionadas"],
                },
            )
            if not creado:
                messages.info(request, "El lote ya había sido procesado; no se duplicó ningún pago.")
            return redirect(_url_profesor(request, "profesor:pago_masivo_resultado", pk=lote.pk))
    contexto.update({"form": form, "filas": filas, "errores_filas": errores, "preview": preview})
    return render(request, "asistencias/profesor/pago_masivo.html", contexto)


@login_required
def pago_masivo_resultado(request, pk):
    contexto = _contexto_profesor(request)
    exigir_contexto_mutable(contexto)
    lote = get_object_or_404(
        LotePago.objects.prefetch_related("pagos__persona", "pagos__transaccion"),
        pk=pk,
        organizacion=contexto["organizacion_activa"],
        metadatos__origen="profesor_masivo",
        metadatos__disciplina_id__in=contexto["disciplina_ids"],
    )
    pagos = list(lote.pagos.all())
    contexto.update(
        {
            "lote": lote,
            "pagos": pagos,
            "resultado_integro": (
                len(pagos) == lote.cantidad_pagos
                and all(pago.transaccion_id for pago in pagos)
                and len({pago.transaccion_id for pago in pagos}) == len(pagos)
                and Transaction.objects.filter(pago_operacional__lote=lote).count() == len(pagos)
            ),
        }
    )
    return render(request, "asistencias/profesor/pago_masivo_resultado.html", contexto)
