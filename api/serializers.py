from rest_framework import serializers

from database.models import Asistencia, Persona, SesionClase

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
        fields = ["persona", "estado"]


class EstudianteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Persona
        fields = ["id", "nombres", "apellidos", "email"]


class EstadoEstudianteSerializer(serializers.Serializer):
    persona = EstudianteSerializer()
    asistencias_total = serializers.IntegerField()
    asistencias_mes = serializers.IntegerField()
    ultima_asistencia = serializers.DateField(allow_null=True)
