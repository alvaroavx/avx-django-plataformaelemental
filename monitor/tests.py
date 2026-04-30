from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ConfiguracionMonitor, ConfiguracionSitio, DiscoverySitio, Proyecto, Sitio
from .services.discovery import ejecutar_discovery_inicial
from .services.urls import normalizar_url


class _HeadersFake:
    def get_content_charset(self):
        return "utf-8"


class _RespuestaFake:
    headers = _HeadersFake()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _max_bytes):
        return b"<html><head><title>AVX</title><meta name='description' content='Mission Control'></head></html>"

    def getcode(self):
        return 200

    def geturl(self):
        return "https://avx.cl/"


class MonitorBaseTestCase(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="monitor",
            password="monitor-test",
        )

    def login(self):
        self.client.force_login(self.usuario)


class MonitorDashboardTests(MonitorBaseTestCase):
    def test_vistas_html_requieren_login(self):
        proyecto = Proyecto.objects.create(nombre="AVX")
        sitio = Sitio.objects.create(proyecto=proyecto, nombre="AVX", url="https://avx.cl")
        rutas = [
            reverse("monitor:dashboard"),
            reverse("monitor:sitio_create"),
            reverse("monitor:sitio_detail", args=[sitio.pk]),
            reverse("monitor:configuracion"),
            reverse("monitor:sitio_configuracion", args=[sitio.pk]),
        ]

        for ruta in rutas:
            with self.subTest(ruta=ruta):
                response = self.client.get(ruta)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])

    def test_dashboard_autenticado_responde_ok_sin_sitios(self):
        self.login()

        response = self.client.get(reverse("monitor:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin sitios monitoreados")
        self.assertContains(response, "Agregar sitio")

    def test_dashboard_muestra_sitio_existente(self):
        self.login()
        proyecto = Proyecto.objects.create(nombre="AVX")
        Sitio.objects.create(
            proyecto=proyecto,
            nombre="Plataforma",
            url="https://plataforma.test",
            ultimo_estado=Sitio.ESTADO_ACTIVO,
        )

        response = self.client.get(reverse("monitor:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plataforma")
        self.assertContains(response, "Activo")


class MonitorSitioWorkflowTests(MonitorBaseTestCase):
    def test_crear_sitio_normaliza_url_y_ejecuta_discovery(self):
        self.login()

        with patch("monitor.views.ejecutar_discovery_inicial") as discovery_mock:
            response = self.client.post(
                reverse("monitor:sitio_create"),
                {
                    "proyecto_nombre": "AVX",
                    "nombre": "Mission Control",
                    "url": " avx.cl/status ",
                },
            )

        sitio = Sitio.objects.get()
        self.assertRedirects(response, reverse("monitor:sitio_detail", args=[sitio.pk]))
        self.assertEqual(sitio.url, "https://avx.cl/status")
        self.assertEqual(sitio.dominio, "avx.cl")
        discovery_mock.assert_called_once_with(sitio)

    def test_crear_sitio_preserva_filtros_globales_en_redirect(self):
        self.login()

        with patch("monitor.views.ejecutar_discovery_inicial"):
            response = self.client.post(
                f"{reverse('monitor:sitio_create')}?periodo_mes=todos&periodo_anio=2026&organizacion=9",
                {
                    "proyecto_nombre": "AVX",
                    "nombre": "Mission Control",
                    "url": "avx.cl",
                },
            )

        sitio = Sitio.objects.get()
        self.assertRedirects(
            response,
            (
                f"{reverse('monitor:sitio_detail', args=[sitio.pk])}"
                "?periodo_mes=todos&periodo_anio=2026&organizacion=9"
            ),
            fetch_redirect_response=False,
        )

    def test_crear_sitio_rechaza_url_invalida(self):
        self.login()

        response = self.client.post(
            reverse("monitor:sitio_create"),
            {
                "proyecto_nombre": "AVX",
                "nombre": "Sitio roto",
                "url": "nota una url",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresa una URL")
        self.assertFalse(Sitio.objects.exists())

    def test_crear_sitio_rechaza_duplicado_en_mismo_proyecto(self):
        self.login()
        proyecto = Proyecto.objects.create(nombre="AVX")
        Sitio.objects.create(proyecto=proyecto, nombre="AVX", url="https://avx.cl")

        response = self.client.post(
            reverse("monitor:sitio_create"),
            {
                "proyecto": proyecto.pk,
                "nombre": "AVX duplicado",
                "url": "https://avx.cl",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este sitio ya existe")
        self.assertEqual(Sitio.objects.count(), 1)

    def test_detalle_muestra_discovery_y_configuracion(self):
        self.login()
        proyecto = Proyecto.objects.create(nombre="AVX")
        sitio = Sitio.objects.create(
            proyecto=proyecto,
            nombre="Mission Control",
            url="https://avx.cl",
            ultimo_estado=Sitio.ESTADO_ACTIVO,
        )
        DiscoverySitio.objects.create(
            sitio=sitio,
            estado_http=200,
            url_final="https://avx.cl",
            titulo="AVX",
            tiempo_respuesta_ms=150,
        )

        response = self.client.get(reverse("monitor:sitio_detail", args=[sitio.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mission Control")
        self.assertContains(response, "AVX")
        self.assertContains(response, "150 ms")

    def test_detalle_no_crea_configuracion_por_solo_ver(self):
        self.login()
        proyecto = Proyecto.objects.create(nombre="AVX")
        sitio = Sitio.objects.create(proyecto=proyecto, nombre="Mission Control", url="https://avx.cl")

        response = self.client.get(reverse("monitor:sitio_detail", args=[sitio.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ConfiguracionSitio.objects.filter(sitio=sitio).exists())


class MonitorConfiguracionTests(MonitorBaseTestCase):
    def test_configuracion_global_puede_existir_sin_configuracion_por_sitio(self):
        self.login()

        response = self.client.post(
            reverse("monitor:configuracion"),
            {
                "timeout_segundos": 15,
                "frecuencia_minutos": 120,
                "seguir_redirecciones": "on",
                "user_agent": "AVX Monitor Test",
            },
        )

        self.assertRedirects(response, reverse("monitor:configuracion"))
        configuracion = ConfiguracionMonitor.objects.get(pk=1)
        self.assertEqual(configuracion.timeout_segundos, 15)
        self.assertEqual(configuracion.frecuencia_minutos, 120)
        self.assertEqual(configuracion.user_agent, "AVX Monitor Test")

    def test_configuracion_global_preserva_filtros_globales_en_redirect(self):
        self.login()

        response = self.client.post(
            f"{reverse('monitor:configuracion')}?periodo_mes=4&periodo_anio=2026&organizacion=3",
            {
                "timeout_segundos": 15,
                "frecuencia_minutos": 120,
                "seguir_redirecciones": "on",
                "user_agent": "AVX Monitor Test",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('monitor:configuracion')}?periodo_mes=4&periodo_anio=2026&organizacion=3",
            fetch_redirect_response=False,
        )

    def test_configuracion_por_sitio_guarda_false_y_lo_muestra_seleccionado(self):
        self.login()
        proyecto = Proyecto.objects.create(nombre="AVX")
        sitio = Sitio.objects.create(proyecto=proyecto, nombre="AVX", url="https://avx.cl")

        response = self.client.post(
            reverse("monitor:sitio_configuracion", args=[sitio.pk]),
            {
                "timeout_segundos": 20,
                "frecuencia_minutos": 180,
                "seguir_redirecciones": "false",
                "activo": "on",
            },
        )

        self.assertRedirects(response, reverse("monitor:sitio_detail", args=[sitio.pk]))
        configuracion = ConfiguracionSitio.objects.get(sitio=sitio)
        self.assertIs(configuracion.seguir_redirecciones, False)

        response = self.client.get(reverse("monitor:sitio_configuracion", args=[sitio.pk]))
        self.assertContains(response, '<option value="false" selected>No</option>', html=True)


class MonitorServiceTests(TestCase):
    def test_normalizar_url_agrega_https_y_conserva_path(self):
        self.assertEqual(normalizar_url("avx.cl/status"), "https://avx.cl/status")

    @patch("monitor.services.discovery.urlopen", return_value=_RespuestaFake())
    def test_discovery_exitoso_actualiza_estado_del_sitio(self, _urlopen_mock):
        proyecto = Proyecto.objects.create(nombre="AVX")
        sitio = Sitio.objects.create(proyecto=proyecto, nombre="AVX", url="https://avx.cl")

        discovery = ejecutar_discovery_inicial(sitio)
        sitio.refresh_from_db()

        self.assertEqual(discovery.estado_http, 200)
        self.assertEqual(discovery.titulo, "AVX")
        self.assertEqual(discovery.meta_description, "Mission Control")
        self.assertEqual(sitio.ultimo_estado, Sitio.ESTADO_ACTIVO)
        self.assertIsNotNone(sitio.ultimo_check_en)

    @patch("monitor.services.discovery.urlopen", side_effect=URLError("timeout simulado"))
    def test_discovery_con_error_queda_controlado_y_visible_en_detalle(self, _urlopen_mock):
        proyecto = Proyecto.objects.create(nombre="AVX")
        sitio = Sitio.objects.create(proyecto=proyecto, nombre="AVX", url="https://avx.cl")

        discovery = ejecutar_discovery_inicial(sitio)
        sitio.refresh_from_db()

        self.assertEqual(sitio.ultimo_estado, Sitio.ESTADO_ERROR)
        self.assertIn("timeout simulado", discovery.error)

        usuario = get_user_model().objects.create_user(username="qa", password="qa-test")
        self.client.force_login(usuario)
        response = self.client.get(reverse("monitor:sitio_detail", args=[sitio.pk]))
        self.assertContains(response, "timeout simulado")
