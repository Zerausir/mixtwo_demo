from __future__ import annotations

import dash
from dash import Input, Output, callback, dash_table, html

from components.ui import empty_state, page_header
from services.queries import explorar_ventas, hay_datos, ventas_por_sucursal

dash.register_page(__name__, path="/explorador", name="Explorador")

FILTROS = [
    Input("filtro-sucursal", "value"), Input("filtro-marca", "value"), Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Explorador de ventas",
            "Detalle de transacciones para los filtros seleccionados arriba. Útil para revisar "
            "casos puntuales, no para tendencias generales (usa Resumen para eso).",
        ),
        html.Div(id="explorador-contenido"),
    ])


@callback(Output("explorador-contenido", "children"), *FILTROS)
def actualizar(sucursales, marcas, lineas, fecha_ini, fecha_fin):
    if not hay_datos(sucursales, marcas, lineas, fecha_ini, fecha_fin):
        return empty_state()

    df = explorar_ventas(sucursales, marcas, lineas, fecha_ini, fecha_fin)
    df_sucursal = ventas_por_sucursal(marcas, lineas, fecha_ini, fecha_fin)

    return [
        html.Div(className="table-card", children=[
            html.H3(f"Líneas de producto ({len(df)} de máx. 500 mostradas)", className="chart-title"),
            dash_table.DataTable(
                data=df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in df.columns],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "6px", "fontSize": "13px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                page_size=15, sort_action="native", filter_action="native",
            ),
        ]),
        html.Div(className="table-card", children=[
            html.H3("Resumen por sucursal", className="chart-title"),
            dash_table.DataTable(
                data=df_sucursal.round(2).to_dict("records"),
                columns=[{"name": c, "id": c} for c in df_sucursal.columns],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                page_size=10,
            ),
        ]),
    ]
