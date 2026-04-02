from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AsistenciaBaseViewSet,
    AsistenciasResumenView,
    AuthenticationViewSet,
    DisciplinaViewSet,
    DocumentoTributarioViewSet,
    EstudianteViewSet,
    FinanzasResumenView,
    HealthCheckView,
    MeView,
    OrganizacionViewSet,
    PagoViewSet,
    PersonaViewSet,
    PersonasResumenView,
    PlanPagoViewSet,
    ReporteResumenView,
    SesionBaseViewSet,
    SesionViewSet,
    TransaccionViewSet,
)

router = DefaultRouter()
router.register(r"auth", AuthenticationViewSet, basename="auth")
router.register(r"sesiones", SesionViewSet, basename="sesiones")
router.register(r"estudiantes", EstudianteViewSet, basename="estudiantes")
router.register(r"v1/personas/organizaciones", OrganizacionViewSet, basename="v1-organizaciones")
router.register(r"v1/personas/personas", PersonaViewSet, basename="v1-personas")
router.register(r"v1/asistencias/disciplinas", DisciplinaViewSet, basename="v1-disciplinas")
router.register(r"v1/asistencias/sesiones", SesionBaseViewSet, basename="v1-sesiones")
router.register(r"v1/asistencias/asistencias", AsistenciaBaseViewSet, basename="v1-asistencias")
router.register(r"v1/finanzas/planes", PlanPagoViewSet, basename="v1-planes")
router.register(r"v1/finanzas/pagos", PagoViewSet, basename="v1-pagos")
router.register(
    r"v1/finanzas/documentos-tributarios",
    DocumentoTributarioViewSet,
    basename="v1-documentos-tributarios",
)
router.register(r"v1/finanzas/transacciones", TransaccionViewSet, basename="v1-transacciones")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="api-health"),
    path("me/", MeView.as_view(), name="api-me"),
    path("reportes/resumen/", ReporteResumenView.as_view(), name="api-reportes-resumen"),
    path("v1/personas/resumen/", PersonasResumenView.as_view(), name="api-v1-personas-resumen"),
    path("v1/asistencias/resumen/", AsistenciasResumenView.as_view(), name="api-v1-asistencias-resumen"),
    path("v1/finanzas/resumen/", FinanzasResumenView.as_view(), name="api-v1-finanzas-resumen"),
    path("", include(router.urls)),
]
