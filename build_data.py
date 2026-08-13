"""
build_data.py — ETL del demo mixtwo.

Lee el CSV crudo de ventas (formato ERP: 55 columnas, encoding cp1252),
deriva MARCA y LINEA_PRODUCTO por reglas de negocio (no existen como
campos explícitos en el origen), y construye una base SQLite de solo
lectura que la aplicación consulta en producción.

Se corre UNA VEZ, al construir la imagen Docker (ver Dockerfile) o
manualmente en desarrollo local:

    python build_data.py data/ventas_mixtwo.csv data/mart.db

Diseño deliberado para el DEMO (distinto de la arquitectura de
producción de Fase 1-4):
- SQLite embebido en la imagen, no Postgres administrado -- el demo usa
  datos estáticos (el corte de 5 meses que envió el cliente), no un
  pipeline en vivo contra el ERP. Cuando el proyecto avance a producción,
  este mismo script es la base para el ETL real, apuntando a Postgres.
- No se versiona el CSV crudo en Git (ver .gitignore) -- son datos de
  ventas reales del cliente. Solo el mart.db ya agregado/anonimizado a
  nivel de fila de transacción se empaqueta en la imagen del contenedor,
  y la imagen del contenedor vive en un registro privado, nunca pública.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Reglas de derivación de MARCA (ver hallazgo: prefijo alfabético dentro del
# campo PRODUCTO, antes del código numérico -- ej. "PB748606", "LIZ74381").
# Cobertura observada: ~75% del valor de ventas. El resto queda como
# "SIN IDENTIFICAR" -- explícito en vez de adivinar.
# ---------------------------------------------------------------------------
PREFIJO_A_MARCA = {
    "LIZ": "Liz",
    "PB": "Punto Blanco",
    "SMK": "Selmark",
    "SMKP": "Selmark",
    "MDC": "Mara Di Carli",
    "HOP": "Hope",
    "HOPL": "Hope",
    "HOPI": "Hope",
    "CLV": "Clever",
    "MAP": "Mapalé",
    "PLI": "Plie",
    "CAR": "Carol",
    "JAN": "Jan",
    "TAL": "Talla Grande",  # ajustar si el cliente confirma otro nombre
    "NUAS": "Nuas",
    "NUASZ": "Nuas",
    "NUAP": "Nuap",
    "GAR": "Gar",
    "CAC": "Cacharel",
    "MAR": "Mari M",
}


def derivar_marca(producto: str) -> str:
    if not isinstance(producto, str):
        return "SIN IDENTIFICAR"
    m = re.search(r"\b([A-Z]{2,5})\d{4,}", producto)
    if not m:
        return "SIN IDENTIFICAR"
    prefijo = m.group(1)
    return PREFIJO_A_MARCA.get(prefijo, f"OTRA ({prefijo})")


# ---------------------------------------------------------------------------
# Reglas de derivación de LINEA_PRODUCTO desde el prefijo de CATEGORÍA
# (RB=Ropa de Baño, RIF/RF=Ropa Íntima Femenina, RIM/RM=Ropa Íntima
# Masculina, REF/REM=Exterior, RDF=Deportivo) más palabras clave para el
# resto. Ver Sección 0.2 del documento de alcance para el detalle.
# ---------------------------------------------------------------------------
def derivar_linea(categoria: str) -> str:
    if not isinstance(categoria, str):
        return "SIN CATEGORIA"
    c = categoria.upper().strip()

    if c.startswith("RB "):
        return "Playa"
    if c.startswith("RIF ") or c.startswith("RF "):
        return "Intimo/Lenceria (Mujer)"
    if c.startswith("RIM ") or c.startswith("RM "):
        return "Hombre"
    if c.startswith("REF "):
        return "Exterior/Activewear Mujer"
    if c.startswith("REM "):
        return "Exterior/Activewear Hombre"
    if c.startswith("RDF "):
        return "Deportivo Mujer"

    if any(k in c for k in ["ROPA DE BAÑO", "BIKINI", "ENTERIZO", "PAREO", "SANDALIA"]):
        return "Playa"
    if any(k in c for k in ["PIJAMA", "BATA", "PANTUFLA", "LOUNGEWEAR", "KIMONO", "SALIDA DE CAMA"]):
        return "Homewear"
    if any(k in c for k in ["BABY DOLL", "CORSET", "LIGUERO", "SEXY", "CONJUNTO SENSUAL", "BRALETTE"]):
        return "Sexy Lingerie"
    if any(k in c for k in ["BOXER", "CALZONCILLO"]):
        return "Hombre"
    if any(k in c for k in ["BRASIER", "PANTY", "TOP", "BODY", "FAJA", "BRATOP", "BRIEF", "SEMIBODY", "PANTYMEDIA"]):
        return "Intimo/Lenceria (Mujer)"

    return "Otros/Accesorios"


def construir(csv_path: str, db_path: str) -> None:
    print(f"Leyendo {csv_path} ...")
    df = pd.read_csv(csv_path, encoding="cp1252", low_memory=False)

    # Normalización de tipos
    df["PRECIO FINAL"] = pd.to_numeric(df["PRECIO FINAL"], errors="coerce").fillna(0.0)
    df["CANTIDAD"] = pd.to_numeric(df["CANTIDAD"], errors="coerce").fillna(0).astype(int)
    df["COSTO TOTAL"] = pd.to_numeric(df.get("COSTO TOTAL"), errors="coerce")
    df["FECHA"] = pd.to_datetime(df["F. DOCUMENTO"], format="%d/%m/%Y", errors="coerce")

    # Derivaciones de negocio -- ver docstring del módulo
    df["MARCA"] = df["PRODUCTO"].apply(derivar_marca)
    df["LINEA_PRODUCTO"] = df["CATEGORÍA"].apply(derivar_linea)

    # Solo las columnas que el dashboard necesita -- no se replica el detalle
    # completo de 55 columnas (costos de importación, aduana, etc. quedan
    # fuera del demo, no aportan a las vistas construidas).
    cols = [
        "FECHA", "SUCURSAL", "CIUDAD", "VENDEDOR", "CÓDIGO", "PRODUCTO",
        "CATEGORÍA", "MARCA", "LINEA_PRODUCTO", "CANTIDAD",
        "PRECIO FINAL", "COSTO TOTAL",
    ]
    ventas = df[cols].rename(columns={
        "CÓDIGO": "CODIGO",
        "CATEGORÍA": "CATEGORIA",
        "PRECIO FINAL": "PRECIO_FINAL",
        "COSTO TOTAL": "COSTO_TOTAL",
    })
    ventas = ventas.dropna(subset=["FECHA"])

    print(f"Filas procesadas: {len(ventas):,}")
    print(f"Rango de fechas: {ventas['FECHA'].min().date()} a {ventas['FECHA'].max().date()}")
    print(f"Marca identificada en {(ventas['MARCA'] != 'SIN IDENTIFICAR').mean()*100:.1f}% de las filas")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    ventas.to_sql("ventas", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX idx_ventas_fecha ON ventas(FECHA)")
    con.execute("CREATE INDEX idx_ventas_marca ON ventas(MARCA)")
    con.execute("CREATE INDEX idx_ventas_linea ON ventas(LINEA_PRODUCTO)")
    con.execute("CREATE INDEX idx_ventas_sucursal ON ventas(SUCURSAL)")
    con.commit()
    con.close()
    print(f"Base construida en {db_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python build_data.py <ruta_csv> <ruta_salida_db>")
        sys.exit(1)
    construir(sys.argv[1], sys.argv[2])
