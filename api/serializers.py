from rest_framework import serializers

from asistencias.models import Asistencia, Disciplina, SesionClase
from finanzas.models import DocumentoTributario, Payment, PaymentPlan, Transaction
from personas.models import Organizacion, Persona, PersonaRol


class DisciplinaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class OrganizacionApiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organizacion
        fields = [
            "id",
            "nombre",
            "razon_social",
            "rut",
            "es_exenta_iva",
            "email_contacto",
            "telefono_contacto",
            "direccion",
        ]


class PersonaApiSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = Persona
        fields = [
            "id",
            "nombres",
            "apellidos",
            "nombre_completo",
            "email",
            "telefono",
            "identificador",
            "activo",
            "roles",
        ]

    def get_roles(self, obj):
        roles = (
            PersonaRol.objects.filter(persona=obj, activo=True)
            .select_related("rol", "organizacion")
            .order_by("organizacion__nombre", "rol__nombre")
        )
        return [
            {
                "rol": item.rol.codigo,
                "rol_nombre": item.rol.nombre,
                "organizacion_id": item.organizacion_id,
                "organizacion_nombre": item.organizacion.nombre,
            }
            for item in roles
        ]


class SesionSerializer(serializers.ModelSerializer):
    disciplina = serializers.StringRelatedField()
    profesores = serializers.StringRelatedField(many=True)

    class Meta:
        model = SesionClase
        fields = ["id", "fecha", "disciplina", "profesores", "estado", "cupo_maximo", "notas"]


class SesionApiSerializer(serializers.ModelSerializer):
    disciplina = serializers.CharField(source="disciplina.nombre", read_only=True)
    disciplina_id = serializers.IntegerField(read_only=True)
    organizacion_id = serializers.IntegerField(source="disciplina.organizacion_id", read_only=True)
    profesores = PersonaApiSerializer(many=True, read_only=True)
    total_asistencias = serializers.IntegerField(read_only=True)

    class Meta:
        model = SesionClase
        fields = [
            "id",
            "fecha",
            "estado",
            "disciplina_id",
            "disciplina",
            "organizacion_id",
            "profesores",
            "cupo_maximo",
            "notas",
            "total_asistencias",
        ]


class AsistenciaSerializer(serializers.ModelSerializer):
    persona = serializers.StringRelatedField()

    class Meta:
        model = Asistencia
        fields = ["id", "persona", "estado", "registrada_en"]


class AsistenciaApiSerializer(serializers.ModelSerializer):
    persona = PersonaApiSerializer(read_only=True)
    sesion_id = serializers.IntegerField(read_only=True)
    sesion_fecha = serializers.DateField(source="sesion.fecha", read_only=True)
    disciplina = serializers.CharField(source="sesion.disciplina.nombre", read_only=True)

    class Meta:
        model = Asistencia
        fields = [
            "id",
            "sesion_id",
            "sesion_fecha",
            "disciplina",
            "persona",
            "estado",
            "comentario",
            "registrada_en",
        ]


class AsistenciaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asistencia
        fields = ["persona", "estado", "comentario"]


class EstudianteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Persona
        fields = ["id", "nombres", "apellidos", "email"]


class EstadoEstudianteSerializer(serializers.Serializer):
    persona = EstudianteSerializer()
    asistencias_total = serializers.IntegerField()
    asistencias_mes = serializers.IntegerField()
    ultima_asistencia = serializers.DateField(allow_null=True)


class PlanPagoApiSerializer(serializers.ModelSerializer):
    organizacion = OrganizacionApiSerializer(read_only=True)

    class Meta:
        model = PaymentPlan
        fields = [
            "id",
            "organizacion",
            "nombre",
            "num_clases",
            "precio",
            "precio_incluye_iva",
            "es_por_defecto",
            "fecha_inicio",
            "fecha_fin",
            "descripcion",
            "activo",
        ]


class PagoApiSerializer(serializers.ModelSerializer):
    persona = PersonaApiSerializer(read_only=True)
    organizacion = OrganizacionApiSerializer(read_only=True)
    plan = PlanPagoApiSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "persona",
            "organizacion",
            "plan",
            "fecha_pago",
            "metodo_pago",
            "numero_comprobante",
            "aplica_iva",
            "monto_incluye_iva",
            "monto_neto",
            "monto_iva",
            "monto_total",
            "clases_asignadas",
            "observaciones",
        ]


class DocumentoTributarioApiSerializer(serializers.ModelSerializer):
    organizacion = OrganizacionApiSerializer(read_only=True)
    tipo_documento_display = serializers.CharField(source="get_tipo_documento_display", read_only=True)

    class Meta:
        model = DocumentoTributario
        fields = [
            "id",
            "organizacion",
            "tipo_documento",
            "tipo_documento_display",
            "fuente",
            "folio",
            "fecha_emision",
            "nombre_emisor",
            "rut_emisor",
            "nombre_receptor",
            "rut_receptor",
            "monto_neto",
            "monto_exento",
            "iva_tasa",
            "monto_iva",
            "retencion_tasa",
            "retencion_monto",
            "monto_total",
            "observaciones",
            "enlace_sii",
        ]


class TransaccionApiSerializer(serializers.ModelSerializer):
    organizacion = OrganizacionApiSerializer(read_only=True)
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "organizacion",
            "fecha",
            "tipo",
            "categoria_id",
            "categoria_nombre",
            "monto",
            "descripcion",
        ]
