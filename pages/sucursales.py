from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dcc, html

from components.ui import page_header
from services.queries import mix_linea_por_sucursal, ventas_por_sucursal

dash.register_page(__name__, path="/sucursales", name="Sucursales")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)


def _fig_heatmap(tabla) -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=tabla.values,
            x=tabla.columns,
            y=tabla.index,
            colorscale="Blues",
            text=tabla.values,
            texttemplate="%{text:.0f}%",
            hovertemplate="%{y}<br>%{x}: %{z:.1f}%<extra></extra>",
            colorbar=dict(title="% de ventas<br>de la tienda"),
        )
    )
    fig.update_layout(
        margin=dict(l=180, r=20, t=20, b=80), height=420,
        paper_bgcolor="white", font=FONT,
    )
    return fig


def layout():
    mix = mix_linea_por_sucursal(incluir_matriz=True)
    resumen = ventas_por_sucursal(incluir_matriz=False)

    return html.Div(
        className="page-content",
        children=[
            page_header(
                "Comparación entre sucursales",
                "El mix de producto varía mucho entre tiendas — un análisis global esconde estas "
                "diferencias. MATRIZ se incluye en el mapa de calor para mostrar por qué se excluye "
                "del resto de KPIs: no es un punto de venta al público comparable.",
            ),
            html.Div(
                className="chart-card",
                children=[
                    html.H3("Composición de ventas por línea, dentro de cada sucursal", className="chart-title"),
                    dcc.Graph(figure=_fig_heatmap(mix), config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                className="note-box",
                children=[
                    html.Strong("Lectura del mapa: "),
                    "MATRIZ concentra 55% en línea Hombre y 0% en Playa — consistente con un centro "
                    "administrativo o mayorista, no una tienda retail. PB Scala y Punto Blanco son "
                    "corners de la marca masculina Punto Blanco, sin línea Playa. Scala Shopping tiene "
                    "la mayor proporción de Playa (37.6%); Centro Comercial Iñaquito la mayor "
                    "concentración en Íntimo (78.6%). Cualquier estrategia de inventario o "
                    "predicción de demanda debe considerar estas diferencias por tienda, no un "
                    "promedio general.",
                ],
            ),
            html.Div(
                className="table-card",
                children=[
                    html.H3("Resumen por sucursal (excluye MATRIZ)", className="chart-title"),
                    dash_table_from_df(resumen),
                ],
            ),
        ],
    )


def dash_table_from_df(df):
    from dash import dash_table
    return dash_table.DataTable(
        data=df.round(2).to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        style_as_list_view=True,
        style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px"},
        style_header={"fontWeight": "600", "backgroundColor": "#f5f7fa"},
        page_size=10,
    )
