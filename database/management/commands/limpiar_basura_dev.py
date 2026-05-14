from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = "Audita y limpia basura interna segura de la base de desarrollo."

    SAFE_MODELS = (LogEntry, Session)

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra lo que se borraria sin modificar datos.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Borra solo admin.LogEntry y django sessions.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        apply = options["apply"]
        if dry_run and apply:
            raise CommandError("Usa solo una opcion: --dry-run o --apply.")
        if not dry_run and not apply:
            dry_run = True

        table_counts = self._table_counts()
        active_tables = self._active_model_tables()
        stale_contenttypes = self._stale_contenttypes()
        stale_contenttype_ids = [content_type.pk for content_type in stale_contenttypes]
        stale_permissions = Permission.objects.filter(content_type_id__in=stale_contenttype_ids).select_related(
            "content_type"
        )

        self.stdout.write("Base de datos configurada:")
        self.stdout.write(f"- engine: {connection.vendor}")
        self.stdout.write(f"- name: {connection.settings_dict.get('NAME')}")
        self.stdout.write("")

        self._write_tables(table_counts, active_tables)
        self._write_stale_contenttypes(stale_contenttypes, stale_permissions)

        self.stdout.write("")
        self.stdout.write("Limpieza segura propuesta:")
        for model in self.SAFE_MODELS:
            self.stdout.write(f"- {model._meta.label}: {model.objects.count()} registros")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se borro ningun registro."))
            return

        with transaction.atomic():
            deleted_log_entries, _ = LogEntry.objects.all().delete()
            deleted_sessions, _ = Session.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Limpieza aplicada."))
        self.stdout.write(f"- admin.LogEntry eliminados: {deleted_log_entries}")
        self.stdout.write(f"- sessions.Session eliminadas: {deleted_sessions}")

    def _table_counts(self):
        with connection.cursor() as cursor:
            tables = sorted(connection.introspection.table_names(cursor))
            counts = {}
            for table in tables:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                counts[table] = cursor.fetchone()[0]
        return counts

    def _active_model_tables(self):
        return {model._meta.db_table for model in apps.get_models(include_auto_created=True)}

    def _stale_contenttypes(self):
        stale = []
        for content_type in ContentType.objects.order_by("app_label", "model"):
            try:
                apps.get_model(content_type.app_label, content_type.model)
            except LookupError:
                stale.append(content_type)
        return stale

    def _classify_table(self, table, active_tables):
        safe_tables = {model._meta.db_table for model in self.SAFE_MODELS}
        regenerable_tables = {
            ContentType._meta.db_table,
            Permission._meta.db_table,
            "django_migrations",
        }
        protected_auth_tables = {
            User._meta.db_table,
            Group._meta.db_table,
            User.groups.through._meta.db_table,
            User.user_permissions.through._meta.db_table,
            Group.permissions.through._meta.db_table,
            Token._meta.db_table,
        }

        if table in safe_tables:
            return "Django interna segura de limpiar"
        if table in regenerable_tables:
            return "Django interna/regenerable; no borrar automaticamente"
        if table in protected_auth_tables:
            return "Django auth funcional; NO tocar"
        if table in active_tables:
            return "Dato funcional/modelo activo; NO tocar"
        return "Sospechosa u obsoleta; requiere confirmacion"

    def _write_tables(self, table_counts, active_tables):
        self.stdout.write("Tablas y conteos:")
        for table, count in table_counts.items():
            clasificacion = self._classify_table(table, active_tables)
            self.stdout.write(f"- {table}: {count} | {clasificacion}")

    def _write_stale_contenttypes(self, stale_contenttypes, stale_permissions):
        self.stdout.write("")
        self.stdout.write("ContentTypes obsoletos detectados:")
        if not stale_contenttypes:
            self.stdout.write("- ninguno")
        for content_type in stale_contenttypes:
            self.stdout.write(f"- {content_type.pk}: {content_type.app_label}.{content_type.model}")

        self.stdout.write("")
        self.stdout.write("Permisos asociados a ContentTypes obsoletos:")
        self.stdout.write(f"- total: {stale_permissions.count()}")
        self.stdout.write("- no se eliminan automaticamente en esta version")
