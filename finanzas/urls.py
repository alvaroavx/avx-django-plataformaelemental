from django.urls import path

from . import views

app_name = "finanzas"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("planes/", views.planes_list, name="planes_list"),
    path("planes/<int:pk>/editar/", views.plan_edit, name="plan_edit"),
    path("planes/<int:pk>/eliminar/", views.plan_delete, name="plan_delete"),
    path("pagos/", views.pagos_list, name="pagos_list"),
    path("pagos/masivo/", views.pago_masivo, name="pago_masivo"),
    path("pagos/masivo/personas/", views.pago_masivo_personas, name="pago_masivo_personas"),
    path("pagos/masivo/<uuid:pk>/", views.pago_masivo_resultado, name="pago_masivo_resultado"),
    path("pagos/<int:pk>/", views.pago_detail, name="pago_detail"),
    path("pagos/<int:pk>/editar/", views.pago_edit, name="pago_edit"),
    path("pagos/<int:pk>/revertir/", views.pago_revertir, name="pago_revertir"),
    path("categorias/", views.categorias_list, name="categorias_list"),
    path("categorias/<int:pk>/editar/", views.categoria_edit, name="categoria_edit"),
    path("categorias/<int:pk>/eliminar/", views.categoria_delete, name="categoria_delete"),
    path("transacciones/", views.transacciones_list, name="transacciones_list"),
    path("transacciones/<int:pk>/", views.transaccion_detail, name="transaccion_detail"),
    path("transacciones/<int:pk>/archivo/", views.transaccion_archivo, name="transaccion_archivo"),
    path("transacciones/<int:pk>/editar/", views.transaccion_edit, name="transaccion_edit"),
    path("transacciones/<int:pk>/eliminar/", views.transaccion_delete, name="transaccion_delete"),
    path("reportes/categorias/", views.reporte_categorias, name="reporte_categorias"),
    path("preparar-mes/", views.preparar_mes, name="preparar_mes"),
    path("preparar-mes/descargar/", views.descargar_cuadratura, name="descargar_cuadratura"),
    path("export/libro-caja.csv", views.export_libro_caja_csv, name="export_libro_caja_csv"),
    path("export/pagos.csv", views.export_pagos_csv, name="export_pagos_csv"),
    path("export/pagos-alumnos.xlsx", views.export_pagos_alumnos_xlsx, name="export_pagos_alumnos_xlsx"),
    path("export/pagos-profesores.xlsx", views.export_pagos_profesores_xlsx, name="export_pagos_profesores_xlsx"),
    path("export/transacciones.csv", views.export_transacciones_csv, name="export_transacciones_csv"),
    path("export/transacciones.xlsx", views.export_transacciones_xlsx, name="export_transacciones_xlsx"),
]
