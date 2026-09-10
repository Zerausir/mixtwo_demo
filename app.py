from __future__ import annotations

import dash
from dash import Dash, Input, Output, callback, dcc, html
from flask_login import current_user

from auth import init_auth
from components.ui import filtro_chip
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

# ---------------------------------------------------------------------------
# Qué filtro aplica en cada página -- controla tanto si el dropdown queda
# deshabilitado (visualmente apagado, no solo un texto que alguien podría no
# leer) como qué dice su chip en la barra de "filtros activos". Página no
# listada = todos aplican (fallback seguro).
# ---------------------------------------------------------------------------
FILTROS_POR_PAGINA = {
    "/": {"sucursal": True, "marca": True, "linea": True},
    "/marcas-lineas": {"sucursal": True, "marca": True, "linea": True},
    "/sucursales": {"sucursal": False, "marca": True, "linea": True},
    "/productos": {"sucursal": True, "marca": True, "linea": True},
    "/clientes": {"sucursal": False, "marca": False, "linea": False},
    "/mayoristas": {"sucursal": False, "marca": False, "linea": False},
    "/prediccion": {"sucursal": True, "marca": False, "linea": False},
    "/explorador": {"sucursal": True, "marca": True, "linea": True},
}


def navigation() -> html.Div:
    usuario_actual = current_user.username if current_user.is_authenticated else ""
    return html.Div(
        className="topbar",
        children=[
            dcc.Location(id="url-actual", refresh=False),
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
                            dcc.Link("Resumen", href="/", id="nav-link-/", className="nav-link"),
                            dcc.Link("Marcas y líneas", href="/marcas-lineas", id="nav-link-/marcas-lineas",
                                     className="nav-link"),
                            dcc.Link("Productos", href="/productos", id="nav-link-/productos", className="nav-link"),
                            dcc.Link("Sucursales", href="/sucursales", id="nav-link-/sucursales", className="nav-link"),
                            dcc.Link("Clientes", href="/clientes", id="nav-link-/clientes", className="nav-link"),
                            dcc.Link("Cuentas mayoristas", href="/mayoristas", id="nav-link-/mayoristas",
                                     className="nav-link"),
                            dcc.Link("Predicción", href="/prediccion", id="nav-link-/prediccion", className="nav-link"),
                            dcc.Link("Explorador", href="/explorador", id="nav-link-/explorador", className="nav-link"),
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
            html.Div(id="filtros-activos", className="filtros-activos-bar"),
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


# ---------------------------------------------------------------------------
# Filtros deshabilitados por página: un dropdown que no afecta nada en la
# página actual se apaga visualmente (opacidad + cursor bloqueado, ver CSS),
# en vez de quedar activo sin hacer nada -- eso es lo que hacía parecer el
# panel "no profesional": un control que responde al clic pero no cambia
# ningún número es peor que uno claramente apagado.
# ---------------------------------------------------------------------------
@callback(
    Output("filtro-sucursal", "disabled"),
    Output("filtro-marca", "disabled"),
    Output("filtro-linea", "disabled"),
    Input("url-actual", "pathname"),
)
def actualizar_filtros_deshabilitados(pathname):
    aplica = FILTROS_POR_PAGINA.get(pathname, {"sucursal": True, "marca": True, "linea": True})
    return not aplica["sucursal"], not aplica["marca"], not aplica["linea"]


NAV_PATHS = ["/", "/marcas-lineas", "/productos", "/sucursales", "/clientes", "/mayoristas", "/prediccion",
             "/explorador"]


@callback(
    [Output(f"nav-link-{p}", "className") for p in NAV_PATHS],
    Input("url-actual", "pathname"),
)
def marcar_pagina_activa(pathname):
    return [
        "nav-link active" if p == pathname else "nav-link"
        for p in NAV_PATHS
    ]


def _etiqueta_lista(valores) -> str:
    if not valores:
        return "Todas"
    if len(valores) <= 2:
        return ", ".join(valores)
    return f"{len(valores)} seleccionadas"


@callback(
    Output("filtros-activos", "children"),
    Input("url-actual", "pathname"),
    Input("filtro-sucursal", "value"),
    Input("filtro-marca", "value"),
    Input("filtro-linea", "value"),
    Input("filtro-fechas", "start_date"),
    Input("filtro-fechas", "end_date"),
    Input("filtro-mayorista-activo", "value"),
    Input("filtro-mayorista-umbral", "value"),
)
def actualizar_chips_filtros(pathname, sucursales, marcas, lineas, fecha_ini, fecha_fin, mayorista_activo, umbral):
    aplica = FILTROS_POR_PAGINA.get(pathname, {"sucursal": True, "marca": True, "linea": True})

    mayorista_texto = f"Excluidas si superan {umbral} órdenes" if (
            mayorista_activo and "excluir" in mayorista_activo and umbral) else "Incluidas (sin excluir)"

    return [
        filtro_chip("Sucursal", _etiqueta_lista(sucursales), aplica["sucursal"]),
        filtro_chip("Marca", _etiqueta_lista(marcas), aplica["marca"]),
        filtro_chip("Línea", _etiqueta_lista(lineas), aplica["linea"]),
        filtro_chip("Fechas", f"{fecha_ini} → {fecha_fin}"),
        filtro_chip("Cuentas mayoristas", mayorista_texto),
    ]


if __name__ == "__main__":
    app.run(host=settings.app_host, port=settings.app_port, debug=settings.app_debug)
