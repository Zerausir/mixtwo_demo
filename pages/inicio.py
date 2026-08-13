from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dcc, html

from components.ui import formato_entero, formato_moneda, kpi_card, page_header
from services.queries import resumen_general, ventas_por_semana

dash.register_page(__name__, path="/", name="Resumen")


def layout():
    resumen = resumen_general()
    semanal = ventas_por_semana()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=semanal["semana_inicio"],
            y=semanal["ventas"],
            mode="lines+markers",
            line=dict(color="#1464f4", width=2),
            marker=dict(size=5),
            fill="tozeroy",
            fillcolor="rgba(20, 100, 244, 0.08)",
            hovertemplate="Semana del %{x}<br>Ventas: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=20, t=20, b=40),
        height=360,
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_title=None,
        yaxis_title="Ventas (USD)",
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=12),
    )

    return html.Div(
        className="page-content",
        children=[
            page_header(
                "Resumen ejecutivo",
                f"Datos del {resumen['fecha_min']} al {resumen['fecha_max']}"
                if resumen["fecha_min"] else "Sin datos cargados",
            ),
            html.Div(
                className="kpi-grid",
                children=[
                    kpi_card("Ventas totales", formato_moneda(resumen["ventas_totales"]), "Periodo completo"),
                    kpi_card("Unidades vendidas", formato_entero(resumen["unidades_totales"])),
                    kpi_card("Transacciones", formato_entero(resumen["transacciones"])),
                    kpi_card("Ticket promedio", formato_moneda(resumen["ticket_promedio"])),
                ],
            ),
            html.Div(
                className="chart-card",
                children=[
                    html.H3("Ventas por semana", className="chart-title"),
                    dcc.Graph(figure=fig, config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                className="note-box",
                children=[
                    html.Strong("Nota sobre el alcance de este demo: "),
                    "los datos cubren un periodo de aproximadamente 6 meses. Para un modelo de "
                    "predicción de demanda que capture estacionalidad (temporadas altas, fechas "
                    "comerciales) se requiere un histórico más largo — este demo muestra el análisis "
                    "descriptivo y la limpieza de datos que son la base de la Fase 1, no un modelo "
                    "predictivo entrenado.",
                ],
            ),
        ],
    )
