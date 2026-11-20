import calendar
import json
from datetime import date, time
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from personas.models import Organizacion, Persona, PersonaRol
from finanzas.models import Payment, PaymentPlan
from finanzas.services import crear_pago_operacional, imputar_pago_a_deudas

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
            "--fecha-corte",
            type=date.fromisoformat,
            help=(
                "Fecha máxima que puede declararse operada, en formato AAAA-MM-DD. "
                "Por defecto usa la fecha local de ejecución, acotada al período."
            ),
        )
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
        inicio_mes = date(anio, mes, 1)
        fin_mes = date(anio, mes, calendar.monthrange(anio, mes)[1])
        fecha_corte = min(options.get("fecha_corte") or timezone.localdate(), fin_mes)
        if fecha_corte < inicio_mes:
            fecha_corte = inicio_mes.fromordinal(inicio_mes.toordinal() - 1)

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
            "fecha_corte": fecha_corte.isoformat(),
            "disciplina_circo": options["disciplina_circo"],
            "sesiones_previstas": sum(
                len(self._fechas_mes(anio, mes, escenario["dia_semana"]))
                for escenario in escenarios
            ),
            "asistencias_previstas": sum(
                cantidad
                for escenario in escenarios
                for indice, fecha in enumerate(
                    self._fechas_mes(anio, mes, escenario["dia_semana"])
                )
                for _estado, cantidad in [
                    escenario["patron"][indice]
                    if indice < len(escenario["patron"]) and fecha <= fecha_corte
                    else (SesionClase.Estado.PROGRAMADA, 0)
                ]
            ),
            "pagos_previstos": sum(
                sum(
                    self._fecha_pago(anio, mes, posicion) <= fecha_corte
                    for posicion, _estudiante in enumerate(escenario["estudiantes"][:6])
                )
                for escenario in escenarios
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
            resultado = self._aplicar_escenarios(escenarios, anio, mes, fecha_corte)
            resultado.update(self._aplicar_pagos(escenarios, anio, mes, fecha_corte))

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
        coincidencias = BloqueHorario.objects.filter(
            organizacion=escenario["organizacion"],
            disciplina=disciplina,
            dia_semana=escenario["dia_semana"],
            hora_inicio=escenario["hora_inicio"],
            hora_fin=escenario["hora_fin"],
        )
        if coincidencias.count() > 1:
            raise CommandError(
                f"Hay más de un bloque compatible con el escenario {escenario['codigo']}."
            )
        existente = coincidencias.first()
        if existente:
            administrado = SesionClase.objects.filter(
                bloque=existente,
                notas__contains=MARCADOR,
            ).exists()
            if not administrado:
                raise CommandError(
                    f"El bloque compatible {existente.pk} no pertenece al poblador; no se reutilizó."
                )
            return existente, False
        return BloqueHorario.objects.get_or_create(
            organizacion=escenario["organizacion"],
            disciplina=disciplina,
            nombre=f"{MARCADOR} {escenario['bloque_nombre']}",
            defaults={
                "dia_semana": escenario["dia_semana"],
                "hora_inicio": escenario["hora_inicio"],
                "hora_fin": escenario["hora_fin"],
            },
        )

    def _aplicar_escenarios(self, escenarios, anio, mes, fecha_corte):
        conteos = {
            "sesiones_creadas": 0,
            "sesiones_actualizadas": 0,
            "sesiones_omitidas_por_conflicto": 0,
            "asistencias_creadas": 0,
            "asistencias_actualizadas": 0,
            "asistencias_eliminadas": 0,
            "matriculas_creadas": 0,
            "bloques_creados": 0,
        }
        detalle = []
        for escenario in escenarios:
            disciplina = escenario["disciplina"]
            asignacion = AsignacionProfesorDisciplina.objects.filter(
                disciplina=disciplina,
                profesor=escenario["profesor"],
            ).first()
            if asignacion and not asignacion.activa:
                raise CommandError(
                    "Existe una asignación inactiva ajena al poblador; no se reactivó automáticamente."
                )
            if asignacion is None:
                asignacion = AsignacionProfesorDisciplina.objects.create(
                    disciplina=disciplina,
                    profesor=escenario["profesor"],
                    activa=True,
                    origen=AsignacionProfesorDisciplina.Origen.EXPLICITA,
                )
            bloque, bloque_creado = self._bloque(escenario)
            conteos["bloques_creados"] += int(bloque_creado)

            for estudiante in escenario["estudiantes"]:
                matricula = AlumnoDisciplina.objects.filter(
                    disciplina=disciplina,
                    alumno=estudiante,
                ).first()
                if matricula and not matricula.activa:
                    raise CommandError(
                        "Existe una matrícula inactiva ajena al poblador; no se reactivó automáticamente."
                    )
                creada = matricula is None
                if creada:
                    AlumnoDisciplina.objects.create(
                        disciplina=disciplina,
                        alumno=estudiante,
                        activa=True,
                        origen=AlumnoDisciplina.Origen.EXPLICITA,
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
                if fecha > fecha_corte:
                    estado, cantidad = SesionClase.Estado.PROGRAMADA, 0
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

                estudiantes_esperados = escenario["estudiantes"][:cantidad]
                esperados_ids = {estudiante.pk for estudiante in estudiantes_esperados}
                obsoletas = Asistencia.objects.filter(
                    sesion=sesion,
                    comentario__contains=MARCADOR,
                ).exclude(persona_id__in=esperados_ids)
                conteos["asistencias_eliminadas"] += obsoletas.count()
                obsoletas.delete()
                for posicion, estudiante in enumerate(estudiantes_esperados):
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

    def _plan_pruebas(self, organizacion, anio, mes):
        nombre = f"Plan sintético {anio}-{mes:02d}"
        plan = PaymentPlan.objects.filter(organizacion=organizacion, nombre=nombre).first()
        if plan and MARCADOR not in plan.descripcion:
            raise CommandError(f"El plan {nombre} ya existe sin el marcador de datos de prueba.")
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        if plan:
            plan.num_clases = 4
            plan.precio = Decimal("40000")
            plan.precio_incluye_iva = False
            plan.fecha_inicio = date(anio, mes, 1)
            plan.fecha_fin = date(anio, mes, ultimo_dia)
            plan.descripcion = f"{MARCADOR} Plan sintético mensual para validación visual."
            plan.activo = True
            plan.save()
            return plan, False
        return PaymentPlan.objects.create(
            organizacion=organizacion,
            nombre=nombre,
            num_clases=4,
            precio=Decimal("40000"),
            precio_incluye_iva=False,
            fecha_inicio=date(anio, mes, 1),
            fecha_fin=date(anio, mes, ultimo_dia),
            descripcion=f"{MARCADOR} Plan sintético mensual para validación visual.",
            activo=True,
        ), True

    def _fecha_pago(self, anio, mes, posicion):
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        return date(anio, mes, min(5 + posicion * 3, ultimo_dia))

    def _aplicar_pagos(self, escenarios, anio, mes, fecha_corte):
        conteos = {
            "planes_creados": 0,
            "pagos_creados": 0,
            "pagos_existentes": 0,
            "deudas_imputadas": 0,
        }
        planes = {}
        clases_variadas = (2, 4, 6, 3, 8, 1)
        montos_variados = (20000, 40000, 60000, 30000, 80000, 10000)
        metodos = (
            Payment.Metodo.TRANSFERENCIA,
            Payment.Metodo.EFECTIVO,
            Payment.Metodo.TARJETA,
            Payment.Metodo.OTRO,
        )
        claves_esperadas = set()

        for escenario in escenarios:
            organizacion = escenario["organizacion"]
            if organizacion.pk not in planes:
                plan, creado = self._plan_pruebas(organizacion, anio, mes)
                planes[organizacion.pk] = plan
                conteos["planes_creados"] += int(creado)
            plan = planes[organizacion.pk]

            for posicion, estudiante in enumerate(escenario["estudiantes"][:6]):
                fecha_pago = self._fecha_pago(anio, mes, posicion)
                if fecha_pago > fecha_corte:
                    continue
                clave = f"datos-prueba-{anio}-{mes:02d}-{escenario['codigo']}-{estudiante.pk}"
                claves_esperadas.add(clave)
                existente = Payment.objects.filter(clave_idempotencia=clave).first()
                if existente:
                    valores_esperados = {
                        "organizacion_id": organizacion.pk,
                        "persona_id": estudiante.pk,
                        "plan_id": plan.pk,
                        "disciplina_id": escenario["disciplina"].pk,
                        "fecha_pago": fecha_pago,
                        "metodo_pago": metodos[posicion % len(metodos)],
                        "monto_referencia": Decimal(montos_variados[posicion]),
                        "clases_asignadas": clases_variadas[posicion],
                    }
                    divergentes = [
                        campo
                        for campo, esperado in valores_esperados.items()
                        if getattr(existente, campo) != esperado
                    ]
                    if divergentes:
                        raise CommandError(
                            f"El pago sintético {clave} fue modificado ({', '.join(divergentes)}); "
                            "no se sobrescribió."
                        )
                    pago = existente
                    conteos["pagos_existentes"] += 1
                else:
                    pago = crear_pago_operacional(
                        pago=Payment(
                            persona=estudiante,
                            organizacion=organizacion,
                            plan=plan,
                            disciplina=escenario["disciplina"],
                            fecha_pago=fecha_pago,
                            metodo_pago=metodos[posicion % len(metodos)],
                            aplica_iva=not organizacion.es_exenta_iva,
                            monto_referencia=Decimal(montos_variados[posicion]),
                            clases_asignadas=clases_variadas[posicion],
                            observaciones=f"{MARCADOR} Pago sintético {escenario['codigo']}.",
                        ),
                        origen="poblador_mes_pruebas",
                        clave_idempotencia=clave,
                    )
                    conteos["pagos_creados"] += 1
                conteos["deudas_imputadas"] += imputar_pago_a_deudas(pago)
        prefijo = f"datos-prueba-{anio}-{mes:02d}-"
        organizaciones_ids = {escenario["organizacion"].pk for escenario in escenarios}
        sobrantes = Payment.objects.filter(
            organizacion_id__in=organizaciones_ids,
            clave_idempotencia__startswith=prefijo,
        ).exclude(clave_idempotencia__in=claves_esperadas)
        if sobrantes.exists():
            raise CommandError(
                "Existen pagos sintéticos del período fuera del escenario o posteriores a la fecha de corte; "
                "no se eliminaron automáticamente."
            )
        return conteos
