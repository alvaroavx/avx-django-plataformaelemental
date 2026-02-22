from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from django.db.models import Sum, Q
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from academia.models import SesionClase
from asistencias.models import Asistencia
from cobros.models import Pago
from cuentas.models import Persona
from finanzas.models import MovimientoCaja

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
        if asistencia.pago_plan_id is None:
            pago_plan = Pago.asignar_plan_para_asistencia(persona, sesion.fecha)
            if pago_plan:
                asistencia.pago_plan = pago_plan
                asistencia.save(update_fields=["pago_plan"])
        return Response(AsistenciaSerializer(asistencia).data, status=status.HTTP_201_CREATED)


class EstudianteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EstudianteSerializer

    def get_queryset(self):
        return Persona.objects.filter(
            Q(roles__rol__codigo="ESTUDIANTE") | Q(pagos__plan__isnull=False)
        ).distinct()

    @action(detail=True, methods=["get"], url_path="estado")
    def estado(self, request, pk=None):
        persona = self.get_object()
        hoy = timezone.localdate()
        pagos_plan = list(
            persona.pagos.filter(tipo=Pago.Tipo.PLAN)
            .select_related("plan")
            .filter(plan__isnull=False)
            .order_by("-fecha_pago")
        )
        pago_activo = next((p for p in pagos_plan if p.vigente_en(hoy)), None)
        if not pago_activo:
            return Response({"detail": "Sin pago de plan vigente"}, status=status.HTTP_404_NOT_FOUND)
        asistencias = Asistencia.objects.filter(persona=persona, sesion__fecha__gte=pago_activo.fecha_pago)
        pagos_clase_ids = set(
            Pago.objects.filter(
                persona=persona,
                tipo=Pago.Tipo.CLASE,
                sesion__fecha__gte=pago_activo.fecha_pago,
            ).values_list("sesion_id", flat=True)
        )
        pendientes = asistencias.filter(pago_plan__isnull=True).exclude(
            sesion_id__in=pagos_clase_ids
        ).count()
        data = {
            "persona": EstudianteSerializer(persona).data,
            "plan": str(pago_activo.plan),
            "clases_total": pago_activo.clases_total or 0,
            "clases_usadas": pago_activo.clases_usadas or 0,
            "clases_restantes": pago_activo.clases_restantes(),
            "pendientes": pendientes,
        }
        serializer = EstadoEstudianteSerializer(data)
        return Response(serializer.data)


class ReporteResumenView(APIView):
    def get(self, request):
        total_sesiones = SesionClase.objects.count()
        total_asistencias = Asistencia.objects.count()
        ingresos = MovimientoCaja.objects.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(total=Sum("monto_total"))["total"] or 0
        egresos = MovimientoCaja.objects.filter(tipo=MovimientoCaja.Tipo.EGRESO).aggregate(total=Sum("monto_total"))["total"] or 0
        return Response(
            {
                "total_sesiones": total_sesiones,
                "total_asistencias": total_asistencias,
                "ingresos": ingresos,
                "egresos": egresos,
            }
        )
