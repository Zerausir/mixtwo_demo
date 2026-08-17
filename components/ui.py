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


def help_icon(texto: str) -> html.Span:
    """Ícono '?' con tooltip al pasar el mouse -- explica un gráfico sin
    que Iván tenga que estar presente para aclararlo en vivo."""
    return html.Span(
        className="help-icon",
        children=["?", html.Span(texto, className="tooltip-text")],
    )


def chart_title_with_help(titulo: str, ayuda: str = "") -> html.Div:
    hijos = [html.H3(titulo, className="chart-title")]
    if ayuda:
        hijos.append(help_icon(ayuda))
    return html.Div(className="chart-title-row", children=hijos)


def empty_state(mensaje: str = "No hay datos para esta combinación de filtros.") -> html.Div:
    return html.Div(
        className="empty-state",
        children=[
            html.Div("🔍", className="empty-state-icon"),
            html.Div("Sin resultados", className="empty-state-title"),
            html.Div(
                f"{mensaje} Prueba ampliando el rango de fechas o quitando alguno de "
                "los filtros seleccionados arriba.",
                className="empty-state-text",
            ),
        ],
    )
