"""
services/database.py — Conexión de solo lectura al mart SQLite.

Patrón simplificado respecto a OBTEL (que usa SQLAlchemy contra Postgres
con roles separados para auth/lectura). Para el demo, una sola conexión
SQLite de solo lectura es suficiente y evita infraestructura adicional
que mantener.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config import settings


def get_connection() -> sqlite3.Connection:
    db_path = Path(settings.db_path)
    if not db_path.exists():
        raise RuntimeError(
            f"No se encontró la base de datos en {db_path}. "
            f"Corre primero: python build_data.py <csv> {db_path}"
        )
    # uri=True + mode=ro: conexión estrictamente de solo lectura -- el
    # dashboard nunca escribe en el mart.
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    return con
