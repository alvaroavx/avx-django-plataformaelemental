import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Exists, OuterRef
from django.utils import timezone

from personas.models import Persona, PersonaRol

from asistencias.models import (
    AlumnoDisciplina,
    AsignacionProfesorDisciplina,
    Asistencia,
    SesionClase,
)


def _estado_relaciones(modelo):
    historicas = modelo.objects.filter(origen=modelo.Origen.HISTORICA)
    activas_revisadas = historicas.filter(
        activa=True,
        revisada_por__isnull=False,
        revisada_en__isnull=False,
    ).count()
    activas_sin_revision = historicas.filter(activa=True).exclude(
        revisada_por__isnull=False,
        revisada_en__isnull=False,
    ).count()
    return {
        "total_relaciones": modelo.objects.count(),
        "creadas_desde_historia": historicas.count(),
        "activas_operativas": modelo.objects.operativas().count(),
        "historicas_inactivas": historicas.filter(activa=False).count(),
        "historicas_activas_revisadas": activas_revisadas,
        "historicas_activas_sin_revision": activas_sin_revision,
        "explicitas_inactivas": modelo.objects.filter(
            origen=modelo.Origen.EXPLICITA,
            activa=False,
        ).count(),
    }


def _roles_activos(codigo, pares_persona_organizacion):
    if not pares_persona_organizacion:
        return set()
    personas = {persona_id for persona_id, _ in pares_persona_organizacion}
    organizaciones = {organizacion_id for _, organizacion_id in pares_persona_organizacion}
    return set(
        PersonaRol.objects.filter(
            persona_id__in=personas,
            organizacion_id__in=organizaciones,
            rol__codigo__iexact=codigo,
            activo=True,
        ).values_list("persona_id", "organizacion_id")
    )


def _transicion_profesores(*, fecha_corte, incluir_detalle):
    sesiones = list(
        SesionClase.profesores.through.objects.filter(
            sesionclase__fecha__gte=fecha_corte,
            sesionclase__disciplina__activa=True,
        )
        .exclude(sesionclase__estado=SesionClase.Estado.CANCELADA)
        .values(
            "persona_id",
            "sesionclase_id",
            "sesionclase__fecha",
            "sesionclase__estado",
            "sesionclase__disciplina_id",
            "sesionclase__disciplina__nombre",
            "sesionclase__disciplina__organizacion_id",
            "sesionclase__disciplina__organizacion__nombre",
        )
        .order_by("sesionclase__fecha", "sesionclase_id", "persona_id")
    )
    grupos = {}
    for sesion in sesiones:
        clave = (sesion["persona_id"], sesion["sesionclase__disciplina_id"])
        grupos.setdefault(clave, []).append(sesion)

    persona_ids = {persona_id for persona_id, _ in grupos}
    disciplina_ids = {disciplina_id for _, disciplina_id in grupos}
    personas_activas = set(
        Persona.objects.filter(pk__in=persona_ids, activo=True).values_list("pk", flat=True)
    )
    pares_rol = {
        (persona_id, items[0]["sesionclase__disciplina__organizacion_id"])
        for (persona_id, _), items in grupos.items()
    }
    roles_activos = _roles_activos("PROFESOR", pares_rol)
    relaciones = {
        (relacion.profesor_id, relacion.disciplina_id): relacion
        for relacion in AsignacionProfesorDisciplina.objects.filter(
            profesor_id__in=persona_ids,
            disciplina_id__in=disciplina_ids,
        ).select_related("profesor", "disciplina__organizacion")
    }
    operativas = set(
        AsignacionProfesorDisciplina.objects.operativas()
        .filter(profesor_id__in=persona_ids, disciplina_id__in=disciplina_ids)
        .values_list("profesor_id", "disciplina_id")
    )

    conteos = {
        "profesores_con_sesiones_desde_corte": len(persona_ids),
        "sesiones_no_canceladas_desde_corte": len({item["sesionclase_id"] for item in sesiones}),
        "pares_profesor_disciplina_desde_corte": len(grupos),
        "relaciones_que_conservan_acceso": 0,
        "relaciones_que_requieren_activacion_administrativa": 0,
        "pares_que_requieren_revision_manual": 0,
    }
    detalle = []
    for clave, items in grupos.items():
        persona_id, disciplina_id = clave
        organizacion_id = items[0]["sesionclase__disciplina__organizacion_id"]
        relacion = relaciones.get(clave)
        habilitado = persona_id in personas_activas and (persona_id, organizacion_id) in roles_activos
        if clave in operativas and habilitado:
            clasificacion = "conserva_acceso"
            conteos["relaciones_que_conservan_acceso"] += 1
        elif relacion and habilitado:
            clasificacion = "activar_administrativamente"
            conteos["relaciones_que_requieren_activacion_administrativa"] += 1
        else:
            clasificacion = "revision_manual"
            conteos["pares_que_requieren_revision_manual"] += 1
        if incluir_detalle:
            persona = relacion.profesor if relacion else Persona.objects.get(pk=persona_id)
            detalle.append(
                {
                    "clasificacion": clasificacion,
                    "organizacion_id": organizacion_id,
                    "organizacion": items[0]["sesionclase__disciplina__organizacion__nombre"],
                    "disciplina_id": disciplina_id,
                    "disciplina": items[0]["sesionclase__disciplina__nombre"],
                    "profesor_id": persona_id,
                    "profesor": persona.nombre_completo,
                    "persona_activa": persona_id in personas_activas,
                    "rol_profesor_activo": (persona_id, organizacion_id) in roles_activos,
                    "relacion_id": relacion.pk if relacion else None,
                    "relacion_origen": relacion.origen if relacion else None,
                    "relacion_activa": relacion.activa if relacion else False,
                    "sesiones": [
                        {
                            "id": item["sesionclase_id"],
                            "fecha": item["sesionclase__fecha"].isoformat(),
                            "estado": item["sesionclase__estado"],
                        }
                        for item in items
                    ],
                }
            )
    return conteos, detalle


def _transicion_alumnos(*, fecha_corte, dias_vigencia, incluir_detalle):
    inicio = fecha_corte - timedelta(days=dias_vigencia)
    pares_recientes = set(
        Asistencia.objects.filter(
            sesion__fecha__gte=inicio,
            sesion__fecha__lte=fecha_corte,
        ).values_list("persona_id", "sesion__disciplina_id")
    )
    relaciones = list(
        AlumnoDisciplina.objects.select_related(
            "alumno", "disciplina__organizacion"
        ).filter(
            alumno_id__in={persona_id for persona_id, _ in pares_recientes},
            disciplina_id__in={disciplina_id for _, disciplina_id in pares_recientes},
        )
    )
    relaciones_por_par = {(item.alumno_id, item.disciplina_id): item for item in relaciones}
    operativas_lista = list(
        AlumnoDisciplina.objects.operativas().select_related(
            "alumno", "disciplina__organizacion"
        )
    )
    relaciones_relevantes = {
        item.pk: item for item in [*operativas_lista, *relaciones]
    }.values()
    pares_org = {
        (item.alumno_id, item.disciplina.organizacion_id)
        for item in relaciones_relevantes
    }
    roles_activos = _roles_activos("ESTUDIANTE", pares_org)
    personas_activas = set(
        Persona.objects.filter(
            pk__in={item.alumno_id for item in relaciones_relevantes},
            activo=True,
        ).values_list("pk", flat=True)
    )
    operativas = {(item.alumno_id, item.disciplina_id) for item in operativas_lista}
    vigentes = [
        item
        for item in operativas_lista
        if item.alumno_id in personas_activas
        and (item.alumno_id, item.disciplina.organizacion_id) in roles_activos
    ]
    operativas_inconsistentes = [
        item
        for item in operativas_lista
        if item not in vigentes
    ]
    candidatos = []
    pares_sin_relacion = 0
    for par in pares_recientes:
        if par in operativas:
            continue
        relacion = relaciones_por_par.get(par)
        if relacion is None:
            pares_sin_relacion += 1
            continue
        organizacion_id = relacion.disciplina.organizacion_id
        if (
            relacion.alumno_id in personas_activas
            and (relacion.alumno_id, organizacion_id) in roles_activos
        ):
            candidatos.append(relacion)

    conteos = {
        "alumnos_vigentes_por_relacion_operativa": len({item.alumno_id for item in vigentes}),
        "matriculas_vigentes_confirmadas": len(vigentes),
        "matriculas_operativas_con_persona_o_rol_inactivo": len(operativas_inconsistentes),
        "relaciones_no_operativas_con_asistencia_reciente_para_revision": len(candidatos),
        "pares_recientes_sin_relacion": pares_sin_relacion,
        "ventana_asistencia_reciente_dias": dias_vigencia,
    }
    detalle = []
    if incluir_detalle:
        for relacion in candidatos:
            detalle.append(
                {
                    "clasificacion": "revisar_y_activar_solo_si_sigue_vigente",
                    "organizacion_id": relacion.disciplina.organizacion_id,
                    "organizacion": relacion.disciplina.organizacion.nombre,
                    "disciplina_id": relacion.disciplina_id,
                    "disciplina": relacion.disciplina.nombre,
                    "alumno_id": relacion.alumno_id,
                    "alumno": relacion.alumno.nombre_completo,
                    "relacion_id": relacion.pk,
                    "relacion_origen": relacion.origen,
                    "relacion_activa": relacion.activa,
                }
            )
    return conteos, detalle


def construir_reporte(
    *,
    fecha_corte=None,
    dias_vigencia_alumno=90,
    incluir_detalle_operativo=False,
):
    fecha_corte = fecha_corte or timezone.localdate()
    asignaciones = _estado_relaciones(AsignacionProfesorDisciplina)
    matriculas = _estado_relaciones(AlumnoDisciplina)

    pares_profesor = SesionClase.profesores.through.objects.values(
        "sesionclase__disciplina_id",
        "persona_id",
    ).distinct()
    pares_profesor_sin_relacion = pares_profesor.annotate(
        tiene_relacion=Exists(
            AsignacionProfesorDisciplina.objects.filter(
                disciplina_id=OuterRef("sesionclase__disciplina_id"),
                profesor_id=OuterRef("persona_id"),
            )
        )
    ).filter(tiene_relacion=False).count()

    pares_alumno = Asistencia.objects.values(
        "sesion__disciplina_id",
        "persona_id",
    ).distinct()
    pares_alumno_sin_relacion = pares_alumno.annotate(
        tiene_relacion=Exists(
            AlumnoDisciplina.objects.filter(
                disciplina_id=OuterRef("sesion__disciplina_id"),
                alumno_id=OuterRef("persona_id"),
            )
        )
    ).filter(tiene_relacion=False).count()

    historicas_profesor = AsignacionProfesorDisciplina.objects.filter(
        origen=AsignacionProfesorDisciplina.Origen.HISTORICA,
    ).annotate(
        tiene_rol=Exists(
            PersonaRol.objects.filter(
                persona_id=OuterRef("profesor_id"),
                organizacion_id=OuterRef("disciplina__organizacion_id"),
                rol__codigo__iexact="PROFESOR",
                activo=True,
            )
        )
    )
    historicas_alumno = AlumnoDisciplina.objects.filter(
        origen=AlumnoDisciplina.Origen.HISTORICA,
    ).annotate(
        tiene_rol=Exists(
            PersonaRol.objects.filter(
                persona_id=OuterRef("alumno_id"),
                organizacion_id=OuterRef("disciplina__organizacion_id"),
                rol__codigo__iexact="ESTUDIANTE",
                activo=True,
            )
        )
    )

    asignaciones["sin_inferencia"] = pares_profesor_sin_relacion
    asignaciones["requieren_revision_manual"] = historicas_profesor.filter(activa=False).count()
    asignaciones["ambiguas_sin_rol_profesor_activo"] = historicas_profesor.filter(tiene_rol=False).count()
    asignaciones["ambiguas_disciplinas_con_varios_profesores_historicos"] = (
        historicas_profesor.values("disciplina_id")
        .annotate(total=Count("profesor_id", distinct=True))
        .filter(total__gt=1)
        .count()
    )

    matriculas["sin_inferencia"] = pares_alumno_sin_relacion
    matriculas["requieren_revision_manual"] = historicas_alumno.filter(activa=False).count()
    matriculas["ambiguas_sin_rol_estudiante_activo"] = historicas_alumno.filter(tiene_rol=False).count()
    matriculas["ambiguas_alumnos_en_varias_disciplinas_historicas"] = (
        historicas_alumno.values("alumno_id")
        .annotate(total=Count("disciplina_id", distinct=True))
        .filter(total__gt=1)
        .count()
    )

    profesores, detalle_profesores = _transicion_profesores(
        fecha_corte=fecha_corte,
        incluir_detalle=incluir_detalle_operativo,
    )
    alumnos, detalle_alumnos = _transicion_alumnos(
        fecha_corte=fecha_corte,
        dias_vigencia=dias_vigencia_alumno,
        incluir_detalle=incluir_detalle_operativo,
    )
    reporte = {
        "contiene_datos_sensibles": incluir_detalle_operativo,
        "fecha_corte": fecha_corte.isoformat(),
        "asignaciones_profesor_disciplina": asignaciones,
        "matriculas_alumno_disciplina": matriculas,
        "transicion_permisos": {
            "profesores": profesores,
            "alumnos": alumnos,
            "regla": (
                "Las sesiones futuras identifican pendientes de revisión; nunca activan relaciones. "
                "La asistencia reciente solo genera candidatos manuales y no prueba vigencia."
            ),
        },
    }
    if incluir_detalle_operativo:
        reporte["detalle_operativo_protegido"] = {
            "profesores": detalle_profesores,
            "alumnos_para_revision_manual": detalle_alumnos,
        }
    return reporte


class Command(BaseCommand):
    help = "Reporta historia y transición de permisos; el detalle nominal es opcional y protegido."

    def add_arguments(self, parser):
        parser.add_argument("--formato", choices=("texto", "json"), default="texto")
        parser.add_argument(
            "--fecha-corte",
            type=date.fromisoformat,
            help="Fecha ISO desde la que una sesión se considera vigente (por defecto: hoy).",
        )
        parser.add_argument(
            "--dias-vigencia-alumno",
            type=int,
            default=90,
            help="Ventana que solo identifica alumnos para revisión manual; no los activa.",
        )
        parser.add_argument(
            "--incluir-detalle-operativo",
            action="store_true",
            help=(
                "Incluye nombres e identificadores. La salida debe guardarse solo en un destino "
                "protegido y nunca versionarse."
            ),
        )
        parser.add_argument(
            "--fallar-si-inseguro",
            action="store_true",
            help="Retorna error si existe una relación histórica activa sin revisión completa.",
        )

    def handle(self, *args, **options):
        if options["dias_vigencia_alumno"] < 1:
            raise CommandError("--dias-vigencia-alumno debe ser mayor que cero.")
        reporte = construir_reporte(
            fecha_corte=options["fecha_corte"],
            dias_vigencia_alumno=options["dias_vigencia_alumno"],
            incluir_detalle_operativo=options["incluir_detalle_operativo"],
        )
        inseguras = sum(
            reporte[seccion]["historicas_activas_sin_revision"]
            for seccion in (
                "asignaciones_profesor_disciplina",
                "matriculas_alumno_disciplina",
            )
        )
        if options["formato"] == "json":
            self.stdout.write(json.dumps(reporte, indent=2, sort_keys=True))
        else:
            for seccion, conteos in reporte.items():
                if not isinstance(conteos, dict):
                    continue
                self.stdout.write(seccion)
                for nombre, valor in conteos.items():
                    self.stdout.write(f"  {nombre}: {valor}")
        if options["fallar_si_inseguro"] and inseguras:
            raise CommandError(
                f"Se detectaron {inseguras} relaciones históricas activas sin revisión completa."
            )
