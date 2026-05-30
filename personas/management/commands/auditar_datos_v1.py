from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import Lower

from personas.models import Persona
from personas.utils import normalizar_telefono, tiene_identidad_minima


def _muestra_ids(ids, limite=20):
    ids = list(ids)
    texto = ", ".join(str(item) for item in ids[:limite])
    if len(ids) > limite:
        texto = f"{texto}, ..."
    return texto or "-"


def _normalizar_nombre(persona):
    return " ".join(f"{persona.nombres} {persona.apellidos}".lower().split())


class Command(BaseCommand):
    help = "Audita datos existentes de personas para preparar reglas v1.0 sin modificar la base."

    def handle(self, *args, **options):
        personas = list(Persona.objects.order_by("id"))
        sin_identidad = [
            persona.id
            for persona in personas
            if not tiene_identidad_minima(
                rut=persona.rut,
                email=persona.email,
                telefono=persona.telefono,
            )
        ]

        rut_duplicados = list(
            Persona.objects.exclude(rut="")
            .values("rut")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("rut")
        )
        email_duplicados = list(
            Persona.objects.exclude(email__isnull=True)
            .exclude(email="")
            .annotate(email_normalizado=Lower("email"))
            .values("email_normalizado")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("email_normalizado")
        )

        telefonos = defaultdict(list)
        telefonos_inconsistentes = []
        nombres = defaultdict(list)
        for persona in personas:
            telefono_normalizado = normalizar_telefono(persona.telefono)
            if telefono_normalizado:
                telefonos[telefono_normalizado].append(persona.id)
            if persona.telefono and persona.telefono != telefono_normalizado:
                telefonos_inconsistentes.append(persona.id)
            nombre_normalizado = _normalizar_nombre(persona)
            if nombre_normalizado:
                nombres[nombre_normalizado].append(persona.id)

        telefonos_duplicados = {
            telefono: ids for telefono, ids in sorted(telefonos.items()) if len(ids) > 1
        }
        posibles_duplicados = {
            nombre: ids for nombre, ids in sorted(nombres.items()) if len(ids) > 1
        }

        self.stdout.write("Auditoria datos v1.0")
        self.stdout.write("====================")
        self.stdout.write(f"Personas revisadas: {len(personas)}")
        self.stdout.write("")

        self._imprimir_critico(
            "Personas sin RUT, email ni telefono",
            len(sin_identidad),
            f"IDs: {_muestra_ids(sin_identidad)}",
        )
        self._imprimir_grupos("RUT duplicados", rut_duplicados, "rut", criticidad="CRITICO")
        self._imprimir_grupos(
            "Emails duplicados",
            email_duplicados,
            "email_normalizado",
            criticidad="ADVERTENCIA",
        )
        self._imprimir_diccionario(
            "Telefonos duplicados",
            telefonos_duplicados,
            criticidad="ADVERTENCIA",
        )
        self._imprimir_critico(
            "Telefonos con formato inconsistente",
            len(telefonos_inconsistentes),
            f"IDs: {_muestra_ids(telefonos_inconsistentes)}",
            criticidad="ADVERTENCIA",
        )
        self._imprimir_diccionario(
            "Potenciales duplicados por nombre",
            posibles_duplicados,
            criticidad="ADVERTENCIA",
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("No se modificaron datos."))

    def _imprimir_critico(self, titulo, total, detalle, *, criticidad="CRITICO"):
        self.stdout.write(f"[{criticidad}] {titulo}: {total}")
        self.stdout.write(f"  {detalle}")

    def _imprimir_grupos(self, titulo, grupos, campo, *, criticidad):
        self.stdout.write(f"[{criticidad}] {titulo}: {len(grupos)} grupos")
        for grupo in grupos[:20]:
            self.stdout.write(f"  {grupo[campo]}: {grupo['total']} registros")
        if len(grupos) > 20:
            self.stdout.write("  ...")

    def _imprimir_diccionario(self, titulo, grupos, *, criticidad):
        self.stdout.write(f"[{criticidad}] {titulo}: {len(grupos)} grupos")
        for clave, ids in list(grupos.items())[:20]:
            self.stdout.write(f"  {clave}: IDs {_muestra_ids(ids)}")
        if len(grupos) > 20:
            self.stdout.write("  ...")
