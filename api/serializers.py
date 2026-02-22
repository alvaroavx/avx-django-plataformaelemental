from rest_framework import serializers

from academia.models import SesionClase
from asistencias.models import Asistencia
from cuentas.models import Persona


class DisciplinaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class SesionSerializer(serializers.ModelSerializer):
    disciplina = serializers.StringRelatedField()
    profesores = serializers.StringRelatedField(many=True)

    class Meta:
        model = SesionClase
        fields = ["id", "fecha", "disciplina", "profesores", "estado", "cupo_maximo", "notas"]


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
    clases_total = serializers.IntegerField()
    clases_usadas = serializers.IntegerField()
    clases_restantes = serializers.IntegerField()
    pendientes = serializers.IntegerField()

