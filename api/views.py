from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from database.models import Asistencia, Persona, SesionClase

from .serializers import (
    AsistenciaCreateSerializer,
    AsistenciaSerializer,
    EstudianteSerializer,
    SesionSerializer,
    EstadoEstudianteSerializer,
)

User = get_user_model()


class HealthCheckView(APIView):
    """
    Minimal endpoint to check service availability without requiring auth.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        payload = {
            "status": "ok",
            "timestamp": timezone.now(),
        }
        return Response(payload, status=status.HTTP_200_OK)


class AuthenticationViewSet(viewsets.ViewSet):
    """
    Token-based authentication workflow using DRF TokenAuthentication.
    """

    def get_permissions(self):
        if self.action == "login":
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def _build_user_payload(self, user):
        return {
            "id": user.pk,
            "username": user.get_username(),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }

    def _rotate_token(self, user):
        Token.objects.filter(user=user).delete()
        return Token.objects.create(user=user)

    def _unauthorized_response(self):
        return Response(
            {"detail": "Credenciales invalidas."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    @action(detail=False, methods=["post"], url_path="login")
    def login(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email")

        if not password:
            raise ValidationError({"password": "La contrasena es obligatoria."})

        if not username and email:
            try:
                username = User.objects.get(email=email).get_username()
            except User.DoesNotExist:
                return self._unauthorized_response()

        if not username:
            raise ValidationError({"username": "Debes indicar usuario o email."})

        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            return self._unauthorized_response()

        token = self._rotate_token(user)
        payload = {
            "token": token.key,
            "user": self._build_user_payload(user),
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="refresh")
    def refresh(self, request):
        if request.auth is None:
            return Response(
                {"detail": "Token no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        new_token = self._rotate_token(request.user)
        return Response(
            {"token": new_token.key},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        token = request.auth
        if token:
            token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SesionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SesionClase.objects.select_related("disciplina").prefetch_related("profesores").order_by("-fecha")
    serializer_class = SesionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        fecha = self.request.query_params.get("fecha")
        if fecha:
            qs = qs.filter(fecha=fecha)
        return qs

    @action(detail=True, methods=["get", "post"])
    def asistencias(self, request, pk=None):
        sesion = self.get_object()
        if request.method == "GET":
            data = AsistenciaSerializer(
                Asistencia.objects.filter(sesion=sesion).select_related("persona"),
                many=True,
            ).data
            return Response(data)
        serializer = AsistenciaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        persona = payload.pop("persona")
        asistencia, _ = Asistencia.objects.update_or_create(
            sesion=sesion,
            persona=persona,
            defaults=payload,
        )
        return Response(AsistenciaSerializer(asistencia).data, status=status.HTTP_201_CREATED)


class EstudianteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EstudianteSerializer

    def get_queryset(self):
        return Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct()

    @action(detail=True, methods=["get"], url_path="estado")
    def estado(self, request, pk=None):
        persona = self.get_object()
        asistencias = Asistencia.objects.filter(persona=persona).select_related("sesion").order_by("-sesion__fecha")
        ultima_asistencia = asistencias.first()
        data = {
            "persona": EstudianteSerializer(persona).data,
            "asistencias_total": asistencias.count(),
            "asistencias_mes": asistencias.filter(
                sesion__fecha__month=timezone.localdate().month,
                sesion__fecha__year=timezone.localdate().year,
            ).count(),
            "ultima_asistencia": ultima_asistencia.sesion.fecha if ultima_asistencia else None,
        }
        serializer = EstadoEstudianteSerializer(data)
        return Response(serializer.data)


class ReporteResumenView(APIView):
    def get(self, request):
        total_sesiones = SesionClase.objects.count()
        total_asistencias = Asistencia.objects.count()
        total_estudiantes = Persona.objects.filter(roles__rol__codigo="ESTUDIANTE").distinct().count()
        return Response(
            {
                "total_sesiones": total_sesiones,
                "total_asistencias": total_asistencias,
                "total_estudiantes": total_estudiantes,
            }
        )
