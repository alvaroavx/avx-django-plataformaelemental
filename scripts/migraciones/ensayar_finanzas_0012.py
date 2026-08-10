#!/usr/bin/env python
"""Mide finanzas.0012 sobre una copia PostgreSQL explícitamente no productiva."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import psycopg


MIGRACION = "0012_payment_clave_idempotencia_payment_disciplina_and_more"
APLICACION = "elemental_ensayo_finanzas_0012"
TABLAS = (
    "finanzas_lotepago",
    "finanzas_payment",
    "finanzas_transaction",
)


def argumentos():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument(
        "--confirmar-copia",
        required=True,
        choices=("COPIA_NO_PRODUCTIVA",),
        help="Confirmación literal obligatoria; el script además rechaza nombres con 'prod'.",
    )
    parser.add_argument(
        "--espacio-disponible-bytes",
        type=int,
        required=True,
        help="Espacio libre del volumen PostgreSQL, medido fuera de este script.",
    )
    parser.add_argument("--intervalo-ms", type=int, default=50)
    parser.add_argument(
        "--timeout-s",
        type=int,
        default=900,
        help="Aborta el proceso de migración si supera este tiempo.",
    )
    return parser.parse_args()


def preparar_django():
    raiz = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(raiz))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plataformaelemental.settings")
    import django

    django.setup()
    from django.db import connection

    connection.ensure_connection()
    parametros = connection.get_connection_params().copy()
    nombre = str(parametros.get("dbname") or parametros.get("database") or "")
    motor = connection.vendor
    connection.close()
    return raiz, motor, nombre, parametros


def conectar(parametros, *, aplicacion):
    parametros = parametros.copy()
    parametros["application_name"] = aplicacion
    return psycopg.connect(**parametros)


def normalizar_sql(sql):
    return re.sub(r"\s+", " ", sql or "").strip()[:500]


def obtener_estado(conn):
    resultado = {
        "tablas": {},
        "migraciones_finanzas": [],
        "migraciones_asistencias": [],
    }
    with conn.cursor() as cursor:
        cursor.execute("SELECT version()")
        resultado["version_postgresql"] = cursor.fetchone()[0]
        for tabla in TABLAS:
            cursor.execute(f'SELECT count(*) FROM "{tabla}"')
            filas = cursor.fetchone()[0]
            cursor.execute(
                "SELECT pg_table_size(to_regclass(%s)), "
                "pg_indexes_size(to_regclass(%s)), pg_total_relation_size(to_regclass(%s))",
                (tabla, tabla, tabla),
            )
            tabla_bytes, indices_bytes, total_bytes = cursor.fetchone()
            resultado["tablas"][tabla] = {
                "filas": filas,
                "tabla_bytes": tabla_bytes,
                "indices_bytes": indices_bytes,
                "total_bytes": total_bytes,
            }
        cursor.execute(
            "SELECT name FROM django_migrations WHERE app = 'finanzas' ORDER BY name"
        )
        resultado["migraciones_finanzas"] = [fila[0] for fila in cursor.fetchall()]
        cursor.execute(
            "SELECT name FROM django_migrations WHERE app = 'asistencias' ORDER BY name"
        )
        resultado["migraciones_asistencias"] = [fila[0] for fila in cursor.fetchall()]
        cursor.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name IN "
            "('finanzas_payment', 'finanzas_transaction', 'finanzas_lotepago')"
        )
        columnas = {(tabla, columna) for tabla, columna in cursor.fetchall()}
        resultado["columnas_nuevas_presentes"] = sorted(
            f"{tabla}.{columna}"
            for tabla, columna in columnas
            if columna
            in {
                "respaldo",
                "clave_idempotencia",
                "disciplina_id",
                "registrado_por_id",
                "transaccion_id",
                "creado_por_id",
            }
        )
        if ("finanzas_payment", "transaccion_id") in columnas:
            cursor.execute("SELECT count(*) FROM finanzas_payment WHERE transaccion_id IS NOT NULL")
            resultado["pagos_con_transaccion"] = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM finanzas_payment WHERE "
                "clave_idempotencia IS NOT NULL OR disciplina_id IS NOT NULL OR "
                "registrado_por_id IS NOT NULL OR respaldo IS NOT NULL OR transaccion_id IS NOT NULL"
            )
            resultado["pagos_historicos_con_datos_nuevos"] = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM finanzas_lotepago WHERE respaldo IS NOT NULL"
            )
            resultado["lotes_historicos_con_respaldo_nuevo"] = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM finanzas_transaction WHERE creado_por_id IS NOT NULL"
            )
            resultado["transacciones_historicas_con_actor_nuevo"] = cursor.fetchone()[0]
        else:
            resultado["pagos_con_transaccion"] = None
        cursor.execute("SELECT count(*) FROM finanzas_transaction")
        resultado["transacciones"] = cursor.fetchone()[0]
    return resultado


def sondear_escrituras(parametros, payment_id, detener, muestras, inicio_ensayo):
    if payment_id is None:
        muestras.append({"omitida": "finanzas_payment no tiene filas"})
        return
    conn = conectar(parametros, aplicacion=f"{APLICACION}_escritura")
    try:
        while not detener.is_set():
            inicio = time.monotonic()
            error = None
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                    cursor.execute(
                        "UPDATE finanzas_payment SET observaciones = observaciones WHERE id = %s",
                        (payment_id,),
                    )
                conn.rollback()
            except Exception as exc:  # El tipo y SQLSTATE son evidencia; no se emiten parámetros.
                conn.rollback()
                error = {"tipo": type(exc).__name__, "sqlstate": getattr(exc, "sqlstate", None)}
            muestras.append(
                {
                    "inicio_s": round(inicio - inicio_ensayo, 6),
                    "duracion_ms": round((time.monotonic() - inicio) * 1000, 3),
                    "error": error,
                }
            )
            detener.wait(0.05)
    finally:
        conn.close()


def resumir_actividad(actividad, intervalo):
    operaciones = {}
    for muestra in actividad:
        sql = muestra["sql"]
        if not sql or sql.startswith("SELECT "):
            continue
        operacion = operaciones.setdefault(
            sql,
            {
                "sql": sql,
                "primera_muestra_s": muestra["t_s"],
                "ultima_muestra_s": muestra["t_s"],
                "muestras": 0,
                "muestras_esperando_lock": 0,
            },
        )
        operacion["ultima_muestra_s"] = muestra["t_s"]
        operacion["muestras"] += 1
        operacion["muestras_esperando_lock"] += int(muestra["wait_event_type"] == "Lock")
    for operacion in operaciones.values():
        observado = operacion["ultima_muestra_s"] - operacion["primera_muestra_s"]
        operacion["duracion_minima_observada_ms"] = round(observado * 1000, 3)
        operacion["duracion_maxima_estimada_ms"] = round((observado + 2 * intervalo) * 1000, 3)
    return list(operaciones.values())


def medir(parametros, raiz, intervalo, timeout_s):
    monitor = conectar(parametros, aplicacion=f"{APLICACION}_monitor")
    # El monitor nunca debe convertirse en el lock que intenta observar.
    monitor.autocommit = True
    with monitor.cursor() as cursor:
        cursor.execute("SELECT id FROM finanzas_payment ORDER BY id LIMIT 1")
        fila = cursor.fetchone()
    payment_id = fila[0] if fila else None

    detener = threading.Event()
    escrituras = []
    inicio = time.monotonic()
    hilo = threading.Thread(
        target=sondear_escrituras,
        args=(parametros, payment_id, detener, escrituras, inicio),
        daemon=True,
    )
    hilo.start()

    entorno = os.environ.copy()
    opciones = entorno.get("PGOPTIONS", "").strip()
    entorno["PGOPTIONS"] = f"{opciones} -c application_name={APLICACION}".strip()
    proceso = subprocess.Popen(
        [
            sys.executable,
            str(raiz / "manage.py"),
            "migrate",
            "finanzas",
            "0012",
            "--noinput",
            "--verbosity",
            "2",
        ],
        cwd=raiz,
        env=entorno,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    actividad = []
    locks = []
    timeout_alcanzado = False
    try:
        while proceso.poll() is None:
            if time.monotonic() - inicio > timeout_s:
                timeout_alcanzado = True
                proceso.terminate()
                break
            with monitor.cursor() as cursor:
                cursor.execute(
                    "SELECT state, wait_event_type, wait_event, query "
                    "FROM pg_stat_activity WHERE application_name = %s",
                    (APLICACION,),
                )
                for estado, wait_type, wait_event, consulta in cursor.fetchall():
                    actividad.append(
                        {
                            "t_s": round(time.monotonic() - inicio, 4),
                            "estado": estado,
                            "wait_event_type": wait_type,
                            "wait_event": wait_event,
                            "sql": normalizar_sql(consulta),
                        }
                    )
                cursor.execute(
                    "SELECT locktype, mode, granted FROM pg_locks l "
                    "JOIN pg_stat_activity a ON a.pid = l.pid "
                    "WHERE a.application_name IN (%s, %s)",
                    (APLICACION, f"{APLICACION}_escritura"),
                )
                locks.append(
                    {
                        "t_s": round(time.monotonic() - inicio, 4),
                        "locks": [
                            {"tipo": tipo, "modo": modo, "concedido": concedido}
                            for tipo, modo, concedido in cursor.fetchall()
                        ],
                    }
                )
            time.sleep(intervalo)
        salida = proceso.communicate(timeout=10)[0]
    finally:
        detener.set()
        hilo.join(timeout=7)
        monitor.close()
        if proceso.poll() is None:
            proceso.terminate()
    return {
        "exit_code": proceso.returncode,
        "timeout_alcanzado": timeout_alcanzado,
        "duracion_total_s": round(time.monotonic() - inicio, 4),
        "salida_manage_py": salida[-12000:],
        "actividad": actividad,
        "operaciones_relevantes": resumir_actividad(actividad, intervalo),
        "locks": locks,
        "escrituras_representativas": escrituras,
    }


def validar_invariantes(antes, despues):
    errores = []
    if antes["transacciones"] != despues["transacciones"]:
        errores.append("La migración cambió el total de transacciones.")
    if despues["pagos_con_transaccion"] != 0:
        errores.append("La migración inventó o eliminó asociaciones pago-transacción.")
    for campo in (
        "pagos_historicos_con_datos_nuevos",
        "lotes_historicos_con_respaldo_nuevo",
        "transacciones_historicas_con_actor_nuevo",
    ):
        if despues.get(campo) != 0:
            errores.append(f"La migración pobló datos históricos inesperadamente: {campo}.")
    return errores


def main():
    args = argumentos()
    if args.espacio_disponible_bytes <= 0:
        raise SystemExit("--espacio-disponible-bytes debe ser mayor que cero")
    if args.intervalo_ms <= 0 or args.timeout_s <= 0:
        raise SystemExit("--intervalo-ms y --timeout-s deben ser mayores que cero")
    raiz, motor, nombre_bd, parametros = preparar_django()
    if motor != "postgresql":
        raise SystemExit("El ensayo exige PostgreSQL real.")
    entorno = os.environ.get("DJANGO_ENV", "").lower()
    if "prod" in nombre_bd.lower() or entorno not in {
        "dev",
        "development",
        "qa",
        "staging",
        "test",
    }:
        raise SystemExit("Seguridad: la base o DJANGO_ENV parecen de producción.")

    conn = conectar(parametros, aplicacion=f"{APLICACION}_preflight")
    antes = obtener_estado(conn)
    if "0011_lotepago_payment_lote" not in antes["migraciones_finanzas"]:
        raise SystemExit("Precondición incumplida: finanzas.0011 no está aplicada.")
    if antes["migraciones_finanzas"][-1] != "0011_lotepago_payment_lote":
        raise SystemExit("Precondición incumplida: finanzas debe quedar exactamente en 0011.")
    if (
        "0004_alter_sesionclase_estado_liberacionsesion_and_more"
        not in antes["migraciones_asistencias"]
    ):
        raise SystemExit("Precondición incumplida: asistencias.0004 debe estar aplicada primero.")
    if MIGRACION in antes["migraciones_finanzas"]:
        raise SystemExit("Precondición incumplida: finanzas.0012 ya está aplicada.")
    conn.close()

    medicion = medir(parametros, raiz, args.intervalo_ms / 1000, args.timeout_s)
    despues = None
    errores = []
    if medicion["exit_code"] == 0:
        conn = conectar(parametros, aplicacion=f"{APLICACION}_postflight")
        despues = obtener_estado(conn)
        conn.close()
        errores = validar_invariantes(antes, despues)
    else:
        errores.append("manage.py migrate terminó con error.")

    reporte = {
        "artefacto": "ensayar_finanzas_0012",
        "migracion": f"finanzas.{MIGRACION}",
        "base_no_productiva_confirmada": True,
        "nombre_base_omitido_por_seguridad": True,
        "espacio_disponible_bytes_declarado": args.espacio_disponible_bytes,
        "antes": antes,
        "medicion": medicion,
        "despues": despues,
        "errores_invariantes": errores,
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(reporte, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Reporte sanitizado: {args.salida}")
    raise SystemExit(1 if errores else 0)


if __name__ == "__main__":
    main()
