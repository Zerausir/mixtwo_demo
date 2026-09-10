from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from components.ui import con_carga, chart_header, empty_state, kpi_card, page_header, umbral_efectivo
from services.queries import pronostico_corto_plazo

dash.register_page(__name__, path="/prediccion", name="Predicción")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-sucursal", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
]

# Umbrales para elegir qué explicación mostrar -- ver _explicacion_tienda()
DIAS_SIN_ACTIVIDAD_UMBRAL = 14  # más de 2 semanas sin vender -> alerta, no es un tema de modelo
SEMANAS_HISTORIA_UMBRAL = 15  # menos de ~15 semanas -> el patrón todavía se está formando


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Predicción de ventas — corto plazo",
            "Esta página solo se filtra por sucursal y fecha (no por marca ni línea de producto) "
            "— es la combinación que se validó como confiable antes de mostrarla.",
        ),
        con_carga("carga-prediccion-contenido", html.Div(id="prediccion-contenido")),
    ])


def _fig_backtest(historico, backtest) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=historico["dia"], y=historico["ventas"], mode="lines",
                             line=dict(color="#EDE1DD", width=1.5), name="Histórico", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=backtest["dia"], y=backtest["ventas"], mode="lines+markers",
                             line=dict(color="#201A1A", width=2), name="Lo que realmente pasó",
                             hovertemplate="%{x}<br>Real: $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=backtest["dia"], y=backtest["prediccion"], mode="lines+markers",
                             line=dict(color="#9C4F5C", width=2, dash="dash"), name="Lo que el modelo predijo",
                             hovertemplate="%{x}<br>Predicción: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(margin=dict(l=40, r=20, t=20, b=40), height=360,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis_title="Ventas (USD)", font=FONT, legend=dict(orientation="h", y=1.15))
    return fig


def _fig_forecast(forecast) -> go.Figure:
    fig = go.Figure(go.Bar(x=forecast["dia"], y=forecast["prediccion"], marker_color="#9C4F5C",
                           hovertemplate="%{x}<br>Proyección: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(margin=dict(l=40, r=20, t=20, b=40), height=300,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis_title="Venta proyectada (USD)", font=FONT)
    return fig


def _explicacion_tienda(resultado: dict, nombre_tienda: str) -> html.Div:
    """
    Cuadro explicativo ESPECÍFICO de la tienda filtrada -- no un texto
    genérico igual para las 9. Se elige una de tres narrativas según el
    diagnóstico real de los datos de esa tienda (ver umbrales arriba):

    (A) Sin actividad reciente: no es un problema del modelo, es que la
        tienda dejó de vender -- se descubrió con PB Scala (última venta
        2 de febrero, 161 días sin registrar nada). Antes de este fix, el
        forecast de "próximos 14 días" se anclaba a la última venta DE LA
        TIENDA en vez del rango global filtrado -- para PB Scala eso
        mostraba una "proyección futura" para el 3-16 de febrero, ya
        pasada hace meses, disfrazada de proyección real. Corregido para
        anclarse siempre al rango global.
    (B) Historia corta: la tienda es relativamente nueva (o reabrió
        recientemente) -- la precisión limitada es de madurez de datos,
        se resuelve con tiempo, no con mejor modelado.
    (C) Tienda madura: historia completa y actividad reciente -- la
        precisión limitada es ruido estadístico genuino (pocas órdenes
        por día), no falta de datos ni defecto del modelo.
    """
    dias_inactiva = resultado["dias_desde_ultima_venta"]
    semanas = resultado["semanas_historia"]
    ordenes_dia = resultado["ordenes_promedio_dia"]
    precision = 100 - resultado["mape_pct"] if resultado["mape_pct"] is not None else None

    if dias_inactiva > DIAS_SIN_ACTIVIDAD_UMBRAL:
        return html.Div(className="note-box critical", children=[
            html.Strong("⚠ Esta tienda no tiene actividad reciente: "),
            f"la última venta registrada de {nombre_tienda} fue hace {dias_inactiva} días. "
            f"El {precision:.0f}% de precisión y la proyección de abajo se calculan igual con los "
            "datos disponibles, pero represéntalo con cuidado: no es que el modelo prediga mal, es "
            "que probablemente esta tienda dejó de operar o dejó de reportar ventas al sistema. "
            "Esto es una pregunta para el negocio, no algo que un mejor modelo pueda arreglar -- "
            "vale la pena confirmar si este punto de venta sigue activo.",
        ])

    if semanas < SEMANAS_HISTORIA_UMBRAL:
        return html.Div(className="note-box important", children=[
            html.Strong("Por qué la precisión de esta tienda es la que es: "),
            f"{nombre_tienda} tiene solo {semanas:.0f} semanas de historia registrada -- es una "
            "tienda relativamente nueva dentro de la muestra de datos. El patrón semanal (qué días "
            "vende más o menos) todavía no se termina de formar con tan poco tiempo. Esto se "
            "resuelve solo con el paso del tiempo, acumulando más semanas de venta -- no es algo "
            "que un modelo distinto pueda arreglar hoy.",
        ])

    return html.Div(className="note-box important", children=[
        html.Strong("Por qué la precisión de esta tienda es la que es: "),
        f"{nombre_tienda} tiene historia suficiente ({semanas:.0f} semanas) y actividad reciente "
        f"normal, pero maneja en promedio solo {ordenes_dia:.1f} órdenes por día. Con tan pocas "
        "transacciones diarias, una sola venta grande o pequeña mueve el total del día de forma "
        "importante -- es ruido estadístico real de una tienda de este tamaño, no una falla del "
        "modelo ni falta de datos. Por eso la precisión de esta tienda es naturalmente más baja que "
        "la de toda la empresa junta (que suma ~63 órdenes/día entre las 9 tiendas, promediando ese "
        "mismo ruido).",
    ])


@callback(Output("prediccion-contenido", "children"), *FILTROS)
def actualizar(sucursales, fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)
    resultado = pronostico_corto_plazo(sucursales, fecha_ini, fecha_fin, umbral_ef)

    if not resultado.get("suficiente"):
        return empty_state("No hay suficientes días de datos en este rango para calcular una proyección confiable.")

    es_agregado = resultado["es_agregado"]
    mape = resultado["mape_pct"]
    precision_aprox = 100 - mape if mape is not None else None

    kpis = [
        kpi_card(
            "Precisión del modelo" if es_agregado else "Precisión del modelo para esta tienda",
            f"{precision_aprox:.0f}%" if precision_aprox is not None else "—",
            "Promedio de varias pruebas (no solo el último mes) contra lo que realmente pasó, sin "
            "haberlo visto antes -- un solo mes de prueba resultó ser poco estable por sí solo.",
            ayuda="Entrenado y probado únicamente con los datos de esta selección -- no es un "
                  "número inflado ni prestado de otra parte. Se promedian varias ventanas de "
                  "prueba distintas para que el número no dependa de qué mes específico te tocó "
                  "mirar.",
        ),
    ]

    if not es_agregado:
        kpis.append(kpi_card(
            "Órdenes por día, en promedio",
            f"{resultado['ordenes_promedio_dia']:.1f}",
            "A menor volumen diario, más ruidoso es el total del día.",
        ))
        kpis.append(kpi_card(
            "Historia disponible",
            f"{resultado['semanas_historia']:.0f} semanas",
            "Menos de ~15 semanas: el patrón semanal todavía se está formando.",
        ))
        kpis.append(kpi_card(
            "Días desde la última venta",
            f"{resultado['dias_desde_ultima_venta']}",
            "Más de 14 días es señal de posible inactividad, no un problema de modelo.",
        ))
        if resultado.get("mape_agregado_pct") is not None:
            precision_agg = 100 - resultado["mape_agregado_pct"]
            kpis.append(kpi_card(
                "Referencia: precisión a nivel de toda la empresa",
                f"{precision_agg:.0f}%",
                "No reemplaza el número de esta tienda, es contexto.",
            ))

    nombre_tienda = ", ".join(s.title() for s in sucursales) if sucursales else ""

    cajas_explicacion = [
        html.Div(className="note-box important", children=[
            html.Strong("Cómo leer esta página: "),
            "El sistema aprende el patrón de ventas de cada día de la semana (por ejemplo, los "
            "sábados suelen vender más que los martes) y usa ese patrón para proyectar los próximos "
            "14 días. No es magia ni inteligencia artificial compleja — es una proyección "
            "estadística simple, elegida a propósito porque es la más confiable con la cantidad de "
            "datos disponible hoy. A medida que se acumule más historial (idealmente más de un "
            "año), el sistema podrá anticipar también temporadas altas como Navidad o vacaciones, "
            "algo que todavía no puede hacer.",
        ]),
    ]
    if not es_agregado:
        cajas_explicacion.append(_explicacion_tienda(resultado, nombre_tienda))

    return [
        *cajas_explicacion,
        html.Div(className="kpi-grid", children=kpis),
        html.Div(className="chart-card", children=[
            chart_header(
                "¿Qué tan bien predice el modelo? (prueba con datos reales)",
                "Se le ocultaron al modelo las últimas semanas antes de calcular esto, para probar "
                "cómo se comporta con información que nunca vio — igual que se comportaría en el "
                "futuro real, no un resultado inflado por 'hacer trampa'.",
            ),
            dcc.Graph(figure=_fig_backtest(resultado["historico"], resultado["backtest"]),
                      config={"displayModeBar": False}),
        ]),
        html.Div(className="chart-card", children=[
            chart_header(
                "Proyección de ventas — próximos 14 días",
                "Estimación de ventas diarias para las próximas dos semanas, basada en el patrón "
                "semanal histórico de esta selección. Ancladas al final del rango de fechas "
                "filtrado, no a la última venta propia de la tienda.",
            ),
            dcc.Graph(figure=_fig_forecast(resultado["forecast"]), config={"displayModeBar": False}),
        ]),
    ]
