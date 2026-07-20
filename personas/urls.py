from django.urls import path

from . import views

app_name = "personas"

urlpatterns = [
    path("solicitar-acceso/", views.solicitud_acceso, name="solicitud_acceso"),
    path("solicitudes-acceso/", views.solicitudes_acceso_list, name="solicitudes_acceso_list"),
    path("solicitudes-acceso/<uuid:pk>/", views.solicitud_acceso_detail, name="solicitud_acceso_detail"),
    path("solicitudes-acceso/<uuid:pk>/aprobar/", views.solicitud_acceso_aprobar, name="solicitud_acceso_aprobar"),
    path("solicitudes-acceso/<uuid:pk>/rechazar/", views.solicitud_acceso_rechazar, name="solicitud_acceso_rechazar"),
    path("solicitudes-acceso/<uuid:pk>/reabrir/", views.solicitud_acceso_reabrir, name="solicitud_acceso_reabrir"),
    path("", views.dashboard, name="dashboard"),
    path("organizaciones/", views.organizaciones_list, name="organizaciones_list"),
    path("organizaciones/nueva/", views.organizacion_create, name="organizacion_create"),
    path("organizaciones/<int:pk>/", views.organizacion_detail, name="organizacion_detail"),
    path("organizaciones/<int:pk>/editar/", views.organizacion_edit, name="organizacion_edit"),
    path("nuevo/", views.persona_create, name="persona_create"),
    path("listado/", views.personas_list, name="personas_list"),
    path("<int:pk>/", views.persona_detail, name="persona_detail"),
    path("<int:pk>/editar/", views.persona_edit, name="persona_edit"),
]
