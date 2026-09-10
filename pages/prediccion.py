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


def _fig_backtest(historico, backtest, es_agregado: bool) -> go.Figure:
    nombre_pred = "Lo que el modelo predijo" if es_agregado else "Proyección distribuida a esta tienda"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=historico["dia"], y=historico["ventas"], mode="lines",
                             line=dict(color="#EDE1DD", width=1.5), name="Histórico", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=backtest["dia"], y=backtest["ventas"], mode="lines+markers",
                             line=dict(color="#201A1A", width=2), name="Lo que realmente pasó",
                             hovertemplate="%{x}<br>Real: $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=backtest["dia"], y=backtest["prediccion"], mode="lines+markers",
                             line=dict(color="#9C4F5C", width=2, dash="dash"), name=nombre_pred,
                             hovertemplate="%{x}<br>" + nombre_pred + ": $%{y:,.0f}<extra></extra>"))
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
            "Precisión del modelo (toda la empresa)",
            f"{precision_aprox:.0f}%" if precision_aprox is not None else "—",
            "No cambia al filtrar una sucursal -- ver por qué abajo.",
        ),
    ]

    if not es_agregado:
        kpis.append(kpi_card(
            "Participación histórica de esta tienda",
            f"{resultado['participacion_pct']:.1f}%",
            "Del total de ventas de la empresa en el periodo seleccionado",
        ))
        if resultado["mape_distribucion_pct"] is not None:
            kpis.append(kpi_card(
                "Ajuste de la distribución para esta tienda",
                f"{100 - resultado['mape_distribucion_pct']:.0f}%",
                "Qué tan bien la participación histórica explica el patrón real de esta tienda -- "
                "no es la precisión del modelo, es una métrica distinta.",
            ))

    explicacion = (
        "El sistema aprende el patrón de ventas de cada día de la semana (por ejemplo, los sábados "
        "suelen vender más que los martes) y usa ese patrón para proyectar los próximos 14 días. No "
        "es magia ni inteligencia artificial compleja — es una proyección estadística simple, "
        "elegida a propósito porque es la más confiable con la cantidad de datos disponible hoy."
    )
    if not es_agregado:
        explicacion += (
            " El modelo SIEMPRE se entrena con el total de la empresa, nunca con una sola tienda por "
            "separado: probamos hacerlo por tienda y el resultado fue mucho menos confiable (una "
            "tienda individual vende con más variabilidad relativa que el conjunto -- es matemática, "
            "no un defecto del modelo -- y varias tiendas tienen historia real más corta de lo que "
            "parece, algunas abrieron a mitad de este periodo). Por eso, al filtrar una sucursal, lo "
            "que ves es la proyección total de la empresa distribuida según cuánto representa "
            "históricamente esa tienda -- no un modelo aparte entrenado solo con sus datos."
        )
    explicacion += (
        " A medida que se acumule más historial (idealmente más de un año), el sistema podrá "
        "anticipar también temporadas altas como Navidad o vacaciones, algo que todavía no puede "
        "hacer."
    )

    titulo_backtest = ("¿Qué tan bien predice el modelo? (prueba con datos reales)" if es_agregado
                       else "Ventas reales de esta tienda vs. proyección distribuida")
    caption_backtest = (
        "Se le ocultaron al modelo las últimas semanas antes de calcular esto, para probar cómo se "
        "comporta con información que nunca vio -- igual que se comportaría en el futuro real, no un "
        "resultado inflado por 'hacer trampa'." if es_agregado else
        "La línea negra es lo que esta tienda vendió de verdad. La línea rosa punteada es la "
        "proyección total de la empresa, distribuida según la participación histórica de esta tienda "
        "-- no un modelo entrenado solo con los datos de esta tienda."
    )

    return [
        html.Div(className="note-box important", children=[
            html.Strong("Cómo leer esta página: "), explicacion,
        ]),
        html.Div(className="kpi-grid", children=kpis),
        html.Div(className="chart-card", children=[
            chart_header(titulo_backtest, caption_backtest),
            dcc.Graph(figure=_fig_backtest(resultado["historico"], resultado["backtest"], es_agregado),
                      config={"displayModeBar": False}),
        ]),
        html.Div(className="chart-card", children=[
            chart_header(
                "Proyección de ventas — próximos 14 días",
                "Estimación de ventas diarias para las próximas dos semanas, basada en el patrón "
                "semanal histórico."
                + ("" if es_agregado else " Distribuida a esta tienda según su participación histórica."),
            ),
            dcc.Graph(figure=_fig_forecast(resultado["forecast"]), config={"displayModeBar": False}),
        ]),
    ]
