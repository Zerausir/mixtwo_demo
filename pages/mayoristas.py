from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from components.ui import con_carga, chart_header, empty_state, formato_entero, formato_moneda, kpi_card, page_header
from services.queries import ranking_clientes, resumen_mayoristas

dash.register_page(__name__, path="/mayoristas", name="Cuentas mayoristas")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
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
        con_carga("carga-mayoristas-contenido", html.Div(id="mayoristas-contenido")),
    ])


def _fig_ranking(ranking, umbral: int, top_n: int = 15) -> go.Figure:
    """
    Barra horizontal de los clientes con más órdenes -- el punto de esta
    página no es solo la tabla, es que el SALTO entre las 2 cuentas
    mayoristas y el resto se vea de un vistazo, igual al patrón de
    'Casos más extremos' del módulo Control de OBTEL. Colorea por encima/
    debajo del umbral para que mover el número en la barra de filtros
    tenga un efecto visual inmediato, no solo en la tabla.
    """
    top = ranking.head(top_n).iloc[::-1]  # invertido para que el #1 quede arriba
    colores = ["#9C4F5C" if o > umbral else "#D8C4C7" for o in top["ordenes"]]
    limite_x = top["ordenes"].max() * 1.15  # espacio extra para que la etiqueta de texto no se corte

    fig = go.Figure(go.Bar(
        x=top["ordenes"], y=top["cliente"], orientation="h", marker_color=colores,
        text=top["ordenes"], textposition="outside",
        hovertemplate="%{y}<br>%{x} órdenes<extra></extra>",
    ))
    fig.add_vline(x=umbral, line_dash="dash", line_color="#8A7C79",
                  annotation_text=f"Umbral: {umbral}", annotation_position="top")
    fig.update_layout(margin=dict(l=170, r=40, t=30, b=40), height=420,
                      plot_bgcolor="white", paper_bgcolor="white",
                      xaxis=dict(title="Órdenes distintas en el periodo", range=[0, limite_x]), font=FONT)
    return fig


def _fig_gasto(ranking, umbral: int, top_n: int = 15) -> go.Figure:
    """
    Mismo ranking, pero ordenado por gasto total en vez de número de
    órdenes -- deliberadamente un ranking DISTINTO al de arriba, no el
    mismo dato repetido. Un cliente puede tener pocas órdenes pero gasto
    alto (compras grandes y esporádicas) o muchas órdenes de bajo valor --
    ver ambos rankings lado a lado muestra esa diferencia, que el ranking
    por órdenes solo no revela.
    """
    top = ranking.sort_values("gasto_total", ascending=False).head(top_n).iloc[::-1]
    total_general = ranking["gasto_total"].sum()
    pct = (top["gasto_total"] / total_general * 100) if total_general else top["gasto_total"] * 0
    colores = ["#9C4F5C" if o > umbral else "#D8C4C7" for o in top["ordenes"]]
    limite_x = top["gasto_total"].max() * 1.2  # espacio extra: etiquetas "$X,XXX" son más largas que números sueltos

    fig = go.Figure(go.Bar(
        x=top["gasto_total"], y=top["cliente"], orientation="h", marker_color=colores,
        customdata=pct,
        text=[f"${v:,.0f}" for v in top["gasto_total"]], textposition="outside",
        hovertemplate="%{y}<br>$%{x:,.2f} (%{customdata:.1f}% del gasto de todos los clientes identificados)<extra></extra>",
    ))
    fig.update_layout(margin=dict(l=170, r=60, t=30, b=40), height=420,
                      plot_bgcolor="white", paper_bgcolor="white",
                      xaxis=dict(title="Gasto total en el periodo (USD)", range=[0, limite_x]), font=FONT)
    return fig


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
        html.Div(className="grid-2", children=[
            html.Div(className="chart-card", children=[
                chart_header(
                    "Top clientes por número de órdenes",
                    "Cada barra es un cliente identificado. La línea punteada marca el umbral actual -- "
                    "muévelo en el control 'Cuentas mayoristas' de arriba y observa cómo cambia qué "
                    "barras quedan resaltadas. El salto entre la segunda y la tercera barra es la "
                    "evidencia visual de que hay un grupo de cuentas cualitativamente distinto al "
                    "resto, no un corte arbitrario.",
                ),
                dcc.Graph(figure=_fig_ranking(ranking, umbral), config={"displayModeBar": False}),
            ]),
            html.Div(className="chart-card", children=[
                chart_header(
                    "Top clientes por gasto total",
                    "Mismo grupo de clientes, ordenado por cuánto gastaron en vez de cuántas veces "
                    "compraron -- un ranking distinto, no el mismo dato repetido. Si alguien aparece "
                    "arriba aquí pero no en el gráfico de la izquierda, son compras grandes y poco "
                    "frecuentes, no un patrón de recompra mayorista.",
                ),
                dcc.Graph(figure=_fig_gasto(ranking, umbral), config={"displayModeBar": False}),
            ]),
        ]),
        html.Div(
            className="note-box important",
            children=[
                html.Strong("Cómo leer la tabla de abajo: "),
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
                sort_action="native", filter_action="native",
                export_format="xlsx", export_headers="display",
            ),
        ]),
    ]
