from __future__ import annotations

import dash
from dash import Dash, Input, Output, callback, dcc, html
from flask_login import current_user

from auth import init_auth
from config import settings

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    suppress_callback_exceptions=True,
    title=f"{settings.cliente_nombre} — Demo de Inteligencia de Datos",
    update_title="Actualizando…",
)
server = app.server
server.config["SECRET_KEY"] = settings.secret_key

init_auth(server)


def navigation() -> html.Header:
    usuario_actual = current_user.username if current_user.is_authenticated else ""
    return html.Header(
        className="topbar",
        children=[
            dcc.Location(id="app-url", refresh=False),
            html.Div(
                className="brand",
                children=[
                    html.Div(settings.cliente_nombre[:2].upper(), className="brand-mark"),
                    html.Div(
                        [
                            html.Div(settings.cliente_nombre, className="brand-title"),
                            html.Div("Demo — Inteligencia de datos", className="brand-subtitle"),
                        ]
                    ),
                ],
            ),
            html.Nav(
                className="nav-links",
                children=[
                    dcc.Link("Resumen", href="/", className="nav-link"),
                    dcc.Link("Marcas y líneas", href="/marcas-lineas", className="nav-link"),
                    dcc.Link("Sucursales", href="/sucursales", className="nav-link"),
                    dcc.Link("Predicción", href="/prediccion", className="nav-link"),
                    dcc.Link("Explorador", href="/explorador", className="nav-link"),
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
    )


def serve_layout() -> html.Div:
    return html.Div(
        className="app-shell",
        children=[
            navigation(),
            html.Main(dash.page_container, className="page-container"),
            html.Footer(
                "Demo construido sobre la muestra de datos compartida por mixtwo — "
                "no refleja el modelo predictivo completo de la propuesta.",
                className="footer",
            ),
        ],
    )


app.layout = serve_layout

if __name__ == "__main__":
    app.run(host=settings.app_host, port=settings.app_port, debug=settings.app_debug)
