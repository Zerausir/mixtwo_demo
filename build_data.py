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


# ---------------------------------------------------------------------------
# Derivación de FORMATO_ID -- señal independiente para detectar cuentas
# mayoristas/corporativas (ver EDA/instrucciones del proyecto, Sección 2.2):
# el RUC ecuatoriano de empresa tiene 13 dígitos y termina en "001"; la
# cédula de persona natural tiene 10 dígitos. El valor genérico
# "9999999999999" es "consumidor final" (venta de mostrador sin registrar
# comprador) -- no es ni empresa ni persona identificada.
# ---------------------------------------------------------------------------
IDENTIFICACION_GENERICA = "9999999999999"


def derivar_formato_id(identificacion: str) -> str:
    if not isinstance(identificacion, str):
        identificacion = str(identificacion)
    identificacion = identificacion.strip()
    if identificacion == IDENTIFICACION_GENERICA:
        return "CONSUMIDOR FINAL"
    if len(identificacion) == 13 and identificacion.endswith("001"):
        return "RUC (empresa)"
    if len(identificacion) == 10:
        return "CÉDULA (persona)"
    return "OTRO FORMATO"


def construir(csv_path: str, db_path: str) -> None:
    print(f"Leyendo {csv_path} ...")
    df = pd.read_csv(csv_path, encoding="cp1252", low_memory=False)

    # --- Deduplicación por clave de venta -------------------------------
    # El CSV es un cruce (JOIN) entre la venta y el/los lote(s) de compra o
    # importación que la abastecieron. Cuando una venta se surte de más de
    # un lote, la fila de venta se repite una vez por lote -- verificado:
    # 889 líneas de venta (1,924 filas) se repiten 2 a 9 veces, con las
    # columnas de VENTA idénticas y solo las de COMPRA (FOB, CIF, costos)
    # cambiando. Sin deduplicar, esto infla ventas totales en ~1.4%
    # ($9,982.75 sobre $708,589.23). Se deduplica ANTES de cualquier
    # cálculo, usando solo las columnas del lado de venta como clave.
    cols_clave_venta = [
        "F. DOCUMENTO", "SUCURSAL", "FACTURERO", "NÚMERO", "CÓDIGO",
        "PRODUCTO", "CATEGORÍA", "CANTIDAD", "PRECIO FINAL", "VENDEDOR",
    ]
    filas_antes = len(df)
    df = df.drop_duplicates(subset=cols_clave_venta, keep="first")
    print(f"Filas eliminadas por duplicación venta-compra: {filas_antes - len(df):,}")

    # Normalización de tipos
    df["PRECIO FINAL"] = pd.to_numeric(df["PRECIO FINAL"], errors="coerce").fillna(0.0)
    df["CANTIDAD"] = pd.to_numeric(df["CANTIDAD"], errors="coerce").fillna(0).astype(int)
    df["COSTO TOTAL"] = pd.to_numeric(df.get("COSTO TOTAL"), errors="coerce")
    df["FECHA"] = pd.to_datetime(df["F. DOCUMENTO"], format="%d/%m/%Y", errors="coerce")

    # Derivaciones de negocio -- ver docstring del módulo
    df["MARCA"] = df["PRODUCTO"].apply(derivar_marca)
    df["LINEA_PRODUCTO"] = df["CATEGORÍA"].apply(derivar_linea)

    # Normalización: CIUDAD tiene 31 grupos de duplicados por formato en el
    # origen (ej. "QUITO"/"Quito"/"quito" como 3 valores distintos, ver
    # EDA Sección 4.1). No se usa todavía en el dashboard, pero se
    # normaliza aquí para que quede resuelto antes de que el análisis
    # geo-demográfico (Nivel Macro) lo necesite.
    df["CIUDAD"] = df["CIUDAD"].astype(str).str.strip().str.upper()

    # FORMATO_ID -- ver docstring arriba. IDENTIFICACIÓN se preserva tal
    # cual (string) para no perder ceros a la izquierda de las cédulas.
    df["IDENTIFICACIÓN"] = df["IDENTIFICACIÓN"].astype(str).str.strip()
    df["FORMATO_ID"] = df["IDENTIFICACIÓN"].apply(derivar_formato_id)

    # --- ORDEN_ID: unidad real de "transacción" -------------------------
    # Cada fila del CSV es una LÍNEA de producto dentro de una factura, no
    # una transacción en sí. IMPORTANTE: FACTURERO + NÚMERO por sí solos
    # NO son una clave única -- el mismo par se repite en fechas distintas
    # y sucursales distintas (verificado: 1,150 de 11,069 "órdenes"
    # agrupadas solo por FACTURERO+NÚMERO mezclaban >1 sucursal, algunas
    # con meses de diferencia entre sí -- la numeración de factura no es
    # global, se reutiliza). Se agrega FECHA y SUCURSAL a la clave para
    # garantizar unicidad real: con esta clave, cada grupo tiene
    # exactamente 1 sucursal por construcción.
    df["ORDEN_ID"] = (
            df["FACTURERO"].astype(str) + "-" +
            df["NÚMERO"].astype(str) + "-" +
            df["FECHA"].dt.strftime("%Y%m%d") + "-" +
            df["SUCURSAL"].astype(str)
    )

    # --- ES_PUNTO_VENTA: MATRIZ no es una tienda retail comparable -------
    # El EDA mostró que MATRIZ es 55% línea Hombre y 0% Playa -- mix
    # incompatible con cualquier otra sucursal, consistente con un centro
    # administrativo/mayorista, no un punto de venta al público. Se marca
    # en vez de eliminarse, para que las vistas puedan excluirla
    # explícitamente sin perder el dato.
    df["ES_PUNTO_VENTA"] = df["SUCURSAL"] != "MATRIZ"

    # Solo las columnas que el dashboard necesita -- no se replica el detalle
    # completo de 55 columnas (costos de importación, aduana, etc. quedan
    # fuera del demo, no aportan a las vistas construidas).
    cols = [
        "FECHA", "ORDEN_ID", "SUCURSAL", "ES_PUNTO_VENTA", "CIUDAD", "VENDEDOR",
        "IDENTIFICACIÓN", "CLIENTE", "FORMATO_ID",
        "CÓDIGO", "PRODUCTO", "CATEGORÍA", "MARCA", "LINEA_PRODUCTO", "CANTIDAD",
        "PRECIO FINAL", "COSTO TOTAL",
    ]
    ventas = df[cols].rename(columns={
        "CÓDIGO": "CODIGO",
        "CATEGORÍA": "CATEGORIA",
        "PRECIO FINAL": "PRECIO_FINAL",
        "COSTO TOTAL": "COSTO_TOTAL",
        "IDENTIFICACIÓN": "IDENTIFICACION",
    })
    ventas = ventas.dropna(subset=["FECHA"])

    print(f"Filas procesadas: {len(ventas):,}")
    print(f"Órdenes reales (ORDEN_ID únicos): {ventas['ORDEN_ID'].nunique():,}")
    print(f"Rango de fechas: {ventas['FECHA'].min().date()} a {ventas['FECHA'].max().date()}")
    print(f"Marca identificada en {(ventas['MARCA'] != 'SIN IDENTIFICAR').mean() * 100:.1f}% de las filas")
    n_ruc = (ventas["FORMATO_ID"] == "RUC (empresa)").sum()
    print(f"Líneas con identificación tipo RUC (empresa, candidatas a mayorista): {n_ruc:,}")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    ventas.to_sql("ventas", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX idx_ventas_fecha ON ventas(FECHA)")
    con.execute("CREATE INDEX idx_ventas_marca ON ventas(MARCA)")
    con.execute("CREATE INDEX idx_ventas_linea ON ventas(LINEA_PRODUCTO)")
    con.execute("CREATE INDEX idx_ventas_sucursal ON ventas(SUCURSAL)")
    con.execute("CREATE INDEX idx_ventas_identificacion ON ventas(IDENTIFICACION)")
    con.commit()
    con.close()
    print(f"Base construida en {db_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python build_data.py <ruta_csv> <ruta_salida_db>")
        sys.exit(1)
    construir(sys.argv[1], sys.argv[2])
