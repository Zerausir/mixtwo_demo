# mixtwo — Demo de Inteligencia de Datos

Demo de evaluación para mixtwo: dashboard con login que muestra el análisis
descriptivo de la muestra de ventas compartida (~6 meses, ene-jul 2026) —
marca derivada por reglas de negocio, peso por línea de producto, tendencia
semanal y un explorador filtrable de transacciones.

**Esto NO es la arquitectura de producción de las Fases 1-4.** Es
deliberadamente más simple: datos estáticos en SQLite embebido, dos
usuarios fijos, sin pipeline en vivo contra el ERP. El objetivo es mostrar
de forma tangible el análisis ya realizado, no anticipar el sistema completo.

## Arquitectura

- **Dash + Flask-Login**, patrón adaptado de un proyecto propio anterior
  (autenticación por sesión, sin autorregistro).
- **SQLite de solo lectura**, construido una vez en el build de la imagen
  Docker a partir del CSV del cliente (`build_data.py`).
- **Sin base de datos externa que mantener** — todo vive en la imagen del
  contenedor. Correcto para un demo; no para producción con datos en vivo.
- Usuarios definidos por variable de entorno (`DASHBOARD_USERS`), con
  contraseña hasheada en bcrypt — nunca en texto plano ni en el código.

## Estructura

```
app.py                 Shell principal: navegación, layout, arranque
auth.py                Login / logout / guard de sesión
config.py              Configuración por variables de entorno
build_data.py           ETL: CSV crudo -> mart.db (deriva MARCA y LINEA_PRODUCTO)
pages/                  Una página por archivo (Dash Pages)
  inicio.py             Resumen ejecutivo + tendencia semanal
  marcas_lineas.py       Peso por línea y por marca
  explorador.py          Tabla filtrable de transacciones
services/
  database.py           Conexión SQLite de solo lectura
  queries.py             Consultas analíticas usadas por las páginas
components/ui.py        Componentes de interfaz reutilizables (KPI cards, etc.)
templates/login.html    Página de login (Flask plano, fuera de Dash)
assets/styles.css       Estilos
scripts/generar_hash.py Utilidad para generar hashes bcrypt de contraseñas
```

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 1. Coloca el CSV del cliente (NO se sube a Git) en data/ventas_mixtwo.csv
# 2. Construye la base de datos:
python build_data.py data/ventas_mixtwo.csv data/mart.db

# 3. Configura credenciales:
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # -> pega en SECRET_KEY
python scripts/generar_hash.py                                # -> genera hash por usuario, pega en DASHBOARD_USERS

# 4. Corre la app:
python app.py
# -> http://localhost:8050
```

## Despliegue en Google Cloud Run

Por qué Cloud Run + GCP para este demo: es el único proveedor grande con
cómputo permanentemente gratuito para cargas de bajo tráfico (2M
solicitudes/mes en la capa siempre-gratis), sin la trampa de instancias
"gratis por 12 meses" que después empiezan a cobrar solas.

### Requisitos previos

- Cuenta de Google Cloud con facturación habilitada (no cobra dentro de
  la capa gratuita, pero pide tarjeta para verificar identidad).
- [`gcloud` CLI](https://cloud.google.com/sdk/docs/install) instalado.
- El repositorio de este demo en GitHub, **en modo privado** — contiene
  la arquitectura de un cliente de consultoría; no hay razón para
  exponerlo públicamente.

### Pasos

```bash
# 1. Autenticación
gcloud auth login
gcloud config set project TU_PROYECTO_GCP

# 2. Habilitar los servicios necesarios (una sola vez)
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# 3. Coloca el CSV real en data/ventas_mixtwo.csv (localmente, NO en Git)
#    antes del build -- Cloud Build necesita el archivo en el contexto.

# 4. Construir y desplegar en un solo paso
gcloud run deploy mixtwo-demo \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "SECRET_KEY=TU_SECRET_KEY,DASHBOARD_USERS=gerardo:HASH1,alejandro:HASH2,MART_DB_PATH=data/mart.db,CLIENTE_NOMBRE=mixtwo"
```

**Nota sobre `--allow-unauthenticated`:** esto permite que cualquiera
llegue a la URL pública del servicio — pero la aplicación misma exige
login (`auth.py` bloquea todo sin sesión válida). Es el mismo modelo que
un sitio web normal: la URL es pública, el contenido no lo es sin
credenciales. Si prefieres una capa adicional de restricción a nivel de
red (por ejemplo, solo IPs conocidas), Cloud Run también soporta
`--no-allow-unauthenticated` con Identity-Aware Proxy, pero es
complejidad adicional que no hace falta para un demo de 2 usuarios.

**Región:** `us-central1` está entre las regiones que califican para la
capa siempre-gratuita de Cloud Run — no cambies de región sin verificar
que la nueva también califique.

### Después del despliegue

`gcloud run deploy` imprime la URL pública del servicio
(`https://mixtwo-demo-XXXXX-uc.a.run.app`). Compártela junto con las
credenciales de Gerardo y Alejandro por un canal separado (no en el mismo
correo que el link, por higiene básica de seguridad).

### Costos esperados

Con 2 usuarios evaluando el demo de forma ocasional, el tráfico se queda
muy por debajo de la cuota gratuita de Cloud Run (2M solicitudes/mes).
Costo esperado: **$0/mes**. Configura una alerta de presupuesto de todas
formas (Billing → Budgets & alerts, ej. $5) para enterarte si algo
escala sin que lo notes.

## Seguridad — antes de compartir el link

- [ ] `SECRET_KEY` generado con `secrets.token_hex(32)`, no un valor de prueba.
- [ ] Contraseñas de Gerardo y Alejandro generadas con `scripts/generar_hash.py`,
      nunca reutilizadas de otro sistema.
- [ ] El repositorio de GitHub está en modo **privado**.
- [ ] `data/ventas_mixtwo.csv` y `data/mart.db` NO están en el historial de Git
      (verificar con `git log --all --full-history -- data/`).
- [ ] Credenciales compartidas por un canal distinto al del link de acceso.
