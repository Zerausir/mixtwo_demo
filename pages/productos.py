from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from components.ui import con_carga, chart_header, empty_state, formato_entero, formato_moneda, kpi_card, page_header, \
    umbral_efectivo
from services.queries import hay_datos, pareto_productos

dash.register_page(__name__, path="/productos", name="Productos")

FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)
FILTROS = [
    Input("filtro-sucursal", "value"), Input("filtro-marca", "value"), Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"), Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"), Input("filtro-mayorista-umbral", "value"),
]


def layout():
    return html.Div(className="page-content", children=[
        page_header(
            "Productos: concentración de ventas (Pareto)",
            "¿Cuántos productos explican la mayoría de las ventas? Útil para priorizar reposición e "
            "inventario: si pocos productos explican casi todo, se gestionan distinto a un catálogo "
            "disperso.",
        ),
        con_carga("carga-productos-contenido", html.Div(id="productos-contenido")),
    ])


def _fig_pareto(top) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(1, len(top) + 1)), y=top["ventas"], name="Ventas por producto",
        marker_color="#9C4F5C", yaxis="y1",
        hovertemplate="%{customdata}<br>Ventas: $%{y:,.0f}<extra></extra>",
        customdata=top["producto"],
    ))
    fig.add_trace(go.Scatter(
        x=list(range(1, len(top) + 1)), y=top["acumulado_pct"], name="% acumulado",
        mode="lines+markers", line=dict(color="#201A1A", width=2), yaxis="y2",
        hovertemplate="Acumulado: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=80, line_dash="dash", line_color="#8A7C79", yref="y2",
                  annotation_text="80%", annotation_position="right")
    fig.update_layout(
        margin=dict(l=50, r=50, t=30, b=40), height=380,
        plot_bgcolor="white", paper_bgcolor="white", font=FONT,
        xaxis_title="Ranking de producto (de mayor a menor venta)",
        yaxis=dict(title="Ventas (USD)"),
        yaxis2=dict(title="% acumulado", overlaying="y", side="right", range=[0, 100]),
        legend=dict(orientation="h", y=1.12),
    )
    return fig


@callback(Output("productos-contenido", "children"), *FILTROS)
def actualizar(sucursales, marcas, lineas, fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_ef = umbral_efectivo(mayorista_activo, umbral)

    if not hay_datos(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef):
        return empty_state()

    resultado = pareto_productos(sucursales, marcas, lineas, fecha_ini, fecha_fin, umbral_ef, top_n=25)
    top = resultado["top"]

    return [
        html.Div(className="kpi-grid", children=[
            kpi_card("Productos distintos vendidos", formato_entero(resultado["n_skus"])),
            kpi_card(
                "Productos que explican el 80% de las ventas",
                formato_entero(resultado["n_para_80"]),
                f"{resultado['pct_skus_para_80']:.1f}% del catálogo activo",
                ayuda="Si este porcentaje es alto (catálogo disperso, no concentrado en pocos "
                      "'productos estrella'), la reposición no se puede simplificar a unos pocos SKUs.",
            ),
        ]),
        html.Div(className="chart-card", children=[
            chart_header(
                "Curva de Pareto — top 25 productos",
                "Barras: ventas de cada producto (ordenados de mayor a menor). Línea: porcentaje "
                "acumulado de las ventas totales. La regla clásica '80/20' esperaría que ~20% de los "
                "productos expliquen el 80% — en mixtwo hace falta un porcentaje bastante mayor del "
                "catálogo, señal de que la demanda está repartida en muchos productos, no concentrada "
                "en pocos.",
            ),
            dcc.Graph(figure=_fig_pareto(top), config={"displayModeBar": False}),
        ]),
        html.Div(className="table-card", children=[
            html.H3("Top 25 productos por ventas", className="chart-title"),
            dash_table.DataTable(
                data=top.round(2).to_dict("records"),
                columns=[
                    {"name": "Código", "id": "codigo"},
                    {"name": "Producto", "id": "producto"},
                    {"name": "Ventas (USD)", "id": "ventas"},
                    {"name": "% acumulado", "id": "acumulado_pct"},
                ],
                style_as_list_view=True,
                style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "padding": "8px", "fontSize": "13px"},
                style_header={"fontWeight": "600", "backgroundColor": "#FBF3F1"},
                page_size=15, sort_action="native",
            ),
        ]),
    ]
