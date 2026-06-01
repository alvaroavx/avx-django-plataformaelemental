from django.urls import path

from .views import HealthCheckView, MeView, StatusView, VersionView


urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="api-health"),
    path("status/", StatusView.as_view(), name="api-status"),
    path("version/", VersionView.as_view(), name="api-version"),
    path("me/", MeView.as_view(), name="api-me"),
]
