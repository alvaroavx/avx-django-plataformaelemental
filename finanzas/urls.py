from django.urls import path

from . import views

app_name = "finanzas"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("planes/", views.planes_list, name="planes_list"),
    path("planes/<int:pk>/editar/", views.plan_edit, name="plan_edit"),
    path("planes/<int:pk>/eliminar/", views.plan_delete, name="plan_delete"),
    path("pagos/", views.pagos_list, name="pagos_list"),
    path("pagos/<int:pk>/", views.pago_detail, name="pago_detail"),
    path("pagos/<int:pk>/editar/", views.pago_edit, name="pago_edit"),
    path("pagos/<int:pk>/eliminar/", views.pago_delete, name="pago_delete"),
    path("boletas/", views.boletas_list, name="boletas_list"),
    path("boletas/<int:pk>/editar/", views.boleta_edit, name="boleta_edit"),
    path("boletas/<int:pk>/eliminar/", views.boleta_delete, name="boleta_delete"),
    path("categorias/", views.categorias_list, name="categorias_list"),
    path("categorias/<int:pk>/editar/", views.categoria_edit, name="categoria_edit"),
    path("categorias/<int:pk>/eliminar/", views.categoria_delete, name="categoria_delete"),
    path("transacciones/", views.transacciones_list, name="transacciones_list"),
    path("transacciones/<int:pk>/editar/", views.transaccion_edit, name="transaccion_edit"),
    path("transacciones/<int:pk>/eliminar/", views.transaccion_delete, name="transaccion_delete"),
    path("reportes/categorias/", views.reporte_categorias, name="reporte_categorias"),
    path("export/pagos.csv", views.export_pagos_csv, name="export_pagos_csv"),
    path("export/transacciones.csv", views.export_transacciones_csv, name="export_transacciones_csv"),
]
