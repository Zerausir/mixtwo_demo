from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from components.ui import chart_header, empty_state, page_header, umbral_efectivo
from services.queries import hay_datos, mix_linea_por_sucursal, ventas_por_sucursal

dash.register_page(__name__, path="/sucursales", name="Sucursales")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-marca", "value"), Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
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
def actualizar(marcas, lineas, fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)

    if not hay_datos(None, marcas, lineas, fecha_ini, fecha_fin, umbral_ef):
        return empty_state()

    mix = mix_linea_por_sucursal(marcas, fecha_ini, fecha_fin, umbral_ef)
    resumen = ventas_por_sucursal(marcas, lineas, fecha_ini, fecha_fin, umbral_ef)
    total_ventas = resumen["ventas"].sum()
    resumen["% del total"] = (resumen["ventas"] / total_ventas * 100).round(1) if total_ventas else 0

    return [
        html.Div(className="chart-card", children=[
            chart_header(
                "Composición de ventas por línea, dentro de cada sucursal",
                "Cada fila suma 100%. Muestra qué porcentaje de las ventas de esa tienda "
                "corresponde a cada línea de producto — no el volumen total de la tienda. "
                "El filtro de 'Línea de producto' de arriba no afecta este gráfico en particular "
                "(sí afecta la tabla de abajo): filtrar por línea aquí sería circular, porque la "
                "línea es justamente el eje que se está desglosando.",
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
                sort_action="native",
                page_size=10,
            ),
        ]),
    ]
