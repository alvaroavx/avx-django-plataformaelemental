from django.urls import path

from . import views

app_name = "asistencias"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sesiones/", views.sesiones_list, name="sesiones_list"),
    path("sesiones/<int:pk>/", views.sesion_detail, name="sesion_detail"),
    path("sesiones/<int:pk>/editar/", views.sesion_edit, name="sesion_edit"),
    path("disciplinas/", views.disciplinas_list, name="disciplinas_list"),
    path("disciplinas/nueva/", views.disciplina_create, name="disciplina_create"),
    path("disciplinas/<int:pk>/", views.disciplina_detail, name="disciplina_detail"),
    path("disciplinas/<int:pk>/editar/", views.disciplina_edit, name="disciplina_edit"),
    path("asistencias/", views.asistencias_list, name="asistencias_list"),
    path("estudiantes/", views.estudiantes_list, name="estudiantes_list"),
    path("profesores/", views.profesores_list, name="profesores_list"),
]
