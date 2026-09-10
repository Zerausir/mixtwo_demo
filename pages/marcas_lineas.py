from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from components.ui import con_carga, chart_header, empty_state, page_header, umbral_efectivo
from services.queries import hay_datos, ventas_por_linea, ventas_por_marca

dash.register_page(__name__, path="/marcas-lineas", name="Marcas y líneas")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-sucursal", "value"), Input("filtro-marca", "value"), Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Marcas y líneas de producto",
            "La marca no existe como campo explícito en el sistema de origen — se identifica "
            "automáticamente a partir del código del producto (cobertura: ~75% del valor de ventas).",
        ),
        con_carga("carga-marcas-contenido", html.Div(id="marcas-contenido")),
    ])


def _fig_linea(df) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df["ventas"], y=df["linea"], orientation="h", marker_color="#9C4F5C",
        text=df["porcentaje"].apply(lambda p: f"{p}%"), textposition="outside",
        hovertemplate="%{y}<br>Ventas: $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(margin=dict(l=190, r=60, t=20, b=40), height=360,
                      plot_bgcolor="white", paper_bgcolor="white",
                      xaxis_title="Ventas (USD)", yaxis=dict(autorange="reversed"), font=FONT)
    return fig


def _fig_marca(df) -> go.Figure:
    total = df["ventas"].sum()
    pct = (df["ventas"] / total * 100) if total else df["ventas"] * 0
    fig = go.Figure(go.Bar(
        x=df["marca"], y=df["ventas"], marker_color="#201A1A",
        customdata=pct,
        text=[f"{p:.1f}%" for p in pct], textposition="outside",
        hovertemplate="%{x}<br>Ventas: $%{y:,.0f} (%{customdata:.1f}% de las marcas mostradas)<extra></extra>",
    ))
    fig.update_layout(margin=dict(l=50, r=20, t=30, b=80), height=360,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis_title="Ventas (USD)", font=FONT)
    return fig


@callback(Output("marcas-contenido", "children"), *FILTROS)
def actualizar(sucursales, marcas, lineas, fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)

    if not hay_datos(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef):
        return empty_state()

    df_linea = ventas_por_linea(sucursales, marcas, fecha_ini, fecha_fin, umbral_ef)
    df_marca = ventas_por_marca(sucursales, lineas, fecha_ini, fecha_fin, umbral_ef)

    return [
        html.Div(className="chart-card", children=[
            chart_header(
                "Peso por línea de producto",
                "Porcentaje del total de ventas que corresponde a cada línea (íntimo, playa, "
                "homewear, etc.), dentro de los filtros seleccionados.",
            ),
            dcc.Graph(figure=_fig_linea(df_linea), config={"displayModeBar": False}),
        ]),
        html.Div(className="chart-card", children=[
            chart_header(
                "Ventas por marca",
                "Solo se muestran líneas de producto donde la marca pudo identificarse "
                "automáticamente por el código.",
            ),
            dcc.Graph(figure=_fig_marca(df_marca), config={"displayModeBar": False}),
        ]),
        html.Div(className="table-card", children=[
            html.H3("Detalle por línea", className="chart-title"),
            dash_table.DataTable(
                data=df_linea.round(2).to_dict("records"),
                columns=[{"name": c, "id": c} for c in df_linea.columns],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                page_size=10,
            ),
        ]),
    ]
