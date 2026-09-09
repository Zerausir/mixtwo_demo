from __future__ import annotations

import dash
from dash import Input, Output, callback, dash_table, html

from components.ui import empty_state, formato_entero, formato_moneda, kpi_card, page_header
from services.queries import ranking_clientes, resumen_mayoristas

dash.register_page(__name__, path="/mayoristas", name="Cuentas mayoristas")

FILTROS = [
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-umbral", "value"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Detección de cuentas mayoristas",
            "Ranking de clientes identificados por número de órdenes distintas en el periodo "
            "seleccionado — independiente de sucursal/marca/línea, porque el estatus de un cliente "
            "no debería depender de qué producto estás mirando. Ajusta el umbral en el control "
            "'Cuentas mayoristas' de la barra superior para ver el efecto de inmediato: ese mismo "
            "umbral es el que se aplica (si está activado) en el resto del panel.",
        ),
        html.Div(id="mayoristas-contenido"),
    ])


@callback(Output("mayoristas-contenido", "children"), *FILTROS)
def actualizar(fecha_ini, fecha_fin, umbral):
    umbral = int(umbral) if umbral else 15
    ranking = ranking_clientes(fecha_ini, fecha_fin, limite=40)

    if ranking.empty:
        return empty_state("No hay clientes identificados en este rango de fechas.")

    resumen = resumen_mayoristas(fecha_ini, fecha_fin, umbral)
    ranking["mayorista"] = ranking["ordenes"] > umbral

    columnas = [
        {"name": "Identificación", "id": "identificacion"},
        {"name": "Cliente", "id": "cliente"},
        {"name": "Formato", "id": "formato"},
        {"name": "Órdenes", "id": "ordenes"},
        {"name": "Gasto total (USD)", "id": "gasto_total"},
        {"name": "Ticket promedio (USD)", "id": "ticket_promedio"},
    ]

    return [
        html.Div(className="kpi-grid", children=[
            kpi_card(
                "Cuentas sobre el umbral",
                formato_entero(resumen["n_cuentas"]),
                f"Más de {umbral} órdenes distintas en el periodo",
            ),
            kpi_card(
                "Ventas de esas cuentas",
                formato_moneda(resumen["ventas_mayoristas"]),
                f"{resumen['porcentaje']:.1f}% de las ventas totales del periodo",
            ),
            kpi_card(
                "Ventas totales del periodo",
                formato_moneda(resumen["ventas_totales"]),
                "Referencia, sin excluir nada",
            ),
        ]),
        html.Div(
            className="note-box important",
            children=[
                html.Strong("Cómo leer esta tabla: "),
                "las filas resaltadas superan el umbral actual y se consideran mayoristas mientras "
                "el control de arriba esté activado. La columna 'Formato' es una señal de apoyo, no "
                "la regla principal: un RUC de empresa con pocas órdenes probablemente es una "
                "persona que factura a su propio negocio, no necesariamente un mayorista — el "
                "número de órdenes manda.",
            ],
        ),
        html.Div(className="table-card", children=[
            html.H3(f"Top {len(ranking)} clientes por número de órdenes", className="chart-title"),
            dash_table.DataTable(
                data=ranking.round(2).to_dict("records"),
                columns=columnas,
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px", "fontSize": "13px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{mayorista} = true"},
                        "backgroundColor": "#F5DEE1",
                        "color": "#9C4F5C",
                        "fontWeight": "600",
                    }
                ],
                page_size=15,
                sort_action="native",
            ),
        ]),
    ]
