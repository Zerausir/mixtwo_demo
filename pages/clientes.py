from __future__ import annotations

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from components.ui import con_carga, chart_header, empty_state, formato_entero, formato_moneda, kpi_card, page_header, \
    umbral_efectivo
from services.queries import clientes_nuevos_vs_recurrentes, listado_clientes, resumen_clientes

dash.register_page(__name__, path="/clientes", name="Clientes")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Clientes: captación y recurrencia",
            "Esta página solo se filtra por fecha (no por sucursal/marca/línea) — el estatus de un "
            "cliente (nuevo, recurrente, identificado) es una propiedad del cliente, no del producto "
            "que se esté mirando. Se excluyen las cuentas mayoristas según el control de arriba, para "
            "que dos cuentas corporativas no distorsionen las cifras de clientes individuales.",
        ),
        con_carga("carga-clientes-contenido", html.Div(id="clientes-contenido")),
        # Este contenedor vive en la parte ESTÁTICA de la página (no dentro
        # de "clientes-contenido") a propósito: su callback depende de
        # "tabla-clientes", un componente que solo existe DESPUÉS de que el
        # callback de "clientes-contenido" haya corrido. Es una cadena de
        # dos pasos válida (A crea la tabla -> B reacciona a la tabla), muy
        # distinta del bug de Resumen (donde un control estaba adentro del
        # mismo callback que lo necesitaba como entrada, un ciclo de un
        # solo paso que nunca se disparaba). Aun así, este contenedor debe
        # existir desde el principio para que la cadena funcione.
        con_carga("carga-clientes-ranking", html.Div(id="clientes-ranking-grafico")),
    ])


def _fig_nuevos_recurrentes(df) -> go.Figure:
    nuevos = df[df["tipo"] == "Nuevos"].set_index("periodo")["ordenes"]
    recurrentes = df[df["tipo"] == "Recurrentes"].set_index("periodo")["ordenes"]
    periodos = sorted(df["periodo"].unique())

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=periodos, y=[nuevos.get(p, 0) for p in periodos], name="Nuevos",
        marker_color="#D8C4C7", hovertemplate="%{x}<br>Nuevos: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=periodos, y=[recurrentes.get(p, 0) for p in periodos], name="Recurrentes",
        marker_color="#9C4F5C", hovertemplate="%{x}<br>Recurrentes: %{y}<extra></extra>",
    ))
    fig.update_layout(
        barmode="stack", margin=dict(l=40, r=20, t=20, b=40), height=340,
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="Órdenes", font=FONT, legend=dict(orientation="h", y=1.12),
    )
    return fig


def _fig_formato(resumen: dict) -> go.Figure:
    identificadas = resumen["ordenes_totales"] - resumen["ordenes_consumidor_final"]
    fig = go.Figure(go.Bar(
        x=["Cliente identificado", "Consumidor final"],
        y=[identificadas, resumen["ordenes_consumidor_final"]],
        marker_color=["#9C4F5C", "#D8C4C7"],
        text=[formato_entero(identificadas), formato_entero(resumen["ordenes_consumidor_final"])],
        textposition="outside",
        hovertemplate="%{x}<br>%{y} órdenes<extra></extra>",
    ))
    fig.update_layout(margin=dict(l=40, r=20, t=20, b=40), height=300,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis_title="Órdenes", font=FONT)
    return fig


def _fig_ranking_clientes(df: pd.DataFrame) -> go.Figure:
    """
    Barras múltiples (órdenes + gasto total) por cliente -- reacciona al
    filtro nativo de la tabla de clientes (ver derived_virtual_data en el
    callback de abajo). Con dos métricas de escala muy distinta ($ vs.
    conteo de órdenes), se usan dos ejes Y en vez de forzarlas a la misma
    escala, que aplastaría una de las dos barras.
    """
    etiquetas = df["Cliente"].str.title()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=etiquetas, y=df["Gasto total (USD)"], name="Gasto total (USD)",
        marker_color="#9C4F5C", yaxis="y1",
        hovertemplate="%{x}<br>Gasto: $%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=etiquetas, y=df["Órdenes"], name="Órdenes", marker_color="#201A1A", yaxis="y2",
        hovertemplate="%{x}<br>Órdenes: %{y}<extra></extra>",
    ))
    fig.update_layout(
        barmode="group", margin=dict(l=50, r=50, t=30, b=110), height=420,
        plot_bgcolor="white", paper_bgcolor="white", font=FONT,
        xaxis=dict(tickangle=-45),
        yaxis=dict(title="Gasto total (USD)"),
        yaxis2=dict(title="Órdenes", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


@callback(Output("clientes-contenido", "children"), *FILTROS)
def actualizar(fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)

    resumen = resumen_clientes(fecha_ini, fecha_fin, umbral_ef)
    nuevos_rec = clientes_nuevos_vs_recurrentes(fecha_ini, fecha_fin, umbral_ef)
    listado = listado_clientes(fecha_ini, fecha_fin, umbral_ef)

    if resumen["ordenes_totales"] == 0:
        return empty_state()

    columnas_tabla = {
        "identificacion": "Identificación", "cliente": "Cliente", "formato": "Formato",
        "primera_compra": "Primera compra", "ultima_compra": "Última compra",
        "ordenes": "Órdenes", "gasto_total": "Gasto total (USD)",
        "ticket_promedio": "Ticket promedio (USD)", "tipo": "Tipo",
    }
    listado_mostrar = listado[list(columnas_tabla.keys())].rename(columns=columnas_tabla)

    return [
        html.Div(className="kpi-grid", children=[
            kpi_card(
                "Tasa de recompra",
                f"{resumen['tasa_recompra']:.1f}%",
                f"{formato_entero(resumen['clientes_recurrentes'])} de {formato_entero(resumen['clientes_identificados'])} clientes identificados",
                ayuda="Porcentaje de clientes identificados que hicieron 2 o más compras en el periodo.",
            ),
            kpi_card(
                "Órdenes de consumidor final",
                f"{resumen['pct_ordenes_consumidor_final']:.1f}%",
                f"{formato_entero(resumen['ordenes_consumidor_final'])} de {formato_entero(resumen['ordenes_totales'])} órdenes",
                ayuda="Ventas de mostrador sin registrar la identidad del comprador.",
            ),
            kpi_card(
                "Ticket: identificado vs. consumidor final",
                f"{formato_moneda(resumen['ticket_identificado'])} / {formato_moneda(resumen['ticket_consumidor_final'])}",
                "El ticket de consumidor final es notablemente menor",
            ),
            kpi_card(
                "Ventas de consumidor final",
                f"{resumen['pct_ventas_consumidor_final']:.1f}%",
                "Del valor total de ventas del periodo",
            ),
        ]),
        html.Div(className="chart-card", children=[
            chart_header(
                "Órdenes de clientes nuevos vs. recurrentes, por mes",
                "'Nuevo' = el cliente compró por primera vez ese mes. 'Recurrente' = ya había comprado "
                "antes. Si la porción recurrente crece mes a mes, es evidencia de que se está "
                "construyendo una base de clientes que vuelve, no solo tráfico nuevo constante.",
            ),
            dcc.Graph(figure=_fig_nuevos_recurrentes(nuevos_rec),
                      config={"displayModeBar": False}) if not nuevos_rec.empty else empty_state(),
        ]),
        html.Div(className="chart-card", children=[
            chart_header(
                "Órdenes: cliente identificado vs. consumidor final",
                "'Consumidor final' es una venta de mostrador sin registrar quién compró — no se "
                "puede saber si es un cliente nuevo o recurrente. Reducir esta proporción (pidiendo "
                "identificación en caja) habilita más análisis de clientes a futuro.",
            ),
            dcc.Graph(figure=_fig_formato(resumen), config={"displayModeBar": False}),
        ]),
        html.Div(className="table-card", children=[
            html.H3(f"Listado de clientes ({formato_entero(len(listado))})", className="chart-title"),
            html.P(
                "Busca por identificación o nombre escribiendo en la fila de filtro bajo cada "
                "encabezado. Usa el botón 'Export' para descargar este listado completo a Excel.",
                className="chart-caption",
            ),
            dash_table.DataTable(
                id="tabla-clientes",
                data=listado_mostrar.round(2).to_dict("records"),
                columns=[{"name": c, "id": c} for c in listado_mostrar.columns],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px", "fontSize": "13px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{Tipo} = Recurrente"},
                        "backgroundColor": "#F5DEE1",
                        "color": "#9C4F5C",
                    }
                ],
                sort_action="native", filter_action="native", page_size=20,
                export_format="xlsx", export_headers="display",
            ),
        ]),
    ]


@callback(Output("clientes-ranking-grafico", "children"), Input("tabla-clientes", "derived_virtual_data"))
def actualizar_ranking_clientes(filas_filtradas):
    """
    Reacciona al filtro nativo de la tabla de arriba: si buscas un cliente
    puntual, este gráfico se reduce a esa búsqueda. `derived_virtual_data`
    es el listado completo que coincide con el filtro actual (no solo la
    página visible), así que refleja exactamente lo que la tabla está
    mostrando -- no una copia aparte que se pueda desincronizar de ella.
    """
    if not filas_filtradas:
        return empty_state("No hay clientes que coincidan con el filtro de la tabla de arriba.")

    df = pd.DataFrame(filas_filtradas)
    total_coincidencias = len(df)
    df = df.sort_values("Gasto total (USD)", ascending=False).head(25)

    if total_coincidencias > 25:
        caption_extra = (
            f"Mostrando los 25 de mayor gasto, de {total_coincidencias} clientes que coinciden con "
            "el filtro de la tabla de arriba -- estrecha la búsqueda para ver un cliente puntual."
        )
    else:
        caption_extra = (
            f"Mostrando los {total_coincidencias} clientes que coinciden con el filtro de la tabla "
            "de arriba."
        )

    return html.Div(className="chart-card", children=[
        chart_header("Órdenes y gasto por cliente", caption_extra),
        dcc.Graph(figure=_fig_ranking_clientes(df), config={"displayModeBar": False}),
    ])
