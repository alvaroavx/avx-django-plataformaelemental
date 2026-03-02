from django.urls import path

from . import views

app_name = "asistencias"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sesiones/", views.sesiones_list, name="sesiones_list"),
    path("sesiones/<int:pk>/", views.sesion_detail, name="sesion_detail"),
    path("asistencias/", views.asistencias_list, name="asistencias_list"),
    path("personas/<int:pk>/", views.persona_detail, name="persona_detail"),
    path("estudiantes/", views.estudiantes_list, name="estudiantes_list"),
    path("profesores/", views.profesores_list, name="profesores_list"),
    path("organizaciones/", views.organizaciones_list, name="organizaciones_list"),
]

