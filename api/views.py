from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class StatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "elemental-apps",
            },
            status=status.HTTP_200_OK,
        )


class VersionView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(
            {
                "name": "Elemental Apps",
                "version": getattr(settings, "APP_VERSION", "v1.0"),
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "username": request.user.get_username(),
                "is_authenticated": True,
                "timestamp": timezone.now(),
            },
            status=status.HTTP_200_OK,
        )
