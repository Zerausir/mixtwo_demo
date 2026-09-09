from __future__ import annotations

from dash import html


def umbral_efectivo(mayorista_activo, umbral):
    """
    Traduce los dos controles globales (checkbox + número) al valor que
    esperan las funciones de services/queries.py: None si la exclusión
    está desactivada o el número no es válido, o el entero del umbral si
    está activa. Centralizado aquí para que las 6 páginas no repitan la
    misma condición.
    """
    if mayorista_activo and "excluir" in mayorista_activo and umbral:
        try:
            return int(umbral)
        except (TypeError, ValueError):
            return None
    return None


def kpi_card(titulo: str, valor: str, subtitulo: str = "", ayuda: str = "") -> html.Div:
    encabezado = [html.Span(titulo, className="kpi-title")]
    if ayuda:
        encabezado.append(help_icon(ayuda))
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(encabezado, className="kpi-title-row"),
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
    """Ícono '?' con tooltip al pasar el mouse -- para profundidad adicional,
    NO como único lugar donde vive la explicación (ver chart_header)."""
    return html.Span(
        className="help-icon",
        children=["?", html.Span(texto, className="tooltip-text")],
    )


def chart_header(titulo: str, caption: str = "") -> html.Div:
    """
    Encabezado de gráfico con texto explicativo SIEMPRE VISIBLE debajo del
    título (no un tooltip que depende de que alguien pase el mouse encima).
    Un gerente viendo el panel sin que Iván esté presente para explicar en
    vivo necesita esto legible de entrada, no descubrible por accidente --
    mismo patrón que los subtítulos permanentes de OBTEL.
    """
    hijos = [html.H3(titulo, className="chart-title")]
    if caption:
        hijos.append(html.P(caption, className="chart-caption"))
    return html.Div(className="chart-header-block", children=hijos)


def filtro_chip(etiqueta: str, valor: str, aplica: bool = True) -> html.Span:
    """Un 'chip' de la barra de filtros activos -- igual al breadcrumb de
    Power BI/OBTEL que muestra de un vistazo qué se está mirando, sin tener
    que revisar cada selector de la barra de arriba."""
    clase = "filter-chip" if aplica else "filter-chip filter-chip-inactive"
    texto = valor if aplica else "No aplica en esta página"
    return html.Span(
        className=clase,
        children=[html.Span(f"{etiqueta}: ", className="filter-chip-label"), texto],
    )


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
