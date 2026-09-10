"""
services/queries.py — Consultas analíticas sobre el mart de ventas.

Todas las funciones de contenido (KPIs, gráficos) aceptan los mismos seis
parámetros de filtro, para que la barra de filtros global (definida en
app.py, persiste entre páginas) controle lo que se muestra en cualquier
página del dashboard:

    sucursales: list[str] | None   -- None o [] = todas
    marcas: list[str] | None       -- None o [] = todas
    lineas: list[str] | None       -- None o [] = todas
    fecha_ini, fecha_fin: str "YYYY-MM-DD" | None
    umbral_mayorista: int | None   -- None = no excluir ninguna cuenta

`MATRIZ` se excluye SIEMPRE de las opciones de sucursal y de los datos --
no es un punto de venta al público (ver EDA, Sección 10). `SIN IDENTIFICAR`
se excluye de las opciones de marca. `umbral_mayorista` excluye del cálculo
cualquier IDENTIFICACION con más de N órdenes distintas EN EL RANGO DE
FECHA seleccionado -- deliberadamente independiente de sucursal/marca/línea
(ver instrucciones del proyecto, Sección 2.2): el estatus de "mayorista" de
un cliente no debería cambiar solo porque el usuario está mirando una
marca distinta.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.database import get_connection

MARCA_EXCLUIDA_DE_OPCIONES = "SIN IDENTIFICAR"
SUCURSAL_EXCLUIDA = "MATRIZ"
IDENTIFICACION_GENERICA = "CONSUMIDOR FINAL"  # FORMATO_ID, no la identificación en sí


def _subquery_mayoristas(fecha_ini, fecha_fin, umbral):
    """
    Subconsulta que resuelve a la lista de IDENTIFICACION con más de
    `umbral` órdenes distintas dentro del rango de fecha -- SIN filtrar por
    sucursal/marca/línea, a propósito (ver docstring del módulo). El
    "CONSUMIDOR FINAL" genérico se excluye de esta detección: es un mismo
    código compartido por miles de compradores de mostrador distintos, no
    un cliente identificable -- su conteo de órdenes no significa nada a
    nivel individual.
    """
    condiciones = ["SUCURSAL != ?", "FORMATO_ID != ?"]
    params: list = [SUCURSAL_EXCLUIDA, IDENTIFICACION_GENERICA]
    if fecha_ini:
        condiciones.append("DATE(FECHA) >= DATE(?)")
        params.append(fecha_ini)
    if fecha_fin:
        condiciones.append("DATE(FECHA) <= DATE(?)")
        params.append(fecha_fin)
    where = " AND ".join(condiciones)
    sql = (
        f"SELECT IDENTIFICACION FROM ventas WHERE {where} "
        f"GROUP BY IDENTIFICACION HAVING COUNT(DISTINCT ORDEN_ID) > ?"
    )
    params.append(umbral)
    return sql, params


def _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None, alias=""):
    """Construye la cláusula WHERE + parámetros a partir de los filtros globales."""
    pref = f"{alias}." if alias else ""
    condiciones = [f"{pref}SUCURSAL != ?"]
    params: list = [SUCURSAL_EXCLUIDA]

    if umbral_mayorista is not None:
        sub_sql, sub_params = _subquery_mayoristas(fecha_ini, fecha_fin, umbral_mayorista)
        condiciones.append(f"{pref}IDENTIFICACION NOT IN ({sub_sql})")
        params.extend(sub_params)

    if sucursales:
        condiciones.append(f"{pref}SUCURSAL IN ({','.join('?' * len(sucursales))})")
        params.extend(sucursales)
    if marcas:
        condiciones.append(f"{pref}MARCA IN ({','.join('?' * len(marcas))})")
        params.extend(marcas)
    if lineas:
        condiciones.append(f"{pref}LINEA_PRODUCTO IN ({','.join('?' * len(lineas))})")
        params.extend(lineas)
    if fecha_ini:
        condiciones.append(f"DATE({pref}FECHA) >= DATE(?)")
        params.append(fecha_ini)
    if fecha_fin:
        condiciones.append(f"DATE({pref}FECHA) <= DATE(?)")
        params.append(fecha_fin)

    return "WHERE " + " AND ".join(condiciones), params


def rango_fechas_disponible() -> tuple[str, str]:
    con = get_connection()
    fila = pd.read_sql("SELECT MIN(DATE(FECHA)) AS min_f, MAX(DATE(FECHA)) AS max_f FROM ventas", con).iloc[0]
    con.close()
    return fila["min_f"], fila["max_f"]


def opciones_cascada(sucursales_sel, marcas_sel, lineas_sel, fecha_ini, fecha_fin, umbral_mayorista=None) -> dict:
    """
    Para cada filtro, calcula qué opciones siguen teniendo datos DADAS las
    selecciones ACTUALES de los otros dos filtros + fecha + umbral de
    mayoristas -- esto es lo que hace que los selectores se actualicen en
    cascada. Cada lista se calcula ignorando su propio filtro (para no
    auto-restringirse a lo ya elegido).
    """
    con = get_connection()

    where_para_sucursal, params_s = _where_clause(None, marcas_sel, lineas_sel, fecha_ini, fecha_fin, umbral_mayorista)
    sucursales = pd.read_sql(
        f"SELECT DISTINCT SUCURSAL FROM ventas {where_para_sucursal} ORDER BY 1", con, params=params_s
    )["SUCURSAL"].tolist()

    where_para_marca, params_m = _where_clause(sucursales_sel, None, lineas_sel, fecha_ini, fecha_fin, umbral_mayorista)
    marcas = pd.read_sql(
        f"SELECT DISTINCT MARCA FROM ventas {where_para_marca} AND MARCA != ? ORDER BY 1",
        con, params=params_m + [MARCA_EXCLUIDA_DE_OPCIONES],
    )["MARCA"].tolist()

    where_para_linea, params_l = _where_clause(sucursales_sel, marcas_sel, None, fecha_ini, fecha_fin, umbral_mayorista)
    lineas = pd.read_sql(
        f"SELECT DISTINCT LINEA_PRODUCTO FROM ventas {where_para_linea} ORDER BY 1", con, params=params_l
    )["LINEA_PRODUCTO"].tolist()

    con.close()
    return {"sucursales": sucursales, "marcas": marcas, "lineas": lineas}


def hay_datos(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None) -> bool:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    n = pd.read_sql(f"SELECT COUNT(*) AS n FROM ventas {where}", con, params=params).iloc[0]["n"]
    con.close()
    return n > 0


def resumen_general(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None) -> dict:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)

    ordenes = pd.read_sql(
        f"SELECT ORDEN_ID, SUM(PRECIO_FINAL) AS valor_orden FROM ventas {where} GROUP BY ORDEN_ID",
        con, params=params,
    )
    totales = pd.read_sql(
        f"""SELECT SUM(PRECIO_FINAL) AS ventas_totales, SUM(CANTIDAD) AS unidades_totales,
                   MIN(FECHA) AS fecha_min, MAX(FECHA) AS fecha_max
            FROM ventas {where}""",
        con, params=params,
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


def deltas_periodo_anterior(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None) -> dict:
    """
    Variación % de cada KPI vs. el periodo INMEDIATAMENTE ANTERIOR, del
    mismo largo en días -- para que los KPI de Resumen respondan "¿esto es
    bueno o malo?" sin que el usuario tenga que comparar mentalmente
    contra otro periodo (hoja de ruta original del proyecto, pendiente
    desde el primer día).

    Devuelve None en cada delta si no hay un fecha_ini/fecha_fin definido,
    o si el periodo anterior no tiene ventas con qué comparar (división
    por cero) -- en vez de mostrar un porcentaje engañoso.
    """
    sin_deltas = {"ventas_totales": None, "ordenes": None, "ticket_promedio": None, "unidades_totales": None}
    if not fecha_ini or not fecha_fin:
        return sin_deltas

    inicio = pd.Timestamp(fecha_ini)
    fin = pd.Timestamp(fecha_fin)
    largo_dias = (fin - inicio).days + 1
    fin_anterior = inicio - pd.Timedelta(days=1)
    inicio_anterior = fin_anterior - pd.Timedelta(days=largo_dias - 1)

    actual = resumen_general(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    anterior = resumen_general(
        sucursales, marcas, lineas, inicio_anterior.strftime("%Y-%m-%d"), fin_anterior.strftime("%Y-%m-%d"),
        umbral_mayorista,
    )

    def _delta(actual_val, anterior_val):
        if not anterior_val:
            return None
        return (actual_val - anterior_val) / anterior_val * 100

    return {
        "ventas_totales": _delta(actual["ventas_totales"], anterior["ventas_totales"]),
        "ordenes": _delta(actual["ordenes"], anterior["ordenes"]),
        "ticket_promedio": _delta(actual["ticket_promedio"], anterior["ticket_promedio"]),
        "unidades_totales": _delta(actual["unidades_totales"], anterior["unidades_totales"]),
    }


def distribucion_ticket(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None) -> pd.DataFrame:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"SELECT ORDEN_ID, SUM(PRECIO_FINAL) AS valor_orden FROM ventas {where} GROUP BY ORDEN_ID",
        con, params=params,
    )
    con.close()
    return df


def ventas_diarias_por_mes(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None) -> pd.DataFrame:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    diario = pd.read_sql(
        f"""SELECT strftime('%Y-%m', FECHA) AS mes, DATE(FECHA) AS dia, SUM(PRECIO_FINAL) AS ventas_dia
            FROM ventas {where} GROUP BY mes, dia""",
        con, params=params,
    )
    con.close()
    resumen = diario.groupby("mes").agg(
        promedio_diario=("ventas_dia", "mean"), dias_con_datos=("dia", "nunique"),
    ).reset_index()
    # "Incompleto" cubre dos causas distintas: (a) corte de la muestra a
    # mitad de mes (afecta a todos los filtros, solo el último mes del
    # rango global), o (b) la sucursal/marca/línea filtrada no tuvo
    # actividad todo el mes (ej. tienda que abrió a fin de mes). Se
    # etiqueta neutral en vez de asumir cuál de las dos aplica.
    resumen["incompleto"] = resumen["dias_con_datos"] < 25
    return resumen


def ventas_por_dia_semana(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None) -> pd.DataFrame:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(f"SELECT DATE(FECHA) AS dia, SUM(PRECIO_FINAL) AS ventas FROM ventas {where} GROUP BY dia", con,
                     params=params)
    con.close()

    df["dia"] = pd.to_datetime(df["dia"])
    df["dow"] = df["dia"].dt.dayofweek
    nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    resumen = df.groupby("dow")["ventas"].mean().reindex(range(7))
    resumen.index = nombres
    return resumen.reset_index().rename(columns={"index": "dia_semana", "ventas": "venta_promedio"})


def ventas_por_linea(sucursales, marcas, fecha_ini, fecha_fin, umbral_mayorista=None) -> pd.DataFrame:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, None, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"SELECT LINEA_PRODUCTO AS linea, SUM(PRECIO_FINAL) AS ventas, SUM(CANTIDAD) AS unidades FROM ventas {where} GROUP BY linea ORDER BY ventas DESC",
        con, params=params,
    )
    con.close()
    total = df["ventas"].sum()
    df["porcentaje"] = (df["ventas"] / total * 100).round(2) if total else 0
    return df


def ventas_por_marca(sucursales, lineas, fecha_ini, fecha_fin, umbral_mayorista=None, top_n: int = 12) -> pd.DataFrame:
    con = get_connection()
    where, params = _where_clause(sucursales, None, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"SELECT MARCA AS marca, SUM(PRECIO_FINAL) AS ventas, SUM(CANTIDAD) AS unidades FROM ventas {where} AND MARCA != ? GROUP BY marca ORDER BY ventas DESC LIMIT ?",
        con, params=params + [MARCA_EXCLUIDA_DE_OPCIONES, top_n],
    )
    con.close()
    return df


def ventas_por_sucursal(marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None) -> pd.DataFrame:
    """
    Incluye última venta y días de inactividad por sucursal -- hallazgo
    real (PB Scala sin vender desde el 2 de febrero, Punto Blanco desde
    el 16 de enero) que hasta ahora solo se veía si alguien filtraba esa
    tienda específica en Predicción. Una tabla de resumen por sucursal sin
    esto puede mostrar un número casi en cero sin ninguna explicación de
    por qué -- se agrega aquí para que sea visible donde el gerente
    naturalmente va a mirar primero (la tabla de todas las tiendas).
    """
    con = get_connection()
    where, params = _where_clause(None, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"""SELECT SUCURSAL AS sucursal, SUM(PRECIO_FINAL) AS ventas, SUM(CANTIDAD) AS unidades,
                   COUNT(DISTINCT ORDEN_ID) AS ordenes, MAX(DATE(FECHA)) AS ultima_venta
            FROM ventas {where} GROUP BY sucursal ORDER BY ventas DESC""",
        con, params=params,
    )
    con.close()

    if df.empty:
        df["dias_desde_ultima_venta"] = []
        return df

    if fecha_fin:
        fecha_referencia = pd.Timestamp(fecha_fin)
    else:
        fecha_referencia = pd.Timestamp(df["ultima_venta"].max())

    df["dias_desde_ultima_venta"] = (fecha_referencia - pd.to_datetime(df["ultima_venta"])).dt.days
    return df


def mix_linea_por_sucursal(marcas, fecha_ini, fecha_fin, umbral_mayorista=None) -> pd.DataFrame:
    con = get_connection()
    where, params = _where_clause(None, marcas, None, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"SELECT SUCURSAL AS sucursal, LINEA_PRODUCTO AS linea, SUM(PRECIO_FINAL) AS ventas FROM ventas {where} GROUP BY sucursal, linea",
        con, params=params,
    )
    con.close()
    tabla = df.pivot_table(index="sucursal", columns="linea", values="ventas", aggfunc="sum", fill_value=0)
    if tabla.empty:
        return tabla
    return (tabla.div(tabla.sum(axis=1), axis=0) * 100).round(1)


def explorar_ventas(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista=None,
                    limite: int = 500) -> pd.DataFrame:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"""SELECT DATE(FECHA) AS fecha, ORDEN_ID AS orden, SUCURSAL AS sucursal, MARCA AS marca,
                   LINEA_PRODUCTO AS linea, PRODUCTO AS producto, CANTIDAD AS cantidad, PRECIO_FINAL AS precio_final
            FROM ventas {where} ORDER BY FECHA DESC LIMIT ?""",
        con, params=params + [limite],
    )
    con.close()
    return df


def pronostico_corto_plazo(sucursales, fecha_ini, fecha_fin, umbral_mayorista=None, semanas_backtest: int = 4) -> dict:
    """
    Pronóstico baseline (MEDIANA estacional por día de semana), filtrable
    solo por sucursal, fecha y umbral de mayoristas -- NO por marca/línea.

    Historial de decisión de arquitectura (importante si se vuelve a tocar):
    en una iteración anterior, este modelo SIEMPRE entrenaba sobre el
    agregado y distribuía la proyección a la tienda por participación
    histórica. El cliente lo cuestionó con razón: quería ver la precisión
    real de CADA tienda. Se probó shrinkage (mezclar patrón propio con el
    agregado) y NO mejoró nada de forma medible -- la causa real es que
    cada tienda maneja apenas 2-18 órdenes por día (vs ~63/día el
    agregado), ruido genuino de conteo de transacciones, no un problema de
    "forma" de patrón que se pueda tomar prestada.

    Segunda ronda de mejora, esta vez sí con resultado real, verificado
    con validación de MÚLTIPLES pliegues (6, no 1) para no juzgar con una
    sola ventana de 4 semanas que resultó ser ruidosa en sí misma
    (variación de hasta ±20 puntos de MAPE entre pliegues distintos):
    - Usar MEDIANA en vez de promedio por día de semana: mejora
      consistente en las tiendas probadas (Centro Comercial Iñaquito
      54.4%->48.7% de error, Mall El Jardín 50.9%->48.2%) -- más robusta
      a que una sola venta grande en un día puntual distorsione el
      patrón.
    - Modelos más complejos (Holt-Winters, OLS con tendencia) NO
      superaron a la mediana simple en ningún caso probado -- confirma,
      a nivel de tienda individual, el mismo hallazgo que ya teníamos a
      nivel agregado en el EDA (Sección 12): más parámetros no ayudan sin
      más datos que los sostengan.
    - La "precisión" ahora es el PROMEDIO de varios pliegues de backtest,
      no un solo mes -- un número más estable, menos dependiente de qué
      4 semanas específicas te tocó mirar.
    """
    con = get_connection()

    # --- Serie de la sucursal filtrada (o el agregado, si no hay filtro) ---
    where, params = _where_clause(sucursales, None, None, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"SELECT DATE(FECHA) AS dia, SUM(PRECIO_FINAL) AS ventas FROM ventas {where} GROUP BY dia ORDER BY dia",
        con, params=params,
    )

    if len(df) < 21:
        con.close()
        return {"suficiente": False}

    df["dia"] = pd.to_datetime(df["dia"])
    df["dow"] = df["dia"].dt.dayofweek
    df = df.sort_values("dia").reset_index(drop=True)

    # Tamaño de CADA pliegue de validación: 1 semana (7 días), no las 4
    # semanas que se muestran en el gráfico -- si se usaran pliegues de 4
    # semanas para los 6 pliegues de validación, se consumirían 168 días
    # solo en pruebas, dejando al pliegue más antiguo con apenas ~25 días
    # para entrenar (bug real, encontrado al no coincidir estos resultados
    # con el experimento de validación hecho aparte). Con pliegues de 1
    # semana, 6 pliegues consumen 42 días, dejando entrenamiento
    # razonable incluso para el pliegue más antiguo.
    dias_por_pliegue = 7
    dias_backtest = min(semanas_backtest * 7, len(df) // 3)  # tamaño del período MOSTRADO en el gráfico
    max_pliegues = 6
    n_pliegues = min(max_pliegues, max(1, (len(df) - 21) // dias_por_pliegue))

    mapes_pliegues = []
    for i in range(n_pliegues):
        corte = len(df) - (n_pliegues - i) * dias_por_pliegue
        if corte < 14:
            continue
        entrenamiento = df.iloc[:corte]
        prueba_pliegue = df.iloc[corte:corte + dias_por_pliegue].copy()
        if prueba_pliegue.empty:
            continue

        mediana_por_dow = entrenamiento.groupby("dow")["ventas"].median()
        prueba_pliegue["prediccion"] = prueba_pliegue["dow"].map(mediana_por_dow)
        error_pct = (prueba_pliegue["ventas"] - prueba_pliegue["prediccion"]).abs() / prueba_pliegue["ventas"].replace(
            0, pd.NA)
        mape_pliegue = float(error_pct.mean() * 100) if len(prueba_pliegue) else None
        if mape_pliegue is not None:
            mapes_pliegues.append(mape_pliegue)

    mape = float(np.mean(mapes_pliegues)) if mapes_pliegues else None

    # Para el GRÁFICO (no para el número de precisión): entrenar con todo
    # menos las últimas `dias_backtest` (4 semanas) y mostrar esa ventana
    # -- son fechas recientes que el usuario reconoce visualmente. El
    # número de precisión de arriba, en cambio, es el promedio de los
    # pliegues de 1 semana calculados arriba, más estable.
    entrenamiento_grafico = df.iloc[:-dias_backtest]
    prueba = df.iloc[-dias_backtest:].copy()
    mediana_grafico = entrenamiento_grafico.groupby("dow")["ventas"].median()
    prueba["prediccion"] = prueba["dow"].map(mediana_grafico)

    ultimo_dia_tienda = df["dia"].max()

    # --- Fecha de referencia para "próximos 14 días": el FINAL DEL RANGO
    # GLOBAL filtrado (o el máximo real de todo el mart si no se especificó
    # fecha_fin), NUNCA la última venta de la tienda individual. Bug real
    # encontrado con PB Scala: su última venta fue el 2 de febrero (no
    # vende desde entonces) -- anclar el forecast a esa fecha generaba una
    # "proyección de próximos 14 días" para el 3-16 de febrero, mostrada
    # como si fueran fechas futuras, cuando el resto del panel está mirando
    # hasta julio. El anclaje correcto es el rango que el usuario está
    # mirando, no el historial propio (posiblemente desactualizado) de
    # cada tienda.
    if fecha_fin:
        fecha_referencia = pd.Timestamp(fecha_fin)
    else:
        ref_query = pd.read_sql("SELECT MAX(DATE(FECHA)) AS f FROM ventas WHERE SUCURSAL != 'MATRIZ'", con)
        fecha_referencia = pd.Timestamp(ref_query.iloc[0]["f"])

    dias_desde_ultima_venta = (fecha_referencia - ultimo_dia_tienda).days

    proximos = pd.date_range(fecha_referencia + pd.Timedelta(days=1), periods=14, freq="D")
    mediana_todo = df.groupby("dow")["ventas"].median()
    forecast = pd.DataFrame({"dia": proximos, "dow": proximos.dayofweek})
    forecast["prediccion"] = forecast["dow"].map(mediana_todo)

    resultado = {
        "suficiente": True,
        "es_agregado": not bool(sucursales),
        "historico": df[["dia", "ventas"]],
        "backtest": prueba[["dia", "ventas", "prediccion"]],
        "forecast": forecast[["dia", "prediccion"]],
        "mape_pct": mape,
        "semanas_historia": round(len(df) / 7, 1),
        "dias_desde_ultima_venta": int(dias_desde_ultima_venta),
        "ordenes_promedio_dia": None,
        "mape_agregado_pct": None,
    }

    # --- Transparencia adicional cuando se filtra una tienda específica ---
    if sucursales:
        ordenes_dia = pd.read_sql(
            f"SELECT DATE(FECHA) AS dia, COUNT(DISTINCT ORDEN_ID) AS n FROM ventas {where} GROUP BY dia",
            con, params=params,
        )
        resultado["ordenes_promedio_dia"] = float(ordenes_dia["n"].mean()) if len(ordenes_dia) else 0.0

        # Agregado como referencia de comparación (mismo periodo, no reemplaza el número de la tienda)
        where_agg, params_agg = _where_clause(None, None, None, fecha_ini, fecha_fin, umbral_mayorista)
        df_agg = pd.read_sql(
            f"SELECT DATE(FECHA) AS dia, SUM(PRECIO_FINAL) AS ventas FROM ventas {where_agg} GROUP BY dia ORDER BY dia",
            con, params=params_agg,
        )
        if len(df_agg) >= 21:
            df_agg["dia"] = pd.to_datetime(df_agg["dia"])
            df_agg["dow"] = df_agg["dia"].dt.dayofweek
            df_agg = df_agg.sort_values("dia").reset_index(drop=True)
            corte_agg = min(semanas_backtest * 7, len(df_agg) // 3)
            train_agg, test_agg = df_agg.iloc[:-corte_agg], df_agg.iloc[-corte_agg:].copy()
            prom_agg = train_agg.groupby("dow")["ventas"].median()
            test_agg["prediccion"] = test_agg["dow"].map(prom_agg)
            err_agg = (test_agg["ventas"] - test_agg["prediccion"]).abs() / test_agg["ventas"].replace(0, pd.NA)
            resultado["mape_agregado_pct"] = float(err_agg.mean() * 100) if len(test_agg) else None

    con.close()
    return resultado


# ---------------------------------------------------------------------------
# Detección de cuentas mayoristas -- página nueva "Cuentas mayoristas".
# Deliberadamente sin filtro de sucursal/marca/línea: el objetivo es ver el
# comportamiento del cliente en TODO el negocio, no en un recorte de él.
# ---------------------------------------------------------------------------
def ranking_clientes(fecha_ini, fecha_fin, limite: int = 40) -> pd.DataFrame:
    """Clientes identificados (excluye 'consumidor final'), ordenados por
    número de órdenes distintas -- la tabla de la página de detección."""
    con = get_connection()
    condiciones = ["SUCURSAL != ?", "FORMATO_ID != ?"]
    params: list = [SUCURSAL_EXCLUIDA, IDENTIFICACION_GENERICA]
    if fecha_ini:
        condiciones.append("DATE(FECHA) >= DATE(?)")
        params.append(fecha_ini)
    if fecha_fin:
        condiciones.append("DATE(FECHA) <= DATE(?)")
        params.append(fecha_fin)
    where = " AND ".join(condiciones)

    df = pd.read_sql(
        f"""SELECT IDENTIFICACION AS identificacion, CLIENTE AS cliente, FORMATO_ID AS formato,
                   COUNT(DISTINCT ORDEN_ID) AS ordenes, SUM(PRECIO_FINAL) AS gasto_total
            FROM ventas WHERE {where}
            GROUP BY IDENTIFICACION, CLIENTE, FORMATO_ID
            ORDER BY ordenes DESC LIMIT ?""",
        con, params=params + [limite],
    )
    con.close()
    df["ticket_promedio"] = (df["gasto_total"] / df["ordenes"]).round(2)
    return df


def listado_clientes(fecha_ini, fecha_fin, umbral_mayorista=None) -> pd.DataFrame:
    """
    Listado COMPLETO de clientes identificados (no un top 40 como
    ranking_clientes) -- para la tabla de la página Clientes, con filtro
    nativo por columna para que se pueda buscar un cliente puntual por
    identificación o nombre. Respeta el umbral de mayoristas (si está
    activo) para que la tabla no incluya las cuentas corporativas que ya
    se excluyen del resto de la página.
    """
    con = get_connection()
    condiciones = ["SUCURSAL != ?", "FORMATO_ID != ?"]
    params: list = [SUCURSAL_EXCLUIDA, IDENTIFICACION_GENERICA]
    if umbral_mayorista is not None:
        sub_sql, sub_params = _subquery_mayoristas(fecha_ini, fecha_fin, umbral_mayorista)
        condiciones.append(f"IDENTIFICACION NOT IN ({sub_sql})")
        params.extend(sub_params)
    if fecha_ini:
        condiciones.append("DATE(FECHA) >= DATE(?)")
        params.append(fecha_ini)
    if fecha_fin:
        condiciones.append("DATE(FECHA) <= DATE(?)")
        params.append(fecha_fin)
    where = " AND ".join(condiciones)

    df = pd.read_sql(
        f"""SELECT IDENTIFICACION AS identificacion, CLIENTE AS cliente, FORMATO_ID AS formato,
                   MIN(DATE(FECHA)) AS primera_compra, MAX(DATE(FECHA)) AS ultima_compra,
                   COUNT(DISTINCT ORDEN_ID) AS ordenes, SUM(PRECIO_FINAL) AS gasto_total
            FROM ventas WHERE {where}
            GROUP BY IDENTIFICACION, CLIENTE, FORMATO_ID
            ORDER BY gasto_total DESC""",
        con, params=params,
    )
    con.close()
    df["ticket_promedio"] = (df["gasto_total"] / df["ordenes"]).round(2)
    df["tipo"] = df["ordenes"].apply(lambda n: "Recurrente" if n >= 2 else "Nuevo/única compra")
    return df


def resumen_mayoristas(fecha_ini, fecha_fin, umbral: int) -> dict:
    """KPIs de cabecera para la página de detección: cuántas cuentas caen
    sobre el umbral actual y qué porcentaje del negocio representan."""
    con = get_connection()

    condiciones = ["SUCURSAL != ?"]
    params: list = [SUCURSAL_EXCLUIDA]
    if fecha_ini:
        condiciones.append("DATE(FECHA) >= DATE(?)")
        params.append(fecha_ini)
    if fecha_fin:
        condiciones.append("DATE(FECHA) <= DATE(?)")
        params.append(fecha_fin)
    where = " AND ".join(condiciones)

    total = pd.read_sql(f"SELECT SUM(PRECIO_FINAL) AS ventas FROM ventas WHERE {where}", con, params=params).iloc[0][
                "ventas"] or 0.0

    sub_sql, sub_params = _subquery_mayoristas(fecha_ini, fecha_fin, umbral)
    mayoristas = pd.read_sql(
        f"""SELECT COUNT(DISTINCT IDENTIFICACION) AS n_cuentas, SUM(PRECIO_FINAL) AS ventas_mayoristas
            FROM ventas WHERE {where} AND IDENTIFICACION IN ({sub_sql})""",
        con, params=params + sub_params,
    ).iloc[0]
    con.close()

    ventas_mayoristas = float(mayoristas["ventas_mayoristas"] or 0)
    return {
        "n_cuentas": int(mayoristas["n_cuentas"] or 0),
        "ventas_mayoristas": ventas_mayoristas,
        "ventas_totales": float(total),
        "porcentaje": (ventas_mayoristas / total * 100) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# Serie temporal con granularidad y métrica configurables -- generaliza lo
# que antes era una sola vista fija (promedio diario por mes). Permite
# elegir Ventas/Órdenes/Unidades y Día/Semana/Mes desde la página Resumen.
# ---------------------------------------------------------------------------
_METRICA_SQL = {
    "ventas": "SUM(PRECIO_FINAL)",
    "ordenes": "COUNT(DISTINCT ORDEN_ID)",
    "unidades": "SUM(CANTIDAD)",
}


def serie_temporal(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista, metrica: str,
                   granularidad: str) -> pd.DataFrame:
    """
    metrica: 'ventas' | 'ordenes' | 'unidades'
    granularidad: 'dia' | 'semana' | 'mes'

    Siempre agrega primero por día (nivel atómico) y luego reagrupa en
    Python -- así se calcula la cobertura real de cada periodo (cuántos
    días de calendario tiene dato adentro) sin duplicar lógica SQL por
    cada nivel de granularidad.
    """
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    expr = _METRICA_SQL[metrica]
    diario = pd.read_sql(
        f"SELECT DATE(FECHA) AS dia, {expr} AS valor FROM ventas {where} GROUP BY dia ORDER BY dia",
        con, params=params,
    )
    con.close()

    if diario.empty:
        return diario

    diario["dia"] = pd.to_datetime(diario["dia"])

    if granularidad == "dia":
        diario["periodo"] = diario["dia"].dt.strftime("%d/%m/%Y")
        diario["incompleto"] = False  # un día es la unidad atómica, siempre "completo"
        return diario[["periodo", "valor", "incompleto"]]

    if granularidad == "semana":
        diario["clave"] = diario["dia"].dt.to_period("W-SUN")
        dias_esperados = 7
        etiqueta = lambda p: f"{p.start_time.strftime('%d/%m')}–{p.end_time.strftime('%d/%m')}"
    else:  # mes
        diario["clave"] = diario["dia"].dt.to_period("M")
        etiqueta = lambda p: p.strftime("%b %Y")

    if granularidad == "mes":
        resumen = diario.groupby("clave").agg(valor=("valor", "sum"), dias_con_datos=("dia", "nunique")).reset_index()
        resumen["dias_esperados"] = resumen["clave"].apply(lambda p: p.days_in_month)
    else:
        resumen = diario.groupby("clave").agg(valor=("valor", "sum"), dias_con_datos=("dia", "nunique")).reset_index()
        resumen["dias_esperados"] = dias_esperados

    resumen["periodo"] = resumen["clave"].apply(etiqueta)
    resumen["incompleto"] = resumen["dias_con_datos"] < (resumen["dias_esperados"] * 0.8)
    return resumen[["periodo", "valor", "incompleto"]]


# ---------------------------------------------------------------------------
# Clientes: nuevos vs. recurrentes, y resumen de captura de identificación.
# Deliberadamente SOLO filtrado por fecha y umbral de mayoristas -- el
# estatus de un cliente (nuevo/recurrente, identificado/consumidor final)
# es una propiedad del cliente, no del producto que se esté mirando (mismo
# criterio que la página de Mayoristas).
# ---------------------------------------------------------------------------
def resumen_clientes(fecha_ini, fecha_fin, umbral_mayorista) -> dict:
    con = get_connection()
    condiciones = ["SUCURSAL != ?"]
    params: list = [SUCURSAL_EXCLUIDA]
    if umbral_mayorista is not None:
        sub_sql, sub_params = _subquery_mayoristas(fecha_ini, fecha_fin, umbral_mayorista)
        condiciones.append(f"IDENTIFICACION NOT IN ({sub_sql})")
        params.extend(sub_params)
    if fecha_ini:
        condiciones.append("DATE(FECHA) >= DATE(?)")
        params.append(fecha_ini)
    if fecha_fin:
        condiciones.append("DATE(FECHA) <= DATE(?)")
        params.append(fecha_fin)
    where = " AND ".join(condiciones)

    df = pd.read_sql(
        f"""SELECT ORDEN_ID, IDENTIFICACION, FORMATO_ID, PRECIO_FINAL
            FROM ventas WHERE {where}""",
        con, params=params,
    )
    con.close()

    ordenes = df.groupby("ORDEN_ID").agg(
        identificacion=("IDENTIFICACION", "first"),
        formato=("FORMATO_ID", "first"),
        valor=("PRECIO_FINAL", "sum"),
    )
    es_generico = ordenes["formato"] == IDENTIFICACION_GENERICA
    ordenes_id = ordenes[~es_generico]

    por_cliente = ordenes_id.groupby("identificacion").size()
    clientes_recurrentes = int((por_cliente >= 2).sum())
    clientes_totales = int(len(por_cliente))

    return {
        "ordenes_totales": int(len(ordenes)),
        "ordenes_consumidor_final": int(es_generico.sum()),
        "pct_ordenes_consumidor_final": float(es_generico.mean() * 100) if len(ordenes) else 0.0,
        "ventas_consumidor_final": float(ordenes[es_generico]["valor"].sum()),
        "pct_ventas_consumidor_final": float(ordenes[es_generico]["valor"].sum() / ordenes["valor"].sum() * 100) if
        ordenes["valor"].sum() else 0.0,
        "ticket_consumidor_final": float(ordenes[es_generico]["valor"].mean()) if es_generico.sum() else 0.0,
        "ticket_identificado": float(ordenes_id["valor"].mean()) if len(ordenes_id) else 0.0,
        "clientes_identificados": clientes_totales,
        "clientes_recurrentes": clientes_recurrentes,
        "tasa_recompra": (clientes_recurrentes / clientes_totales * 100) if clientes_totales else 0.0,
    }


def clientes_nuevos_vs_recurrentes(fecha_ini, fecha_fin, umbral_mayorista) -> pd.DataFrame:
    """Por mes: cuántas órdenes son de clientes en su primer mes de compra
    ('nuevo') vs. de clientes que ya habían comprado antes ('recurrente')."""
    con = get_connection()
    condiciones = ["SUCURSAL != ?", "FORMATO_ID != ?"]
    params: list = [SUCURSAL_EXCLUIDA, IDENTIFICACION_GENERICA]
    if umbral_mayorista is not None:
        sub_sql, sub_params = _subquery_mayoristas(fecha_ini, fecha_fin, umbral_mayorista)
        condiciones.append(f"IDENTIFICACION NOT IN ({sub_sql})")
        params.extend(sub_params)
    if fecha_ini:
        condiciones.append("DATE(FECHA) >= DATE(?)")
        params.append(fecha_ini)
    if fecha_fin:
        condiciones.append("DATE(FECHA) <= DATE(?)")
        params.append(fecha_fin)
    where = " AND ".join(condiciones)

    df = pd.read_sql(
        f"SELECT ORDEN_ID, IDENTIFICACION, FECHA FROM ventas WHERE {where}",
        con, params=params,
    )
    con.close()

    if df.empty:
        return df

    df["FECHA"] = pd.to_datetime(df["FECHA"])
    df["mes"] = df["FECHA"].dt.to_period("M")

    primera_compra = df.groupby("IDENTIFICACION")["FECHA"].min().dt.to_period("M")
    df["es_nuevo"] = df["IDENTIFICACION"].map(primera_compra) == df["mes"]

    ordenes = df.groupby(["mes", "ORDEN_ID"]).agg(es_nuevo=("es_nuevo", "first")).reset_index()
    resumen = ordenes.groupby(["mes", "es_nuevo"]).size().reset_index(name="ordenes")
    resumen["periodo"] = resumen["mes"].astype(str)
    resumen["tipo"] = resumen["es_nuevo"].map({True: "Nuevos", False: "Recurrentes"})
    return resumen[["periodo", "tipo", "ordenes"]]


# ---------------------------------------------------------------------------
# Pareto de productos -- ¿cuántos SKUs explican el 80% de las ventas?
# Filtrado por sucursal/marca/línea/fecha/mayorista, igual que el resto del
# panel (a diferencia de Clientes/Mayoristas, aquí sí tiene sentido cruzar
# por producto/tienda).
# ---------------------------------------------------------------------------
def pareto_productos(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista, top_n: int = 20) -> dict:
    con = get_connection()
    where, params = _where_clause(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_mayorista)
    df = pd.read_sql(
        f"""SELECT CODIGO AS codigo, PRODUCTO AS producto, SUM(PRECIO_FINAL) AS ventas
            FROM ventas {where} GROUP BY codigo, producto ORDER BY ventas DESC""",
        con, params=params,
    )
    con.close()

    if df.empty:
        return {"top": df, "n_skus": 0, "n_para_80": 0, "pct_skus_para_80": 0.0}

    total = df["ventas"].sum()
    df["acumulado_pct"] = df["ventas"].cumsum() / total * 100 if total else 0
    n_para_80 = int((df["acumulado_pct"] <= 80).sum()) + 1
    n_para_80 = min(n_para_80, len(df))

    return {
        "top": df.head(top_n).reset_index(drop=True),
        "n_skus": int(len(df)),
        "n_para_80": n_para_80,
        "pct_skus_para_80": (n_para_80 / len(df) * 100) if len(df) else 0.0,
    }
