"""
config.py — Configuración por variables de entorno.

Simplificación deliberada respecto al patrón de OBTEL para este demo:
- No hay conexión a Postgres. Los datos viven en un SQLite de solo
  lectura empaquetado en la imagen (ver build_data.py y Dockerfile).
- No hay tabla de usuarios en base de datos. Las credenciales viven en
  la variable de entorno DASHBOARD_USERS, nunca en el código ni en Git
  (ver .env.example y README para cómo generarlas).

Esto es correcto para un demo de 1-2 usuarios con datos estáticos. La
arquitectura de producción (Fase 1 en adelante) SÍ necesita Postgres y
gestión de usuarios en base de datos, como en OBTEL -- este archivo no
pretende ser esa arquitectura, es la versión mínima suficiente para
demostrar el producto.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno requerida: {name}. "
            f"Revisa el archivo .env (ver .env.example)."
        )
    return value


def _parse_users(raw: str) -> dict[str, str]:
    """
    Formato esperado en DASHBOARD_USERS:
        usuario1:hash_bcrypt1,usuario2:hash_bcrypt2

    Generar cada hash con scripts/generar_hash.py -- nunca guardar la
    contraseña en texto plano en ningún lado.
    """
    usuarios: dict[str, str] = {}
    for par in raw.split(","):
        par = par.strip()
        if not par:
            continue
        if ":" not in par:
            raise RuntimeError(
                f"Entrada inválida en DASHBOARD_USERS: {par!r}. "
                f"Formato esperado usuario:hash_bcrypt."
            )
        usuario, hash_bcrypt = par.split(":", 1)
        usuarios[usuario.strip()] = hash_bcrypt.strip()
    return usuarios


@dataclass(frozen=True)
class Settings:
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("PORT", os.getenv("APP_PORT", "8050")))
    app_debug: bool = os.getenv("APP_DEBUG", "false").lower() in {"1", "true", "yes"}

    secret_key: str = os.getenv("SECRET_KEY", "")
    db_path: str = os.getenv("MART_DB_PATH", "data/mart.db")

    dashboard_users: dict[str, str] = field(default_factory=dict)

    cliente_nombre: str = os.getenv("CLIENTE_NOMBRE", "mixtwo")


def _build_settings() -> Settings:
    secret_key = _require_env("SECRET_KEY")
    dashboard_users = _parse_users(_require_env("DASHBOARD_USERS"))
    return Settings(secret_key=secret_key, dashboard_users=dashboard_users)


settings = _build_settings()
