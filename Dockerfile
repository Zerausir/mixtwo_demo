# Imagen del demo mixtwo — SQLite embebido, sin dependencias externas.
#
# El CSV crudo NUNCA se versiona en Git (ver .gitignore). Para construir
# la imagen, primero copia el archivo del cliente a data/ventas_mixtwo.csv
# en tu máquina (no se sube a GitHub), y luego:
#
#   docker build -t mixtwo-demo .
#
# El build ejecuta build_data.py una sola vez, en este paso, y el
# resultado (mart.db) queda empaquetado dentro de la imagen.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Construye la base de datos de solo lectura a partir del CSV crudo.
# Si data/ventas_mixtwo.csv no existe en el contexto de build, esto falla
# explícitamente en vez de servir un demo vacío sin avisar.
RUN python build_data.py data/ventas_mixtwo.csv data/mart.db

EXPOSE 8050

# Cloud Run inyecta la variable PORT -- config.py ya la respeta
# (ver APP_PORT / PORT en config.py). gunicorn la lee vía --bind.
CMD exec gunicorn --bind :${PORT:-8050} --workers 2 --threads 4 --timeout 60 app:server
