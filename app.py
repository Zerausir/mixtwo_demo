from __future__ import annotations

import dash
from dash import Dash, Input, Output, callback, dcc, html
from flask_login import current_user

from auth import init_auth
from config import settings
from services.queries import opciones_cascada, rango_fechas_disponible

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    suppress_callback_exceptions=True,
    title=f"{settings.cliente_nombre} — Panel de Inteligencia de Datos",
    update_title="Actualizando…",
)
server = app.server
server.config["SECRET_KEY"] = settings.secret_key

init_auth(server)

FECHA_MIN, FECHA_MAX = rango_fechas_disponible()


def navigation() -> html.Div:
    usuario_actual = current_user.username if current_user.is_authenticated else ""
    return html.Div(
        className="topbar",
        children=[
            html.Div(
                className="topbar-row1",
                children=[
                    html.Div(
                        className="brand",
                        children=[
                            html.Div("MI", className="brand-mark"),
                            html.Div([
                                html.Div(settings.cliente_nombre, className="brand-title"),
                                html.Div("Panel de inteligencia de datos", className="brand-subtitle"),
                            ]),
                        ],
                    ),
                    html.Nav(
                        className="nav-links",
                        children=[
                            dcc.Link("Resumen", href="/", className="nav-link"),
                            dcc.Link("Marcas y líneas", href="/marcas-lineas", className="nav-link"),
                            dcc.Link("Sucursales", href="/sucursales", className="nav-link"),
                            dcc.Link("Cuentas mayoristas", href="/mayoristas", className="nav-link"),
                            dcc.Link("Predicción", href="/prediccion", className="nav-link"),
                            dcc.Link("Explorador", href="/explorador", className="nav-link"),
                        ],
                    ),
                    html.Div(
                        className="snapshot-badge",
                        title="Este panel usa una muestra fija de datos, no una conexión en vivo al sistema de mixtwo.",
                        children=[
                            html.Span(className="dot"),
                            f"Datos de muestra: {FECHA_MIN} a {FECHA_MAX}",
                        ],
                    ),
                    html.Div(
                        className="nav-user",
                        children=[
                            html.Span(usuario_actual, className="nav-user-name"),
                            html.A("Salir", href="/logout", className="nav-link nav-logout"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="filter-bar",
                children=[
                    html.Div(className="filter-group", children=[
                        html.Label("Sucursal", className="filter-label"),
                        dcc.Dropdown(id="filtro-sucursal", multi=True, placeholder="Todas las sucursales"),
                    ]),
                    html.Div(className="filter-group", children=[
                        html.Label("Marca", className="filter-label"),
                        dcc.Dropdown(id="filtro-marca", multi=True, placeholder="Todas las marcas"),
                    ]),
                    html.Div(className="filter-group", children=[
                        html.Label("Línea de producto", className="filter-label"),
                        dcc.Dropdown(id="filtro-linea", multi=True, placeholder="Todas las líneas"),
                    ]),
                    html.Div(className="filter-group", children=[
                        html.Label("Rango de fechas", className="filter-label"),
                        dcc.DatePickerRange(
                            id="filtro-fechas",
                            min_date_allowed=FECHA_MIN,
                            max_date_allowed=FECHA_MAX,
                            start_date=FECHA_MIN,
                            end_date=FECHA_MAX,
                            display_format="DD/MM/YYYY",
                            clearable=False,
                        ),
                    ]),
                    html.Div(className="filter-group filter-group-mayorista", children=[
                        html.Label("Cuentas mayoristas", className="filter-label"),
                        html.Div(
                            className="mayorista-control",
                            children=[
                                dcc.Checklist(
                                    id="filtro-mayorista-activo",
                                    options=[{"label": " Excluir si supera", "value": "excluir"}],
                                    value=["excluir"],
                                    className="mayorista-checkbox",
                                ),
                                dcc.Input(
                                    id="filtro-mayorista-umbral",
                                    type="number", min=1, step=1, value=15,
                                    className="mayorista-input",
                                ),
                                html.Span("órdenes", className="mayorista-suffix"),
                            ],
                        ),
                    ]),
                    html.Button("Limpiar filtros", id="filtro-limpiar", className="filter-reset", n_clicks=0),
                ],
            ),
        ],
    )


def serve_layout() -> html.Div:
    return html.Div(
        className="app-shell",
        children=[
            navigation(),
            html.Main(dash.page_container, className="page-container"),
            html.Footer(
                "Panel construido sobre la muestra de datos compartida por mixtwo — "
                "no refleja el modelo predictivo completo de la propuesta ni una conexión en vivo al ERP.",
                className="footer",
            ),
        ],
    )


app.layout = serve_layout


# ---------------------------------------------------------------------------
# Opciones en cascada: cada dropdown recalcula sus opciones a partir de los
# OTROS filtros activos (nunca del suyo propio, para no auto-restringirse).
# Esto es lo que hace que, por ejemplo, elegir una marca deje ver solo las
# sucursales donde esa marca realmente se vende.
# ---------------------------------------------------------------------------
@callback(
    Output("filtro-sucursal", "options"),
    Output("filtro-marca", "options"),
    Output("filtro-linea", "options"),
    Input("filtro-sucursal", "value"),
    Input("filtro-marca", "value"),
    Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"),
    Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"),
    Input("filtro-mayorista-umbral", "value"),
)
def actualizar_opciones_filtros(sucursales_sel, marcas_sel, lineas_sel, fecha_ini, fecha_fin, mayorista_activo, umbral):
    umbral_efectivo = umbral if (mayorista_activo and "excluir" in mayorista_activo and umbral) else None
    opciones = opciones_cascada(sucursales_sel, marcas_sel, lineas_sel, fecha_ini, fecha_fin, umbral_efectivo)
    return (
        [{"label": s.title(), "value": s} for s in opciones["sucursales"]],
        [{"label": m, "value": m} for m in opciones["marcas"]],
        [{"label": l, "value": l} for l in opciones["lineas"]],
    )


@callback(
    Output("filtro-sucursal", "value"),
    Output("filtro-marca", "value"),
    Output("filtro-linea", "value"),
    Output("filtro-fechas", "start_date"),
    Output("filtro-fechas", "end_date"),
    Output("filtro-mayorista-activo", "value"),
    Output("filtro-mayorista-umbral", "value"),
    Input("filtro-limpiar", "n_clicks"),
    prevent_initial_call=True,
)
def limpiar_filtros(n_clicks):
    return [], [], [], FECHA_MIN, FECHA_MAX, ["excluir"], 15


if __name__ == "__main__":
    app.run(host=settings.app_host, port=settings.app_port, debug=settings.app_debug)
