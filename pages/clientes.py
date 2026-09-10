from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from components.ui import con_carga, chart_header, empty_state, formato_entero, formato_moneda, kpi_card, page_header, \
    umbral_efectivo
from services.queries import clientes_nuevos_vs_recurrentes, resumen_clientes

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


@callback(Output("clientes-contenido", "children"), *FILTROS)
def actualizar(fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)

    resumen = resumen_clientes(fecha_ini, fecha_fin, umbral_ef)
    nuevos_rec = clientes_nuevos_vs_recurrentes(fecha_ini, fecha_fin, umbral_ef)

    if resumen["ordenes_totales"] == 0:
        return empty_state()

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
    ]
