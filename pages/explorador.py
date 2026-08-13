from __future__ import annotations

import dash
from dash import Input, Output, callback, dash_table, dcc, html

from components.ui import page_header
from services.queries import explorar_ventas, opciones_filtro, ventas_por_sucursal

dash.register_page(__name__, path="/explorador", name="Explorador")


def layout():
    opciones = opciones_filtro()
    df_sucursal = ventas_por_sucursal()

    return html.Div(
        className="page-content",
        children=[
            page_header(
                "Explorador de ventas",
                "Filtra por sucursal, marca o línea de producto para revisar el detalle de transacciones.",
            ),
            html.Div(
                className="filters-row",
                children=[
                    dcc.Dropdown(
                        id="filtro-sucursal",
                        options=[{"label": s, "value": s} for s in opciones["sucursales"]],
                        placeholder="Sucursal",
                        className="filter-dropdown",
                    ),
                    dcc.Dropdown(
                        id="filtro-linea",
                        options=[{"label": l, "value": l} for l in opciones["lineas"]],
                        placeholder="Línea de producto",
                        className="filter-dropdown",
                    ),
                    dcc.Dropdown(
                        id="filtro-marca",
                        options=[{"label": m, "value": m} for m in opciones["marcas"]],
                        placeholder="Marca",
                        className="filter-dropdown",
                    ),
                ],
            ),
            html.Div(id="tabla-explorador"),
            html.Div(
                className="table-card",
                children=[
                    html.H3("Resumen por sucursal (sin filtrar)", className="chart-title"),
                    dash_table.DataTable(
                        data=df_sucursal.round(2).to_dict("records"),
                        columns=[{"name": c, "id": c} for c in df_sucursal.columns],
                        style_as_list_view=True,
                        style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px"},
                        style_header={"fontWeight": "600", "backgroundColor": "#f5f7fa"},
                        page_size=10,
                    ),
                ],
            ),
        ],
    )


@callback(
    Output("tabla-explorador", "children"),
    Input("filtro-sucursal", "value"),
    Input("filtro-linea", "value"),
    Input("filtro-marca", "value"),
)
def actualizar_tabla(sucursal, linea, marca):
    df = explorar_ventas(sucursal, linea, marca)
    return html.Div(
        className="table-card",
        children=[
            html.H3(f"Transacciones ({len(df)} de máx. 500 mostradas)", className="chart-title"),
            dash_table.DataTable(
                data=df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in df.columns],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "6px", "fontSize": "13px"},
                style_header={"fontWeight": "600", "backgroundColor": "#f5f7fa"},
                page_size=15,
                sort_action="native",
                filter_action="native",
            ),
        ],
    )
