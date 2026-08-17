from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from components.ui import chart_title_with_help, empty_state, page_header
from services.queries import hay_datos, mix_linea_por_sucursal, ventas_por_sucursal

dash.register_page(__name__, path="/sucursales", name="Sucursales")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-marca", "value"), Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Comparación entre sucursales",
            "El mix de producto varía mucho entre tiendas — un análisis global esconde estas "
            "diferencias. El filtro de sucursal de arriba no aplica en esta página, ya que su "
            "propósito es comparar todas las tiendas entre sí.",
        ),
        html.Div(id="sucursales-contenido"),
    ])


def _fig_heatmap(tabla) -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=tabla.values, x=tabla.columns, y=tabla.index,
        colorscale=[[0, "#FBF3F1"], [0.5, "#E8B4BB"], [1, "#9C4F5C"]],
        text=tabla.values, texttemplate="%{text:.0f}%",
        hovertemplate="%{y}<br>%{x}: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="% de ventas<br>de la tienda"),
    ))
    fig.update_layout(margin=dict(l=180, r=20, t=20, b=80), height=420, paper_bgcolor="white", font=FONT)
    return fig


@callback(Output("sucursales-contenido", "children"), *FILTROS)
def actualizar(marcas, lineas, fecha_ini, fecha_fin):
    if not hay_datos(None, marcas, lineas, fecha_ini, fecha_fin):
        return empty_state()

    mix = mix_linea_por_sucursal(marcas, fecha_ini, fecha_fin)
    resumen = ventas_por_sucursal(marcas, lineas, fecha_ini, fecha_fin)

    return [
        html.Div(className="chart-card", children=[
            chart_title_with_help(
                "Composición de ventas por línea, dentro de cada sucursal",
                "Cada fila suma 100%. Muestra qué porcentaje de las ventas de esa tienda "
                "corresponde a cada línea de producto — no el volumen total de la tienda.",
            ),
            dcc.Graph(figure=_fig_heatmap(mix), config={"displayModeBar": False}) if not mix.empty else empty_state(),
        ]),
        html.Div(className="table-card", children=[
            html.H3("Resumen por sucursal", className="chart-title"),
            dash_table.DataTable(
                data=resumen.round(2).to_dict("records"),
                columns=[{"name": c, "id": c} for c in resumen.columns],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                page_size=10,
            ),
        ]),
    ]
