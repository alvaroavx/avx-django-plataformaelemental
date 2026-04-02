from django.contrib.auth import authenticate, get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from asistencias.models import Asistencia, Disciplina, SesionClase
from finanzas.models import DocumentoTributario, Payment, PaymentPlan, Transaction
from personas.models import Organizacion, Persona

from .serializers import (
    AsistenciaApiSerializer,
    AsistenciaCreateSerializer,
    AsistenciaSerializer,
    DisciplinaSerializer,
    DocumentoTributarioApiSerializer,
    EstadoEstudianteSerializer,
    EstudianteSerializer,
    OrganizacionApiSerializer,
    PagoApiSerializer,
    PersonaApiSerializer,
    PlanPagoApiSerializer,
    SesionApiSerializer,
    SesionSerializer,
    TransaccionApiSerializer,
)
from .throttles import AuthBurstRateThrottle, AuthSustainedRateThrottle

User = get_user_model()


def _entero_query(request, nombre):
    valor = request.query_params.get(nombre)
    if valor in (None, ""):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValidationError({nombre: "Debe ser un entero valido."})


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "timestamp": timezone.now(),
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        persona = getattr(request.user, "persona", None)
        return Response(
            {
                "user": {
                    "id": request.user.pk,
                    "username": request.user.get_username(),
                    "email": request.user.email,
                    "first_name": request.user.first_name,
                    "last_name": request.user.last_name,
                },
                "persona": PersonaApiSerializer(persona).data if persona else None,
            }
        )


class AuthenticationViewSet(viewsets.ViewSet):
    throttle_classes = [AuthBurstRateThrottle, AuthSustainedRateThrottle]

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
        return Response(
            {
                "token": token.key,
                "user": self._build_user_payload(user),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="refresh")
    def refresh(self, request):
        if request.auth is None:
            return Response(
                {"detail": "Token no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        new_token = self._rotate_token(request.user)
        return Response({"token": new_token.key}, status=status.HTTP_200_OK)

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


class OrganizacionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organizacion.objects.order_by("nombre")
    serializer_class = OrganizacionApiSerializer


class PersonaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PersonaApiSerializer

    def get_queryset(self):
        qs = Persona.objects.all().order_by("apellidos", "nombres")
        organizacion = _entero_query(self.request, "organizacion")
        rol = self.request.query_params.get("rol")
        buscar = self.request.query_params.get("buscar", "").strip()

        if organizacion:
            qs = qs.filter(roles__organizacion_id=organizacion, roles__activo=True)
        if rol:
            qs = qs.filter(roles__rol__codigo__iexact=rol, roles__activo=True)
        if buscar:
            qs = qs.filter(
                Q(nombres__icontains=buscar)
                | Q(apellidos__icontains=buscar)
                | Q(email__icontains=buscar)
                | Q(identificador__icontains=buscar)
            )
        return qs.distinct()


class PersonasResumenView(APIView):
    def get(self, request):
        organizacion = _entero_query(request, "organizacion")
        personas = Persona.objects.all()
        if organizacion:
            personas = personas.filter(roles__organizacion_id=organizacion, roles__activo=True)
        return Response(
            {
                "total_personas": personas.distinct().count(),
                "total_estudiantes": personas.filter(roles__rol__codigo="ESTUDIANTE", roles__activo=True).distinct().count(),
                "total_profesores": personas.filter(roles__rol__codigo="PROFESOR", roles__activo=True).distinct().count(),
            }
        )


class DisciplinaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DisciplinaSerializer

    def get_queryset(self):
        qs = Disciplina.objects.order_by("nombre")
        organizacion = _entero_query(self.request, "organizacion")
        if organizacion:
            qs = qs.filter(organizacion_id=organizacion)
        if self.request.query_params.get("activa") == "true":
            qs = qs.filter(activa=True)
        return qs


class SesionBaseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SesionApiSerializer

    def get_queryset(self):
        qs = (
            SesionClase.objects.select_related("disciplina", "disciplina__organizacion")
            .prefetch_related("profesores")
            .annotate(total_asistencias=Count("asistencias"))
            .order_by("-fecha", "-id")
        )
        organizacion = _entero_query(self.request, "organizacion")
        disciplina = _entero_query(self.request, "disciplina")
        profesor = _entero_query(self.request, "profesor")
        fecha = self.request.query_params.get("fecha")
        estado = self.request.query_params.get("estado")

        if organizacion:
            qs = qs.filter(disciplina__organizacion_id=organizacion)
        if disciplina:
            qs = qs.filter(disciplina_id=disciplina)
        if profesor:
            qs = qs.filter(profesores__id=profesor)
        if fecha:
            qs = qs.filter(fecha=fecha)
        if estado:
            qs = qs.filter(estado=estado)
        return qs.distinct()

    @action(detail=True, methods=["get", "post"])
    def asistencias(self, request, pk=None):
        sesion = self.get_object()
        if request.method == "GET":
            data = AsistenciaApiSerializer(
                Asistencia.objects.filter(sesion=sesion).select_related("persona", "sesion", "sesion__disciplina"),
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
        return Response(AsistenciaApiSerializer(asistencia).data, status=status.HTTP_201_CREATED)


class AsistenciaBaseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AsistenciaApiSerializer

    def get_queryset(self):
        qs = Asistencia.objects.select_related("persona", "sesion", "sesion__disciplina").order_by("-sesion__fecha", "-id")
        organizacion = _entero_query(self.request, "organizacion")
        sesion = _entero_query(self.request, "sesion")
        persona = _entero_query(self.request, "persona")
        periodo_mes = _entero_query(self.request, "periodo_mes")
        periodo_anio = _entero_query(self.request, "periodo_anio")

        if organizacion:
            qs = qs.filter(sesion__disciplina__organizacion_id=organizacion)
        if sesion:
            qs = qs.filter(sesion_id=sesion)
        if persona:
            qs = qs.filter(persona_id=persona)
        if periodo_mes:
            qs = qs.filter(sesion__fecha__month=periodo_mes)
        if periodo_anio:
            qs = qs.filter(sesion__fecha__year=periodo_anio)
        return qs


class AsistenciasResumenView(APIView):
    def get(self, request):
        organizacion = _entero_query(request, "organizacion")
        periodo_mes = _entero_query(request, "periodo_mes")
        periodo_anio = _entero_query(request, "periodo_anio")

        sesiones = SesionClase.objects.all()
        asistencias = Asistencia.objects.all()
        if organizacion:
            sesiones = sesiones.filter(disciplina__organizacion_id=organizacion)
            asistencias = asistencias.filter(sesion__disciplina__organizacion_id=organizacion)
        if periodo_mes:
            sesiones = sesiones.filter(fecha__month=periodo_mes)
            asistencias = asistencias.filter(sesion__fecha__month=periodo_mes)
        if periodo_anio:
            sesiones = sesiones.filter(fecha__year=periodo_anio)
            asistencias = asistencias.filter(sesion__fecha__year=periodo_anio)

        return Response(
            {
                "total_sesiones": sesiones.count(),
                "total_asistencias": asistencias.count(),
                "presentes": asistencias.filter(estado="presente").count(),
            }
        )


class PlanPagoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PlanPagoApiSerializer

    def get_queryset(self):
        qs = PaymentPlan.objects.select_related("organizacion").order_by("organizacion__nombre", "nombre")
        organizacion = _entero_query(self.request, "organizacion")
        if organizacion:
            qs = qs.filter(organizacion_id=organizacion)
        if self.request.query_params.get("activo") == "true":
            qs = qs.filter(activo=True)
        return qs


class PagoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PagoApiSerializer

    def get_queryset(self):
        qs = Payment.objects.select_related("persona", "organizacion", "plan").order_by("-fecha_pago", "-id")
        organizacion = _entero_query(self.request, "organizacion")
        persona = _entero_query(self.request, "persona")
        periodo_mes = _entero_query(self.request, "periodo_mes")
        periodo_anio = _entero_query(self.request, "periodo_anio")

        if organizacion:
            qs = qs.filter(organizacion_id=organizacion)
        if persona:
            qs = qs.filter(persona_id=persona)
        if periodo_mes:
            qs = qs.filter(fecha_pago__month=periodo_mes)
        if periodo_anio:
            qs = qs.filter(fecha_pago__year=periodo_anio)
        return qs


class DocumentoTributarioViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentoTributarioApiSerializer

    def get_queryset(self):
        qs = DocumentoTributario.objects.select_related("organizacion").order_by("-fecha_emision", "-id")
        organizacion = _entero_query(self.request, "organizacion")
        periodo_mes = _entero_query(self.request, "periodo_mes")
        periodo_anio = _entero_query(self.request, "periodo_anio")
        tipo_documento = self.request.query_params.get("tipo_documento")

        if organizacion:
            qs = qs.filter(organizacion_id=organizacion)
        if periodo_mes:
            qs = qs.filter(fecha_emision__month=periodo_mes)
        if periodo_anio:
            qs = qs.filter(fecha_emision__year=periodo_anio)
        if tipo_documento:
            qs = qs.filter(tipo_documento=tipo_documento)
        return qs


class TransaccionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransaccionApiSerializer

    def get_queryset(self):
        qs = Transaction.objects.select_related("organizacion", "categoria").order_by("-fecha", "-id")
        organizacion = _entero_query(self.request, "organizacion")
        periodo_mes = _entero_query(self.request, "periodo_mes")
        periodo_anio = _entero_query(self.request, "periodo_anio")
        tipo = self.request.query_params.get("tipo")

        if organizacion:
            qs = qs.filter(organizacion_id=organizacion)
        if periodo_mes:
            qs = qs.filter(fecha__month=periodo_mes)
        if periodo_anio:
            qs = qs.filter(fecha__year=periodo_anio)
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs


class FinanzasResumenView(APIView):
    def get(self, request):
        organizacion = _entero_query(request, "organizacion")
        periodo_mes = _entero_query(request, "periodo_mes")
        periodo_anio = _entero_query(request, "periodo_anio")

        pagos = Payment.objects.all()
        documentos = DocumentoTributario.objects.all()
        transacciones = Transaction.objects.all()

        if organizacion:
            pagos = pagos.filter(organizacion_id=organizacion)
            documentos = documentos.filter(organizacion_id=organizacion)
            transacciones = transacciones.filter(organizacion_id=organizacion)
        if periodo_mes:
            pagos = pagos.filter(fecha_pago__month=periodo_mes)
            documentos = documentos.filter(fecha_emision__month=periodo_mes)
            transacciones = transacciones.filter(fecha__month=periodo_mes)
        if periodo_anio:
            pagos = pagos.filter(fecha_pago__year=periodo_anio)
            documentos = documentos.filter(fecha_emision__year=periodo_anio)
            transacciones = transacciones.filter(fecha__year=periodo_anio)

        totales_pagos = pagos.aggregate(
            monto_total=Sum("monto_total"),
            monto_iva=Sum("monto_iva"),
        )
        totales_documentos = documentos.aggregate(
            monto_total=Sum("monto_total"),
            retencion=Sum("retencion_monto"),
        )
        ingresos = transacciones.filter(tipo=Transaction.Tipo.INGRESO).aggregate(total=Sum("monto"))["total"] or 0
        egresos = transacciones.filter(tipo=Transaction.Tipo.EGRESO).aggregate(total=Sum("monto"))["total"] or 0

        return Response(
            {
                "pagos_total": totales_pagos["monto_total"] or 0,
                "pagos_iva": totales_pagos["monto_iva"] or 0,
                "documentos_total": totales_documentos["monto_total"] or 0,
                "documentos_retencion": totales_documentos["retencion"] or 0,
                "transacciones_ingresos": ingresos,
                "transacciones_egresos": egresos,
            }
        )
