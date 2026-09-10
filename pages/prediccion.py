from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from components.ui import chart_header, empty_state, kpi_card, page_header, umbral_efectivo
from services.queries import pronostico_corto_plazo

dash.register_page(__name__, path="/prediccion", name="Predicción")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-sucursal", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Predicción de ventas — corto plazo",
            "Esta página solo se filtra por sucursal y fecha (no por marca ni línea de producto) "
            "— es la combinación que se validó como confiable antes de mostrarla.",
        ),
        html.Div(id="prediccion-contenido"),
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
            "Entre menos órdenes maneja una tienda al día, más pesa cada venta individual sobre el "
            "total -- eso explica por qué esta tienda predice distinto al agregado, no un defecto "
            "del modelo.",
        ))
        kpis.append(kpi_card(
            "Historia disponible",
            f"{resultado['semanas_historia']:.0f} semanas",
            "Menos de ~26 semanas (medio año) significa que el patrón semanal de esta tienda "
            "todavía se está formando.",
        ))
        if resultado.get("mape_agregado_pct") is not None:
            precision_agg = 100 - resultado["mape_agregado_pct"]
            kpis.append(kpi_card(
                "Referencia: precisión a nivel de toda la empresa",
                f"{precision_agg:.0f}%",
                "Más alta porque suma ~63 órdenes/día entre las 9 tiendas -- el ruido de cada venta "
                "individual se cancela entre más transacciones. No reemplaza el número de esta "
                "tienda, es contexto.",
            ))

    explicacion = (
        "El sistema aprende el patrón de ventas de cada día de la semana (por ejemplo, los sábados "
        "suelen vender más que los martes) y usa ese patrón para proyectar los próximos 14 días. No "
        "es magia ni inteligencia artificial compleja — es una proyección estadística simple, "
        "elegida a propósito porque es la más confiable con la cantidad de datos disponible hoy."
    )
    if not es_agregado:
        explicacion += (
            " Este modelo se entrena y valida únicamente con los datos de la tienda filtrada -- el "
            "número de precisión que ves arriba es específico de esta tienda, no un promedio de la "
            "empresa. Es normal que sea más bajo que el de toda la empresa junta: con pocas órdenes "
            "al día, cada venta grande o pequeña mueve el total más de lo que movería en un negocio "
            "que suma muchas tiendas."
        )
    explicacion += (
        " A medida que se acumule más historial (idealmente más de un año), el sistema podrá "
        "anticipar también temporadas altas como Navidad o vacaciones, algo que todavía no puede "
        "hacer."
    )

    return [
        html.Div(className="note-box important", children=[
            html.Strong("Cómo leer esta página: "), explicacion,
        ]),
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
                "semanal histórico de esta selección.",
            ),
            dcc.Graph(figure=_fig_forecast(resultado["forecast"]), config={"displayModeBar": False}),
        ]),
    ]
