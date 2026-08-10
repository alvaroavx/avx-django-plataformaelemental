import calendar
import json
from datetime import date, time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from personas.models import Organizacion, Persona, PersonaRol

from asistencias.models import (
    AlumnoDisciplina,
    AsignacionProfesorDisciplina,
    Asistencia,
    BloqueHorario,
    Disciplina,
    SesionClase,
)


MARCADOR = "[DATOS_PRUEBA_MES_OPERATIVO]"


class Command(BaseCommand):
    help = "Puebla un mes operativo sintético e idempotente para tres profesores. Solo desarrollo."

    def add_arguments(self, parser):
        parser.add_argument("--anio", type=int, default=2026)
        parser.add_argument("--mes", type=int, default=8)
        parser.add_argument("--organizacion-elementos-id", type=int, required=True)
        parser.add_argument("--organizacion-latin-id", type=int, required=True)
        parser.add_argument("--profesor-lyra-id", type=int, required=True)
        parser.add_argument("--profesor-latin-id", type=int, required=True)
        parser.add_argument("--profesor-circo-id", type=int, required=True)
        parser.add_argument("--disciplina-circo", default="Tela Aérea")
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe los datos. Sin esta opción solo muestra el plan.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Este poblador está bloqueado fuera de un entorno DEBUG.")

        anio = options["anio"]
        mes = options["mes"]
        if mes not in range(1, 13):
            raise CommandError("El mes debe estar entre 1 y 12.")
        try:
            date(anio, mes, 1)
        except ValueError as exc:
            raise CommandError("El año y mes no forman un período válido.") from exc

        elementos = self._organizacion(options["organizacion_elementos_id"])
        latin = self._organizacion(options["organizacion_latin_id"])
        profesor_lyra = self._profesor(options["profesor_lyra_id"], elementos)
        profesor_latin = self._profesor(options["profesor_latin_id"], latin)
        profesor_circo = self._profesor(options["profesor_circo_id"], elementos)
        lyra = self._disciplina_existente(elementos, "Lyra")
        latinrengo = self._disciplina_existente(latin, "LatinRengo")

        estudiantes_elementos = self._estudiantes_organizacion(elementos)
        estudiantes_latin = self._estudiantes_organizacion(latin)
        if len(estudiantes_elementos) < 12:
            raise CommandError("Espacio Elementos necesita al menos 12 estudiantes activos.")
        if len(estudiantes_latin) < 12:
            raise CommandError("Latin Rengo necesita al menos 12 estudiantes activos.")

        escenarios = [
            {
                "codigo": "lyra",
                "organizacion": elementos,
                "disciplina": lyra,
                "profesor": profesor_lyra,
                "dia_semana": BloqueHorario.Dia.LUNES,
                "bloque_nombre": "Lyra Lunes",
                "hora_inicio": time(19, 0),
                "hora_fin": time(21, 0),
                "estudiantes": self._priorizar_matriculados(lyra, estudiantes_elementos, 10),
                "patron": [
                    (SesionClase.Estado.COMPLETADA, 8),
                    (SesionClase.Estado.ABIERTA, 3),
                ],
            },
            {
                "codigo": "latinrengo",
                "organizacion": latin,
                "disciplina": latinrengo,
                "profesor": profesor_latin,
                "dia_semana": BloqueHorario.Dia.SABADO,
                "bloque_nombre": "LatinRengo sabado",
                "hora_inicio": time(18, 0),
                "hora_fin": time(20, 0),
                "estudiantes": self._priorizar_matriculados(latinrengo, estudiantes_latin, 12),
                "patron": [
                    (SesionClase.Estado.COMPLETADA, 10),
                    (SesionClase.Estado.PROGRAMADA, 0),
                ],
            },
            {
                "codigo": "circo",
                "organizacion": elementos,
                "disciplina": None,
                "profesor": profesor_circo,
                "dia_semana": BloqueHorario.Dia.VIERNES,
                "bloque_nombre": f"{options['disciplina_circo']} Viernes",
                "hora_inicio": time(18, 30),
                "hora_fin": time(20, 0),
                "estudiantes": estudiantes_elementos[:12],
                "patron": [(SesionClase.Estado.ABIERTA, 4)],
            },
        ]

        plan = {
            "modo": "aplicar" if options["aplicar"] else "preview",
            "periodo": f"{anio}-{mes:02d}",
            "disciplina_circo": options["disciplina_circo"],
            "sesiones_previstas": sum(
                len(self._fechas_mes(anio, mes, escenario["dia_semana"]))
                for escenario in escenarios
            ),
            "asistencias_previstas": sum(
                cantidad
                for escenario in escenarios
                for _estado, cantidad in escenario["patron"]
            ),
        }
        if not options["aplicar"]:
            self.stdout.write(json.dumps(plan, ensure_ascii=False, indent=2))
            self.stdout.write(self.style.WARNING("Preview: no se escribieron datos."))
            return

        with transaction.atomic():
            disciplina_circo = self._disciplina_circo(
                elementos,
                options["disciplina_circo"],
            )
            escenarios[2]["disciplina"] = disciplina_circo
            resultado = self._aplicar_escenarios(escenarios, anio, mes)

        self.stdout.write(json.dumps(plan | resultado, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS("Mes de pruebas poblado correctamente."))

    def _organizacion(self, organizacion_id):
        try:
            return Organizacion.objects.get(pk=organizacion_id)
        except Organizacion.DoesNotExist as exc:
            raise CommandError(f"No existe la organización {organizacion_id}.") from exc

    def _profesor(self, persona_id, organizacion):
        try:
            profesor = Persona.objects.get(pk=persona_id, activo=True)
        except Persona.DoesNotExist as exc:
            raise CommandError(f"No existe la persona activa {persona_id}.") from exc
        tiene_rol = PersonaRol.objects.filter(
            persona=profesor,
            organizacion=organizacion,
            rol__codigo__iexact="PROFESOR",
            activo=True,
        ).exists()
        if not tiene_rol:
            raise CommandError(
                f"La persona {persona_id} no es profesor activo de la organización {organizacion.pk}."
            )
        return profesor

    def _disciplina_existente(self, organizacion, nombre):
        try:
            return Disciplina.objects.get(
                organizacion=organizacion,
                nombre__iexact=nombre,
                activa=True,
            )
        except Disciplina.DoesNotExist as exc:
            raise CommandError(
                f"No existe la disciplina activa {nombre} en la organización {organizacion.pk}."
            ) from exc
        except Disciplina.MultipleObjectsReturned as exc:
            raise CommandError(
                f"Hay más de una disciplina activa llamada {nombre} en la organización {organizacion.pk}."
            ) from exc

    def _disciplina_circo(self, organizacion, nombre):
        existentes = Disciplina.objects.filter(
            organizacion=organizacion,
            nombre__iexact=nombre,
            nivel="",
        )
        if existentes.count() > 1:
            raise CommandError(f"Hay más de una disciplina circense llamada {nombre}.")
        disciplina = existentes.first()
        if disciplina:
            if not disciplina.activa:
                raise CommandError(
                    f"La disciplina {nombre} ya existe pero está inactiva; no se reactivó automáticamente."
                )
            return disciplina
        return Disciplina.objects.create(
            organizacion=organizacion,
            nombre=nombre,
            descripcion=f"{MARCADOR} Disciplina circense sintética para pruebas operativas.",
            badge_color=Disciplina.BadgeColor.MORADO,
            activa=True,
        )

    def _estudiantes_organizacion(self, organizacion):
        return list(
            Persona.objects.filter(
                activo=True,
                roles__organizacion=organizacion,
                roles__rol__codigo__iexact="ESTUDIANTE",
                roles__activo=True,
            )
            .distinct()
            .order_by("pk")
        )

    def _priorizar_matriculados(self, disciplina, estudiantes, limite):
        ids_validos = {persona.pk for persona in estudiantes}
        ids_matriculados = AlumnoDisciplina.objects.operativas().filter(
            disciplina=disciplina,
            alumno_id__in=ids_validos,
        ).values("alumno_id")
        matriculados = list(
            Persona.objects.filter(
                pk__in=ids_matriculados,
            )
            .distinct()
            .order_by("pk")
        )
        usados = {persona.pk for persona in matriculados}
        matriculados.extend(persona for persona in estudiantes if persona.pk not in usados)
        return matriculados[:limite]

    def _fechas_mes(self, anio, mes, dia_semana):
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        return [
            fecha
            for dia in range(1, ultimo_dia + 1)
            if (fecha := date(anio, mes, dia)).weekday() == dia_semana
        ]

    def _bloque(self, escenario):
        disciplina = escenario["disciplina"]
        existente = (
            BloqueHorario.objects.filter(
                organizacion=escenario["organizacion"],
                disciplina=disciplina,
                dia_semana=escenario["dia_semana"],
            )
            .order_by("hora_inicio", "pk")
            .first()
        )
        if existente:
            return existente, False
        return BloqueHorario.objects.get_or_create(
            organizacion=escenario["organizacion"],
            disciplina=disciplina,
            nombre=escenario["bloque_nombre"],
            defaults={
                "dia_semana": escenario["dia_semana"],
                "hora_inicio": escenario["hora_inicio"],
                "hora_fin": escenario["hora_fin"],
            },
        )

    def _aplicar_escenarios(self, escenarios, anio, mes):
        conteos = {
            "sesiones_creadas": 0,
            "sesiones_actualizadas": 0,
            "sesiones_omitidas_por_conflicto": 0,
            "asistencias_creadas": 0,
            "asistencias_actualizadas": 0,
            "matriculas_creadas": 0,
            "bloques_creados": 0,
        }
        detalle = []
        for escenario in escenarios:
            disciplina = escenario["disciplina"]
            asignacion, _ = AsignacionProfesorDisciplina.objects.update_or_create(
                disciplina=disciplina,
                profesor=escenario["profesor"],
                defaults={
                    "activa": True,
                    "origen": AsignacionProfesorDisciplina.Origen.EXPLICITA,
                },
            )
            if not asignacion.activa:
                raise CommandError("No se pudo activar la asignación del profesor.")
            bloque, bloque_creado = self._bloque(escenario)
            conteos["bloques_creados"] += int(bloque_creado)

            for estudiante in escenario["estudiantes"]:
                _matricula, creada = AlumnoDisciplina.objects.update_or_create(
                    disciplina=disciplina,
                    alumno=estudiante,
                    defaults={
                        "activa": True,
                        "origen": AlumnoDisciplina.Origen.EXPLICITA,
                    },
                )
                conteos["matriculas_creadas"] += int(creada)

            sesiones_escenario = []
            fechas = self._fechas_mes(anio, mes, escenario["dia_semana"])
            for indice, fecha in enumerate(fechas):
                estado, cantidad = (
                    escenario["patron"][indice]
                    if indice < len(escenario["patron"])
                    else (SesionClase.Estado.PROGRAMADA, 0)
                )
                nota = f"{MARCADOR} {anio}-{mes:02d} · {escenario['codigo']}"
                existentes = SesionClase.objects.filter(disciplina=disciplina, fecha=fecha).order_by("pk")
                if existentes.count() > 1:
                    raise CommandError(
                        f"Hay sesiones duplicadas para {disciplina.nombre} el {fecha}; no se modificaron."
                    )
                sesion = existentes.first()
                if sesion and MARCADOR not in sesion.notas:
                    conteos["sesiones_omitidas_por_conflicto"] += 1
                    sesiones_escenario.append({"fecha": fecha.isoformat(), "resultado": "conflicto"})
                    continue
                if sesion:
                    sesion.bloque = bloque
                    sesion.estado = estado
                    sesion.cupo_maximo = 16
                    sesion.notas = nota
                    sesion.save(update_fields=["bloque", "estado", "cupo_maximo", "notas"])
                    conteos["sesiones_actualizadas"] += 1
                else:
                    sesion = SesionClase.objects.create(
                        disciplina=disciplina,
                        bloque=bloque,
                        fecha=fecha,
                        estado=estado,
                        cupo_maximo=16,
                        notas=nota,
                    )
                    conteos["sesiones_creadas"] += 1
                sesion.profesores.add(escenario["profesor"])

                for posicion, estudiante in enumerate(escenario["estudiantes"][:cantidad]):
                    estado_asistencia = Asistencia.Estado.PRESENTE
                    if posicion == cantidad - 1:
                        estado_asistencia = Asistencia.Estado.JUSTIFICADA
                    elif cantidad >= 6 and posicion == cantidad - 2:
                        estado_asistencia = Asistencia.Estado.AUSENTE
                    _asistencia, creada = Asistencia.objects.update_or_create(
                        sesion=sesion,
                        persona=estudiante,
                        defaults={
                            "estado": estado_asistencia,
                            "comentario": f"{MARCADOR} Registro sintético de asistencia.",
                        },
                    )
                    llave = "asistencias_creadas" if creada else "asistencias_actualizadas"
                    conteos[llave] += 1
                sesiones_escenario.append(
                    {
                        "id": sesion.pk,
                        "fecha": fecha.isoformat(),
                        "estado": estado,
                        "asistencias": cantidad,
                    }
                )
            detalle.append(
                {
                    "codigo": escenario["codigo"],
                    "organizacion_id": escenario["organizacion"].pk,
                    "disciplina_id": disciplina.pk,
                    "profesor_id": escenario["profesor"].pk,
                    "sesiones": sesiones_escenario,
                }
            )
        return conteos | {"detalle": detalle}
