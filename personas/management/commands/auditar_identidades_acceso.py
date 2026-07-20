from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from personas.models import Persona, PersonaRol


PATRONES_CUENTA_TECNICA = ("admin", "api", "bot", "deploy", "service", "sistema", "system", "test")


def normalizar_email(valor):
    return (valor or "").strip().lower()


def enmascarar_email(valor):
    email = normalizar_email(valor)
    if not email:
        return "-"
    usuario, separador, dominio = email.partition("@")
    if not separador:
        return "***"
    inicio = usuario[:1] or "*"
    return f"{inicio}***@{dominio}"


class Command(BaseCommand):
    help = "Audita identidades User/Persona/Roles sin modificar datos ni mostrar correos completos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=20,
            help="Maximo de IDs por grupo informado (por defecto: 20).",
        )

    def handle(self, *args, **options):
        limite = max(options["limite"], 1)
        User = get_user_model()
        usuarios = list(User.objects.order_by("id"))

        sin_email = [usuario for usuario in usuarios if not normalizar_email(usuario.email)]
        inactivos = [usuario for usuario in usuarios if not usuario.is_active]
        superusuarios = [usuario for usuario in usuarios if usuario.is_superuser]
        candidatos_tecnicos = [
            usuario
            for usuario in usuarios
            if usuario.is_staff
            or usuario.is_superuser
            or any(patron in (usuario.username or "").lower() for patron in PATRONES_CUENTA_TECNICA)
        ]

        usuarios_por_email = defaultdict(list)
        for usuario in usuarios:
            email = normalizar_email(usuario.email)
            if email:
                usuarios_por_email[email].append(usuario)
        emails_duplicados = {
            email: grupo for email, grupo in usuarios_por_email.items() if len(grupo) > 1
        }

        usuarios_por_id = {usuario.id: usuario for usuario in usuarios}
        personas_por_usuario = {
            persona.user_id: persona
            for persona in Persona.objects.select_related("user").exclude(user__isnull=True)
        }
        usuarios_sin_persona = [usuario for usuario in usuarios if usuario.id not in personas_por_usuario]
        personas_sin_usuario = list(Persona.objects.filter(user__isnull=True).order_by("id"))
        email_diferente = [
            (usuarios_por_id[usuario_id], persona)
            for usuario_id, persona in personas_por_usuario.items()
            if normalizar_email(usuarios_por_id[usuario_id].email)
            and normalizar_email(persona.email)
            and normalizar_email(usuarios_por_id[usuario_id].email) != normalizar_email(persona.email)
        ]

        roles_por_usuario = defaultdict(list)
        for persona_rol in (
            PersonaRol.objects.filter(activo=True, persona__user__isnull=False)
            .select_related("persona__user", "rol", "organizacion")
            .order_by("persona__user_id", "organizacion_id", "rol_id")
        ):
            roles_por_usuario[persona_rol.persona.user_id].append(
                f"rol={persona_rol.rol_id}/org={persona_rol.organizacion_id}"
            )

        self.stdout.write("Auditoria read-only de identidades y accesos")
        self.stdout.write("============================================")
        self.stdout.write(f"Usuarios revisados: {len(usuarios)}")
        self._imprimir_usuarios("Users sin email", sin_email, limite)
        self._imprimir_duplicados(emails_duplicados, limite)
        self._imprimir_diferencias(email_diferente, limite)
        self._imprimir_usuarios("Users sin Persona", usuarios_sin_persona, limite)
        self._imprimir_ids("Personas sin User", [persona.id for persona in personas_sin_usuario], limite)
        self._imprimir_usuarios("Usuarios inactivos", inactivos, limite)
        self._imprimir_usuarios("Superusuarios", superusuarios, limite)
        self._imprimir_usuarios(
            "Candidatos a cuenta tecnica (heuristica por staff/superuser/username)",
            candidatos_tecnicos,
            limite,
        )
        self.stdout.write(f"Users con PersonaRol activo: {len(roles_por_usuario)}")
        for usuario_id, roles in list(roles_por_usuario.items())[:limite]:
            self.stdout.write(f"  User {usuario_id}: {', '.join(roles)}")
        if len(roles_por_usuario) > limite:
            self.stdout.write("  ...")
        self.stdout.write(self.style.SUCCESS("No se modificaron datos."))

    def _imprimir_usuarios(self, titulo, usuarios, limite):
        self._imprimir_ids(titulo, [usuario.id for usuario in usuarios], limite)

    def _imprimir_ids(self, titulo, ids, limite):
        muestra = ", ".join(str(item) for item in ids[:limite]) or "-"
        if len(ids) > limite:
            muestra = f"{muestra}, ..."
        self.stdout.write(f"{titulo}: {len(ids)}")
        self.stdout.write(f"  IDs: {muestra}")

    def _imprimir_duplicados(self, emails_duplicados, limite):
        self.stdout.write(f"Emails User duplicados (trim/lower): {len(emails_duplicados)} grupos")
        for email, grupo in list(emails_duplicados.items())[:limite]:
            ids = ", ".join(str(usuario.id) for usuario in grupo)
            self.stdout.write(f"  {enmascarar_email(email)}: Users {ids}")
        if len(emails_duplicados) > limite:
            self.stdout.write("  ...")

    def _imprimir_diferencias(self, diferencias, limite):
        self.stdout.write(f"User.email distinto de Persona.email: {len(diferencias)}")
        for usuario, persona in diferencias[:limite]:
            self.stdout.write(
                f"  User {usuario.id} ({enmascarar_email(usuario.email)}) / "
                f"Persona {persona.id} ({enmascarar_email(persona.email)})"
            )
        if len(diferencias) > limite:
            self.stdout.write("  ...")
