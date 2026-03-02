from django.urls import path

from . import views

app_name = "personas"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("nuevo/", views.persona_create, name="persona_create"),
    path("listado/", views.personas_list, name="personas_list"),
    path("<int:pk>/", views.persona_detail, name="persona_detail"),
    path("<int:pk>/editar/", views.persona_edit, name="persona_edit"),
]
