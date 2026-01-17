from django.urls import path

from . import views

app_name = "webapp"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sesiones/", views.sesiones_list, name="sesiones_list"),
    path("sesiones/rapida/", views.sesion_rapida, name="sesion_rapida"),
    path("sesiones/<int:pk>/asistencia/", views.sesion_asistencia, name="sesion_asistencia"),
    path("asistencias/", views.asistencias_list, name="asistencias_list"),
    path("personas/<int:pk>/", views.persona_detail, name="persona_detail"),
    path("estudiantes/", views.estudiantes_list, name="estudiantes_list"),
    path("profesores/", views.profesores_list, name="profesores_list"),
    path("pagos/", views.pagos_list, name="pagos_list"),
    path("finanzas/unificadas/", views.finanzas_unificadas, name="finanzas_unificadas"),
]
