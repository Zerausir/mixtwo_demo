from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dash_table, dcc, html

from components.ui import page_header
from services.queries import ventas_por_linea, ventas_por_marca

dash.register_page(__name__, path="/marcas-lineas", name="Marcas y líneas")


def layout():
    df_linea = ventas_por_linea()
    df_marca = ventas_por_marca()

    fig_linea = go.Figure(
        go.Bar(
            x=df_linea["ventas"],
            y=df_linea["linea"],
            orientation="h",
            marker_color="#1464f4",
            text=df_linea["porcentaje"].apply(lambda p: f"{p}%"),
            textposition="outside",
            hovertemplate="%{y}<br>Ventas: $%{x:,.0f}<extra></extra>",
        )
    )
    fig_linea.update_layout(
        margin=dict(l=180, r=60, t=20, b=40),
        height=380,
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_title="Ventas (USD)",
        yaxis=dict(autorange="reversed"),
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=12),
    )

    fig_marca = go.Figure(
        go.Bar(
            x=df_marca["marca"],
            y=df_marca["ventas"],
            marker_color="#0b1f33",
            hovertemplate="%{x}<br>Ventas: $%{y:,.0f}<extra></extra>",
        )
    )
    fig_marca.update_layout(
        margin=dict(l=50, r=20, t=20, b=80),
        height=380,
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis_title="Ventas (USD)",
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=12),
    )

    return html.Div(
        className="page-content",
        children=[
            page_header(
                "Marcas y líneas de producto",
                "La marca no existe como campo explícito en el sistema de origen — se deriva "
                "por reglas desde el código de producto. Cobertura actual: ~75% del valor de ventas.",
            ),
            html.Div(
                className="chart-card",
                children=[
                    html.H3("Peso por línea de producto", className="chart-title"),
                    dcc.Graph(figure=fig_linea, config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                className="chart-card",
                children=[
                    html.H3("Ventas por marca (identificadas)", className="chart-title"),
                    dcc.Graph(figure=fig_marca, config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                className="table-card",
                children=[
                    html.H3("Detalle por línea", className="chart-title"),
                    dash_table.DataTable(
                        data=df_linea.round(2).to_dict("records"),
                        columns=[{"name": c, "id": c} for c in df_linea.columns],
                        style_as_list_view=True,
                        style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px"},
                        style_header={"fontWeight": "600", "backgroundColor": "#f5f7fa"},
                        page_size=10,
                    ),
                ],
            ),
        ],
    )
