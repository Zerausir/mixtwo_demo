"""
services/queries.py — Consultas analíticas sobre el mart de ventas.

Cada función retorna un DataFrame de pandas listo para graficar. Sin
caché explícito (Flask-Caching) por simplicidad del demo -- con SQLite
local y bajo tráfico de 1-2 usuarios, el costo de recalcular en cada
carga es insignificante.
"""
from __future__ import annotations

import pandas as pd

from services.database import get_connection


def resumen_general() -> dict:
    """KPIs de cabecera: ventas totales, unidades, ticket promedio, rango de fechas."""
    con = get_connection()
    fila = pd.read_sql(
        """
        SELECT
            SUM(PRECIO_FINAL) AS ventas_totales,
            SUM(CANTIDAD) AS unidades_totales,
            COUNT(DISTINCT DATE(FECHA)) AS dias_con_venta,
            MIN(FECHA) AS fecha_min,
            MAX(FECHA) AS fecha_max,
            COUNT(*) AS transacciones
        FROM ventas
        """,
        con,
    ).iloc[0]
    con.close()
    ticket_promedio = fila["ventas_totales"] / fila["transacciones"] if fila["transacciones"] else 0
    return {
        "ventas_totales": float(fila["ventas_totales"] or 0),
        "unidades_totales": int(fila["unidades_totales"] or 0),
        "transacciones": int(fila["transacciones"] or 0),
        "ticket_promedio": float(ticket_promedio),
        "fecha_min": fila["fecha_min"],
        "fecha_max": fila["fecha_max"],
    }


def ventas_por_semana() -> pd.DataFrame:
    con = get_connection()
    df = pd.read_sql(
        """
        SELECT
            strftime('%Y-W%W', FECHA) AS semana,
            MIN(DATE(FECHA)) AS semana_inicio,
            SUM(PRECIO_FINAL) AS ventas,
            SUM(CANTIDAD) AS unidades
        FROM ventas
        GROUP BY semana
        ORDER BY semana_inicio
        """,
        con,
    )
    con.close()
    return df


def ventas_por_linea() -> pd.DataFrame:
    con = get_connection()
    df = pd.read_sql(
        """
        SELECT
            LINEA_PRODUCTO AS linea,
            SUM(PRECIO_FINAL) AS ventas,
            SUM(CANTIDAD) AS unidades,
            COUNT(*) AS transacciones
        FROM ventas
        GROUP BY linea
        ORDER BY ventas DESC
        """,
        con,
    )
    con.close()
    total = df["ventas"].sum()
    df["porcentaje"] = (df["ventas"] / total * 100).round(2) if total else 0
    return df


def ventas_por_marca(top_n: int = 12) -> pd.DataFrame:
    con = get_connection()
    df = pd.read_sql(
        """
        SELECT
            MARCA AS marca,
            SUM(PRECIO_FINAL) AS ventas,
            SUM(CANTIDAD) AS unidades
        FROM ventas
        WHERE MARCA != 'SIN IDENTIFICAR'
        GROUP BY marca
        ORDER BY ventas DESC
        LIMIT ?
        """,
        con,
        params=(top_n,),
    )
    con.close()
    return df


def ventas_por_sucursal() -> pd.DataFrame:
    con = get_connection()
    df = pd.read_sql(
        """
        SELECT
            SUCURSAL AS sucursal,
            SUM(PRECIO_FINAL) AS ventas,
            SUM(CANTIDAD) AS unidades,
            COUNT(*) AS transacciones
        FROM ventas
        GROUP BY sucursal
        ORDER BY ventas DESC
        """,
        con,
    )
    con.close()
    return df


def opciones_filtro() -> dict:
    """Valores únicos para poblar los dropdowns del explorador."""
    con = get_connection()
    sucursales = pd.read_sql("SELECT DISTINCT SUCURSAL FROM ventas ORDER BY 1", con)["SUCURSAL"].tolist()
    lineas = pd.read_sql("SELECT DISTINCT LINEA_PRODUCTO FROM ventas ORDER BY 1", con)["LINEA_PRODUCTO"].tolist()
    marcas = pd.read_sql(
        "SELECT DISTINCT MARCA FROM ventas WHERE MARCA != 'SIN IDENTIFICAR' ORDER BY 1", con
    )["MARCA"].tolist()
    con.close()
    return {"sucursales": sucursales, "lineas": lineas, "marcas": marcas}


def explorar_ventas(sucursal: str | None, linea: str | None, marca: str | None, limite: int = 500) -> pd.DataFrame:
    condiciones = []
    params: list = []

    if sucursal:
        condiciones.append("SUCURSAL = ?")
        params.append(sucursal)
    if linea:
        condiciones.append("LINEA_PRODUCTO = ?")
        params.append(linea)
    if marca:
        condiciones.append("MARCA = ?")
        params.append(marca)

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    params.append(limite)

    con = get_connection()
    df = pd.read_sql(
        f"""
        SELECT
            DATE(FECHA) AS fecha,
            SUCURSAL AS sucursal,
            MARCA AS marca,
            LINEA_PRODUCTO AS linea,
            PRODUCTO AS producto,
            CANTIDAD AS cantidad,
            PRECIO_FINAL AS precio_final
        FROM ventas
        {where}
        ORDER BY FECHA DESC
        LIMIT ?
        """,
        con,
        params=params,
    )
    con.close()
    return df
