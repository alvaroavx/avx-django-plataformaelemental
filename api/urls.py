from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuthenticationViewSet,
    EstudianteViewSet,
    HealthCheckView,
    ReporteResumenView,
    SesionViewSet,
)

router = DefaultRouter()
router.register(r"auth", AuthenticationViewSet, basename="auth")
router.register(r"sesiones", SesionViewSet, basename="sesiones")
router.register(r"estudiantes", EstudianteViewSet, basename="estudiantes")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="api-health"),
    path("reportes/resumen/", ReporteResumenView.as_view(), name="api-reportes-resumen"),
    path("", include(router.urls)),
]
