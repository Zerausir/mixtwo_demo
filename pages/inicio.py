from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dcc, html

from components.ui import formato_entero, formato_moneda, kpi_card, page_header
from services.queries import (
    distribucion_ticket,
    resumen_general,
    ventas_diarias_por_mes,
    ventas_por_dia_semana,
)

dash.register_page(__name__, path="/", name="Resumen")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)


def _fig_tendencia(df) -> go.Figure:
    colores = ["#94a3b8" if parcial else "#1464f4" for parcial in df["parcial"]]
    fig = go.Figure(
        go.Bar(
            x=df["mes"],
            y=df["promedio_diario"],
            marker_color=colores,
            text=[f"{'(parcial)' if p else ''}" for p in df["parcial"]],
            textposition="outside",
            hovertemplate="%{x}<br>Promedio diario: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=20, t=20, b=40), height=340,
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="Venta promedio diaria (USD)", font=FONT,
    )
    return fig


def _fig_boxplot_ticket(df) -> go.Figure:
    fig = go.Figure(
        go.Box(
            x=df["valor_orden"],
            marker_color="#1464f4",
            boxmean=True,
            name="",
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=40), height=200,
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis_title="Valor de la orden (USD)", font=FONT,
        showlegend=False, yaxis=dict(showticklabels=False),
    )
    return fig


def _fig_dia_semana(df) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=df["dia_semana"], y=df["venta_promedio"],
            marker_color="#0b1f33",
            hovertemplate="%{x}<br>Venta promedio: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=20, t=20, b=40), height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="Venta promedio (USD)", font=FONT,
    )
    return fig


def layout():
    resumen = resumen_general(incluir_matriz=False)
    tendencia = ventas_diarias_por_mes(incluir_matriz=False)
    ticket = distribucion_ticket(incluir_matriz=False)
    dia_semana = ventas_por_dia_semana(incluir_matriz=False)

    return html.Div(
        className="page-content",
        children=[
            page_header(
                "Resumen ejecutivo",
                f"Datos del {resumen['fecha_min']} al {resumen['fecha_max']} · "
                "excluye MATRIZ (centro administrativo, no punto de venta al público)"
                if resumen["fecha_min"] else "Sin datos cargados",
            ),
            html.Div(
                className="kpi-grid",
                children=[
                    kpi_card("Ventas totales", formato_moneda(resumen["ventas_totales"]), "Periodo completo"),
                    kpi_card("Órdenes reales", formato_entero(resumen["ordenes"]), "Facturas, no líneas de producto"),
                    kpi_card("Ticket promedio", formato_moneda(resumen["ticket_promedio"]),
                             f"Mediana: {formato_moneda(resumen['ticket_mediana'])}"),
                    kpi_card("Unidades vendidas", formato_entero(resumen["unidades_totales"])),
                ],
            ),
            html.Div(
                className="chart-card",
                children=[
                    html.H3("Venta promedio diaria por mes", className="chart-title"),
                    html.P(
                        "Se usa promedio diario, no suma del mes, para que un mes incompleto no "
                        "se vea como una caída. Barras grises = mes con datos parciales.",
                        className="chart-note",
                    ),
                    dcc.Graph(figure=_fig_tendencia(tendencia), config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                className="grid-2",
                children=[
                    html.Div(
                        className="chart-card",
                        children=[
                            html.H3("Distribución del valor de orden", className="chart-title"),
                            html.P(
                                "La distribución está sesgada a la derecha — el promedio se ve "
                                "arrastrado por órdenes grandes; la mediana representa mejor la orden típica.",
                                className="chart-note",
                            ),
                            dcc.Graph(figure=_fig_boxplot_ticket(ticket), config={"displayModeBar": False}),
                        ],
                    ),
                    html.Div(
                        className="chart-card",
                        children=[
                            html.H3("Venta promedio por día de la semana", className="chart-title"),
                            dcc.Graph(figure=_fig_dia_semana(dia_semana), config={"displayModeBar": False}),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="note-box",
                children=[
                    html.Strong("Nota sobre el alcance de este demo: "),
                    "los datos cubren aproximadamente 6 meses. Esto es suficiente para confirmar "
                    "un patrón semanal confiable (ver gráfico de día de la semana), pero no para "
                    "capturar estacionalidad anual (temporadas altas, fechas comerciales). El "
                    "componente de predicción de este demo (página Predicción) refleja esa "
                    "limitación de forma explícita, con su error medido.",
                ],
            ),
        ],
    )
