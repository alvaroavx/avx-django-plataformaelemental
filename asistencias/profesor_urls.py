from django.urls import path

from . import profesor_views

app_name = "profesor"

urlpatterns = [
    path("", profesor_views.inicio, name="inicio"),
    path("sesiones/", profesor_views.sesiones, name="sesiones"),
    path("sesiones/crear/", profesor_views.sesion_crear, name="sesion_crear"),
    path("sesiones/<int:pk>/liberar/", profesor_views.sesion_liberar, name="sesion_liberar"),
    path("sesiones/<int:pk>/estado/", profesor_views.sesion_estado, name="sesion_estado"),
    path("alumnos/", profesor_views.alumnos, name="alumnos"),
    path("alumnos/crear/", profesor_views.alumno_crear, name="alumno_crear"),
    path("pagos/", profesor_views.pagos, name="pagos"),
    path("pagos/crear/", profesor_views.pago_crear, name="pago_crear"),
    path("pagos/<int:pk>/", profesor_views.pago_detalle, name="pago_detalle"),
    path("pagos/masivo/nuevo/", profesor_views.pago_masivo, name="pago_masivo"),
    path("pagos/masivo/alumnos/", profesor_views.pago_masivo_alumnos, name="pago_masivo_alumnos"),
    path("pagos/masivo/<uuid:pk>/", profesor_views.pago_masivo_resultado, name="pago_masivo_resultado"),
]
