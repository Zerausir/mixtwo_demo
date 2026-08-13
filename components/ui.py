from __future__ import annotations

from dash import html


def kpi_card(titulo: str, valor: str, subtitulo: str = "") -> html.Div:
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(titulo, className="kpi-title"),
            html.Div(valor, className="kpi-value"),
            html.Div(subtitulo, className="kpi-subtitle") if subtitulo else None,
        ],
    )


def formato_moneda(valor: float) -> str:
    return f"${valor:,.2f}"


def formato_entero(valor: int) -> str:
    return f"{valor:,.0f}"


def page_header(titulo: str, descripcion: str = "") -> html.Div:
    return html.Div(
        className="page-header",
        children=[
            html.H2(titulo, className="page-title"),
            html.P(descripcion, className="page-description") if descripcion else None,
        ],
    )
