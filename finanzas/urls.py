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
    path("documentos-tributarios/", views.documentos_tributarios_list, name="documentos_tributarios_list"),
    path(
        "documentos-tributarios/importar/",
        views.documento_tributario_importar,
        name="documento_tributario_importar",
    ),
    path(
        "documentos-tributarios/importar/parse-preview/",
        views.documento_tributario_parse_preview,
        name="documento_tributario_parse_preview",
    ),
    path(
        "documentos-tributarios/importar/archivo/<str:token>/<str:tipo_archivo>/",
        views.documento_tributario_importacion_archivo,
        name="documento_tributario_importacion_archivo",
    ),
    path("documentos-tributarios/<int:pk>/", views.documento_tributario_detail, name="documento_tributario_detail"),
    path(
        "documentos-tributarios/<int:pk>/archivo/<str:tipo_archivo>/",
        views.documento_tributario_archivo,
        name="documento_tributario_archivo",
    ),
    path(
        "documentos-tributarios/<int:pk>/editar/",
        views.documento_tributario_edit,
        name="documento_tributario_edit",
    ),
    path(
        "documentos-tributarios/<int:pk>/eliminar/",
        views.documento_tributario_delete,
        name="documento_tributario_delete",
    ),
    path("boletas/", views.documentos_tributarios_list, name="boletas_list"),
    path("boletas/<int:pk>/editar/", views.documento_tributario_edit, name="boleta_edit"),
    path("boletas/<int:pk>/eliminar/", views.documento_tributario_delete, name="boleta_delete"),
    path("categorias/", views.categorias_list, name="categorias_list"),
    path("categorias/<int:pk>/editar/", views.categoria_edit, name="categoria_edit"),
    path("categorias/<int:pk>/eliminar/", views.categoria_delete, name="categoria_delete"),
    path("transacciones/", views.transacciones_list, name="transacciones_list"),
    path("transacciones/<int:pk>/", views.transaccion_detail, name="transaccion_detail"),
    path("transacciones/<int:pk>/archivo/", views.transaccion_archivo, name="transaccion_archivo"),
    path("transacciones/<int:pk>/editar/", views.transaccion_edit, name="transaccion_edit"),
    path("transacciones/<int:pk>/eliminar/", views.transaccion_delete, name="transaccion_delete"),
    path("reportes/categorias/", views.reporte_categorias, name="reporte_categorias"),
    path("export/pagos.csv", views.export_pagos_csv, name="export_pagos_csv"),
    path("export/transacciones.csv", views.export_transacciones_csv, name="export_transacciones_csv"),
]
