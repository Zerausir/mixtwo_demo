"""
services/queries.py — Consultas analíticas sobre el mart de ventas.

Revisado tras el EDA (ver notebook EDA_mixtwo.ipynb) -- correcciones clave
respecto a la versión anterior:

1. "Transacción" = orden real (ORDEN_ID), no fila/línea de producto. La
   versión anterior contaba cada línea como una transacción, subestimando
   el ticket promedio en ~3x (revisar notebook, Hallazgo 2).
2. La tendencia temporal usa promedio DIARIO por mes, no suma por semana --
   la suma sin normalizar hace ver un periodo parcial (el mes en curso)
   como una caída cuando en realidad no lo es (Hallazgo 3).
3. MATRIZ se excluye por defecto de las comparaciones entre sucursales --
   no es un punto de venta al público comparable (Hallazgo 5).
"""
from __future__ import annotations

import pandas as pd

from services.database import get_connection


def resumen_general(incluir_matriz: bool = False) -> dict:
    """KPIs de cabecera, calculados a nivel de ORDEN real, no de línea."""
    con = get_connection()
    filtro = "" if incluir_matriz else "WHERE ES_PUNTO_VENTA = 1"

    ordenes = pd.read_sql(
        f"""
        SELECT ORDEN_ID, SUM(PRECIO_FINAL) AS valor_orden
        FROM ventas
        {filtro}
        GROUP BY ORDEN_ID
        """,
        con,
    )
    totales = pd.read_sql(
        f"""
        SELECT
            SUM(PRECIO_FINAL) AS ventas_totales,
            SUM(CANTIDAD) AS unidades_totales,
            MIN(FECHA) AS fecha_min,
            MAX(FECHA) AS fecha_max
        FROM ventas
        {filtro}
        """,
        con,
    ).iloc[0]
    con.close()

    return {
        "ventas_totales": float(totales["ventas_totales"] or 0),
        "unidades_totales": int(totales["unidades_totales"] or 0),
        "ordenes": int(len(ordenes)),
        "ticket_promedio": float(ordenes["valor_orden"].mean()) if len(ordenes) else 0.0,
        "ticket_mediana": float(ordenes["valor_orden"].median()) if len(ordenes) else 0.0,
        "fecha_min": totales["fecha_min"],
        "fecha_max": totales["fecha_max"],
    }


def distribucion_ticket(incluir_matriz: bool = False) -> pd.DataFrame:
    """Valor de cada orden real -- para el boxplot/histograma de ticket."""
    con = get_connection()
    filtro = "" if incluir_matriz else "WHERE ES_PUNTO_VENTA = 1"
    df = pd.read_sql(
        f"""
        SELECT ORDEN_ID, SUM(PRECIO_FINAL) AS valor_orden
        FROM ventas
        {filtro}
        GROUP BY ORDEN_ID
        """,
        con,
    )
    con.close()
    return df


def ventas_diarias_por_mes(incluir_matriz: bool = False) -> pd.DataFrame:
    """
    Promedio de venta DIARIA por mes -- comparación "like-for-like" que no
    penaliza el mes en curso por tener menos días con datos. Marca
    explícitamente si el último mes está incompleto.
    """
    con = get_connection()
    filtro = "" if incluir_matriz else "WHERE ES_PUNTO_VENTA = 1"
    diario = pd.read_sql(
        f"""
        SELECT
            strftime('%Y-%m', FECHA) AS mes,
            DATE(FECHA) AS dia,
            SUM(PRECIO_FINAL) AS ventas_dia
        FROM ventas
        {filtro}
        GROUP BY mes, dia
        """,
        con,
    )
    con.close()

    resumen = diario.groupby("mes").agg(
        promedio_diario=("ventas_dia", "mean"),
        dias_con_datos=("dia", "nunique"),
    ).reset_index()

    resumen["parcial"] = resumen["dias_con_datos"] < 25
    return resumen


def ventas_por_dia_semana(incluir_matriz: bool = False) -> pd.DataFrame:
    """Venta promedio por día de la semana -- estacionalidad semanal real."""
    con = get_connection()
    filtro = "" if incluir_matriz else "WHERE ES_PUNTO_VENTA = 1"
    df = pd.read_sql(
        f"""
        SELECT DATE(FECHA) AS dia, SUM(PRECIO_FINAL) AS ventas
        FROM ventas
        {filtro}
        GROUP BY dia
        """,
        con,
    )
    con.close()

    df["dia"] = pd.to_datetime(df["dia"])
    df["dow"] = df["dia"].dt.dayofweek  # 0=lunes
    nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    resumen = df.groupby("dow")["ventas"].mean().reindex(range(7))
    resumen.index = nombres
    return resumen.reset_index().rename(columns={"index": "dia_semana", "ventas": "venta_promedio"})


def ventas_por_linea() -> pd.DataFrame:
    con = get_connection()
    df = pd.read_sql(
        """
        SELECT
            LINEA_PRODUCTO AS linea,
            SUM(PRECIO_FINAL) AS ventas,
            SUM(CANTIDAD) AS unidades
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


def ventas_por_sucursal(incluir_matriz: bool = False) -> pd.DataFrame:
    con = get_connection()
    filtro = "" if incluir_matriz else "WHERE ES_PUNTO_VENTA = 1"
    df = pd.read_sql(
        f"""
        SELECT
            SUCURSAL AS sucursal,
            SUM(PRECIO_FINAL) AS ventas,
            SUM(CANTIDAD) AS unidades,
            COUNT(DISTINCT ORDEN_ID) AS ordenes
        FROM ventas
        {filtro}
        GROUP BY sucursal
        ORDER BY ventas DESC
        """,
        con,
    )
    con.close()
    return df


def mix_linea_por_sucursal(incluir_matriz: bool = True) -> pd.DataFrame:
    """
    Composición % de líneas dentro de cada sucursal -- para el heatmap de
    heterogeneidad. Incluye MATRIZ por defecto aquí, con la etiqueta
    visible, porque el punto del gráfico es justamente mostrar que MATRIZ
    no se comporta como el resto (ver Hallazgo 5 del EDA).
    """
    con = get_connection()
    filtro = "" if incluir_matriz else "WHERE ES_PUNTO_VENTA = 1"
    df = pd.read_sql(
        f"""
        SELECT SUCURSAL AS sucursal, LINEA_PRODUCTO AS linea, SUM(PRECIO_FINAL) AS ventas
        FROM ventas
        {filtro}
        GROUP BY sucursal, linea
        """,
        con,
    )
    con.close()

    tabla = df.pivot_table(index="sucursal", columns="linea", values="ventas", aggfunc="sum", fill_value=0)
    tabla_pct = tabla.div(tabla.sum(axis=1), axis=0) * 100
    return tabla_pct.round(1)


def opciones_filtro() -> dict:
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
            ORDEN_ID AS orden,
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


def pronostico_corto_plazo(semanas_backtest: int = 4) -> dict:
    """
    Pronóstico ingenuo estacional: para cada día de la semana, usa el
    promedio de ese mismo día en semanas anteriores. Deliberadamente
    simple -- es lo que los datos actuales pueden sostener de forma
    honesta (Hallazgo 4 del EDA: hay patrón semanal real, no hay
    estacionalidad anual). No es una red neuronal ni gradient boosting;
    es un baseline transparente con error medido -- lo apropiado para un
    demo con 6 meses de datos, no un modelo que promete más de lo que
    los datos pueden respaldar.
    """
    con = get_connection()
    df = pd.read_sql(
        """
        SELECT DATE(FECHA) AS dia, SUM(PRECIO_FINAL) AS ventas
        FROM ventas
        WHERE ES_PUNTO_VENTA = 1
        GROUP BY dia
        ORDER BY dia
        """,
        con,
    )
    con.close()

    df["dia"] = pd.to_datetime(df["dia"])
    df["dow"] = df["dia"].dt.dayofweek
    df = df.sort_values("dia").reset_index(drop=True)

    dias_backtest = semanas_backtest * 7
    entrenamiento = df.iloc[:-dias_backtest] if len(df) > dias_backtest else df.iloc[:0]
    prueba = df.iloc[-dias_backtest:] if len(df) > dias_backtest else df

    promedio_por_dow = entrenamiento.groupby("dow")["ventas"].mean()

    prueba = prueba.copy()
    prueba["prediccion"] = prueba["dow"].map(promedio_por_dow)
    prueba["error_abs_pct"] = (prueba["ventas"] - prueba["prediccion"]).abs() / prueba["ventas"].replace(0, pd.NA)
    mape = float(prueba["error_abs_pct"].mean() * 100) if len(prueba) else None

    ultimo_dia = df["dia"].max()
    proximos = pd.date_range(ultimo_dia + pd.Timedelta(days=1), periods=14, freq="D")
    promedio_todo = df.groupby("dow")["ventas"].mean()
    forecast = pd.DataFrame({"dia": proximos, "dow": proximos.dayofweek})
    forecast["prediccion"] = forecast["dow"].map(promedio_todo)

    return {
        "historico": df[["dia", "ventas"]],
        "backtest": prueba[["dia", "ventas", "prediccion"]],
        "forecast": forecast[["dia", "prediccion"]],
        "mape_pct": mape,
    }
