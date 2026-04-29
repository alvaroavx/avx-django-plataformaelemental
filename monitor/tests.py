from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class MonitorDashboardTests(TestCase):
    def test_dashboard_requiere_login(self):
        response = self.client.get(reverse("monitor:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_dashboard_autenticado_responde_ok(self):
        usuario = get_user_model().objects.create_user(
            username="monitor",
            password="monitor-test",
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse("monitor:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monitor")
