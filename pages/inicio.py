from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from components.ui import (
    chart_title_with_help,
    empty_state,
    formato_entero,
    formato_moneda,
    kpi_card,
    page_header,
    umbral_efectivo,
)
from services.queries import (
    distribucion_ticket,
    hay_datos,
    resumen_general,
    ventas_diarias_por_mes,
    ventas_por_dia_semana,
)

dash.register_page(__name__, path="/", name="Resumen")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-sucursal", "value"), Input("filtro-marca", "value"), Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
]


def layout():
    return html.Div(
        className="page-content",
        children=[
            page_header(
                "Resumen ejecutivo",
                "Vista general del negocio para el periodo y los filtros seleccionados arriba. "
                "Se excluye siempre el centro administrativo (MATRIZ) y, según el control de "
                "'Cuentas mayoristas' de arriba, las cuentas que superan el umbral configurado.",
            ),
            html.Div(id="inicio-contenido"),
        ],
    )


def _fig_tendencia(df) -> go.Figure:
    colores = ["#D8C4C7" if incompleto else "#9C4F5C" for incompleto in df["incompleto"]]
    fig = go.Figure(go.Bar(
        x=df["mes"], y=df["promedio_diario"], marker_color=colores,
        text=["Datos incompletos" if p else "" for p in df["incompleto"]], textposition="outside",
        hovertemplate="%{x}<br>Promedio diario: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(margin=dict(l=40, r=20, t=20, b=40), height=320,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis_title="Venta promedio diaria (USD)", font=FONT)
    return fig


def _fig_boxplot_ticket(df) -> go.Figure:
    fig = go.Figure(go.Box(x=df["valor_orden"], marker_color="#9C4F5C", boxmean=True, name=""))
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=40), height=190,
                      plot_bgcolor="white", paper_bgcolor="white",
                      xaxis_title="Valor de la orden (USD)", font=FONT,
                      showlegend=False, yaxis=dict(showticklabels=False))
    return fig


def _fig_dia_semana(df) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df["dia_semana"], y=df["venta_promedio"], marker_color="#201A1A",
        hovertemplate="%{x}<br>Venta promedio: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(margin=dict(l=40, r=20, t=20, b=40), height=300,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis_title="Venta promedio (USD)", font=FONT)
    return fig


@callback(Output("inicio-contenido", "children"), *FILTROS)
def actualizar(sucursales, marcas, lineas, fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)

    if not hay_datos(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef):
        return empty_state()

    resumen = resumen_general(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef)
    tendencia = ventas_diarias_por_mes(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef)
    ticket = distribucion_ticket(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef)
    dia_semana = ventas_por_dia_semana(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef)

    return [
        html.Div(className="kpi-grid", children=[
            kpi_card("Ventas totales", formato_moneda(resumen["ventas_totales"]), "Periodo y filtros seleccionados"),
            kpi_card("Órdenes reales", formato_entero(resumen["ordenes"]), "Facturas, no líneas de producto"),
            kpi_card("Ticket promedio", formato_moneda(resumen["ticket_promedio"]),
                     f"Mediana: {formato_moneda(resumen['ticket_mediana'])}"),
            kpi_card("Unidades vendidas", formato_entero(resumen["unidades_totales"])),
        ]),
        html.Div(className="chart-card", children=[
            chart_title_with_help(
                "Venta promedio diaria por mes",
                "Se usa el promedio por día, no la suma del mes completo, para que un mes con "
                "menos días de datos no se vea como una caída de ventas. Las barras en color claro "
                "marcadas 'Datos incompletos' tienen menos de 25 días de venta registrados dentro de "
                "los filtros elegidos — puede ser porque el corte de la muestra ocurre a mitad de ese "
                "mes, o porque la tienda/marca/línea filtrada no tuvo actividad todo el mes (por "
                "ejemplo, una tienda que abrió a fin de mes). Compáralas con cuidado frente a las "
                "demás.",
            ),
            dcc.Graph(figure=_fig_tendencia(tendencia), config={"displayModeBar": False}),
        ]),
        html.Div(className="grid-2", children=[
            html.Div(className="chart-card", children=[
                chart_title_with_help(
                    "Distribución del valor de orden",
                    "Cada punto es una compra completa. La línea del medio (mediana) representa "
                    "mejor la compra típica que el promedio, que compras grandes puntuales inflan.",
                ),
                dcc.Graph(figure=_fig_boxplot_ticket(ticket), config={"displayModeBar": False}),
            ]),
            html.Div(className="chart-card", children=[
                chart_title_with_help(
                    "Venta promedio por día de la semana",
                    "Promedio histórico de ventas para cada día. Útil para planear personal y "
                    "reposición: los días más altos necesitan más preparación.",
                ),
                dcc.Graph(figure=_fig_dia_semana(dia_semana), config={"displayModeBar": False}),
            ]),
        ]),
    ]
