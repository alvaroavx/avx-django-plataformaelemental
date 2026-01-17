from rest_framework import serializers

from academia.models import SesionClase
from asistencias.models import Asistencia
from cobros.models import Suscripcion
from cuentas.models import Persona


class DisciplinaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class SesionSerializer(serializers.ModelSerializer):
    disciplina = serializers.StringRelatedField()
    profesor = serializers.StringRelatedField()
    profesores = serializers.StringRelatedField(many=True)

    class Meta:
        model = SesionClase
        fields = ["id", "fecha", "disciplina", "profesor", "profesores", "estado", "cupo_maximo", "notas"]


class AsistenciaSerializer(serializers.ModelSerializer):
    persona = serializers.StringRelatedField()

    class Meta:
        model = Asistencia
        fields = ["id", "persona", "estado", "registrada_en"]


class AsistenciaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asistencia
        fields = ["persona", "estado", "convenio"]


class EstudianteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Persona
        fields = ["id", "nombres", "apellidos", "email"]


class EstadoEstudianteSerializer(serializers.Serializer):
    persona = EstudianteSerializer()
    plan = serializers.CharField()
    clases_asignadas = serializers.IntegerField()
    clases_usadas = serializers.IntegerField()
    clases_sobreconsumo = serializers.IntegerField()
    saldo_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2)


class SuscripcionSerializer(serializers.ModelSerializer):
    plan = serializers.StringRelatedField()

    class Meta:
        model = Suscripcion
        fields = ["id", "plan", "fecha_inicio", "fecha_fin", "estado"]
