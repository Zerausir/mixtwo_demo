from __future__ import annotations

import dash
from dash import Input, Output, callback, dash_table, html

from components.ui import con_carga, empty_state, page_header, umbral_efectivo
from services.queries import explorar_ventas, hay_datos, ventas_por_sucursal

dash.register_page(__name__, path="/explorador", name="Explorador")

FILTROS = [
    Input("filtro-sucursal", "value"), Input("filtro-marca", "value"), Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Explorador de ventas",
            "Detalle de transacciones para los filtros seleccionados arriba. Útil para revisar "
            "casos puntuales, no para tendencias generales (usa Resumen para eso).",
        ),
        con_carga("carga-explorador-contenido", html.Div(id="explorador-contenido")),
    ])


@callback(Output("explorador-contenido", "children"), *FILTROS)
def actualizar(sucursales, marcas, lineas, fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)

    if not hay_datos(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef):
        return empty_state()

    df = explorar_ventas(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef)
    df_sucursal = ventas_por_sucursal(marcas, lineas, fecha_ini, fecha_fin, umbral_ef)
    total_ventas = df_sucursal["ventas"].sum()
    df_sucursal["% del total"] = (df_sucursal["ventas"] / total_ventas * 100).round(1) if total_ventas else 0

    columnas_resumen = {
        "sucursal": "Sucursal", "ventas": "Ventas (USD)", "unidades": "Unidades",
        "ordenes": "Órdenes", "% del total": "% del total",
        "ultima_venta": "Última venta", "dias_desde_ultima_venta": "Días sin vender",
    }
    df_sucursal_mostrar = df_sucursal[list(columnas_resumen.keys())].rename(columns=columnas_resumen)

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
                export_format="xlsx", export_headers="display",
            ),
        ]),
        html.Div(className="table-card", children=[
            html.H3("Resumen por sucursal", className="chart-title"),
            dash_table.DataTable(
                data=df_sucursal_mostrar.round(2).to_dict("records"),
                columns=[{"name": c, "id": c} for c in df_sucursal_mostrar.columns],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{Días sin vender} > 14"},
                        "backgroundColor": "#FBEAEA",
                        "color": "#8B2E2E",
                        "fontWeight": "600",
                    }
                ],
                page_size=10,
                export_format="xlsx", export_headers="display",
            ),
        ]),
    ]
