from django.urls import path

from . import views


app_name = "monitor"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sitios/nuevo/", views.sitio_create, name="sitio_create"),
    path("sitios/<int:pk>/", views.sitio_detail, name="sitio_detail"),
    path("sitios/<int:pk>/configuracion/", views.sitio_configuracion, name="sitio_configuracion"),
    path("configuracion/", views.configuracion, name="configuracion"),
]
