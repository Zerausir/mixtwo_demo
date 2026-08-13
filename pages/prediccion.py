from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dcc, html

from components.ui import page_header
from services.queries import pronostico_corto_plazo

dash.register_page(__name__, path="/prediccion", name="Predicción")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)


def _fig_backtest(historico, backtest) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=historico["dia"], y=historico["ventas"],
        mode="lines", line=dict(color="#cbd5e1", width=1.5),
        name="Histórico", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=backtest["dia"], y=backtest["ventas"],
        mode="lines+markers", line=dict(color="#0b1f33", width=2),
        name="Real (periodo de prueba)",
        hovertemplate="%{x}<br>Real: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=backtest["dia"], y=backtest["prediccion"],
        mode="lines+markers", line=dict(color="#1464f4", width=2, dash="dash"),
        name="Predicción del modelo",
        hovertemplate="%{x}<br>Predicción: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        margin=dict(l=40, r=20, t=20, b=40), height=380,
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="Ventas (USD)", font=FONT,
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def _fig_forecast(forecast) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=forecast["dia"], y=forecast["prediccion"],
            marker_color="#1464f4",
            hovertemplate="%{x}<br>Predicción: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=20, t=20, b=40), height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="Venta proyectada (USD)", font=FONT,
    )
    return fig


def layout():
    resultado = pronostico_corto_plazo(semanas_backtest=4)
    mape = resultado["mape_pct"]

    return html.Div(
        className="page-content",
        children=[
            page_header(
                "Predicción de corto plazo",
                "Modelo baseline (promedio estacional por día de la semana), no una red neuronal ni "
                "un modelo de boosting — es lo que 6 meses de datos pueden sostener de forma honesta.",
            ),
            html.Div(
                className="note-box important",
                children=[
                    html.Strong("Qué SÍ y qué NO hace este modelo: "),
                    "captura el patrón semanal real (ver Resumen ejecutivo) para proyectar ventas a "
                    "1-2 semanas. NO captura estacionalidad anual — no sabe distinguir un diciembre "
                    "de un febrero porque los datos no incluyen un diciembre todavía. Cuando el "
                    "histórico crezca más allá de un ciclo anual completo, este modelo se reemplaza "
                    "por uno que sí capture esa estacionalidad (ver Fase 1 de la propuesta).",
                ],
            ),
            html.Div(
                className="chart-card",
                children=[
                    html.H3("Validación: predicción vs. realidad (últimas 4 semanas)", className="chart-title"),
                    html.P(
                        f"Error promedio del modelo en el periodo de prueba (MAPE): "
                        f"{f'{mape:.1f}%' if mape is not None else 'no calculable'}. "
                        "Esto se calcula entrenando el modelo solo con datos anteriores al periodo de "
                        "prueba, para simular cómo se hubiera comportado en producción — no se hace "
                        "trampa mostrando el ajuste sobre los mismos datos de entrenamiento.",
                        className="chart-note",
                    ),
                    dcc.Graph(figure=_fig_backtest(resultado["historico"], resultado["backtest"]),
                              config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                className="chart-card",
                children=[
                    html.H3("Proyección — próximos 14 días", className="chart-title"),
                    dcc.Graph(figure=_fig_forecast(resultado["forecast"]), config={"displayModeBar": False}),
                ],
            ),
        ],
    )
