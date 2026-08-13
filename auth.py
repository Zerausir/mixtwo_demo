"""
auth.py — Autenticación del demo, adaptada de dashboard/auth.py de OBTEL.

Qué se mantiene igual (patrón probado, sin razón para cambiarlo):
- Flask-Login + bcrypt.
- Guard de sesión en @server.before_request, no en un callback de Dash --
  así ninguna página se sirve sin sesión válida.
- /login como ruta Flask plana con HTML simple, no una página de Dash.
- Mismo mensaje de error genérico exista o no el usuario -- no revela
  cuál de las dos cosas falló.

Qué cambia respecto a OBTEL (deliberado, ver config.py):
- Los usuarios viven en Settings.dashboard_users (desde la variable de
  entorno DASHBOARD_USERS), no en una tabla de Postgres. Sin
  autorregistro, sin base de datos de autenticación separada -- para
  2 usuarios fijos (Gerardo, Alejandro) esto es proporcional; una tabla
  con roles y reseteo de contraseña es sobre-ingeniería para un demo.
"""
from __future__ import annotations

import logging

import bcrypt
from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from config import settings

logger = logging.getLogger(__name__)

login_manager = LoginManager()
login_manager.login_view = "auth.login"

auth_bp = Blueprint("auth", __name__, template_folder="templates")


class Usuario(UserMixin):
    def __init__(self, username: str):
        self.id = username
        self.username = username


@login_manager.user_loader
def load_user(user_id: str):
    if user_id in settings.dashboard_users:
        return Usuario(user_id)
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/")

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").encode("utf-8")

        hash_guardado = settings.dashboard_users.get(username)

        # Mismo mensaje de error tanto si el usuario no existe como si la
        # contraseña es incorrecta -- no revelar cuál de las dos falló.
        if hash_guardado and bcrypt.checkpw(password, hash_guardado.encode("utf-8")):
            login_user(Usuario(username))
            siguiente = request.args.get("next") or "/"
            return redirect(siguiente)

        logger.info("Intento de login fallido para username=%r", username)
        error = "Usuario o contraseña incorrectos."

    return render_template("login.html", error=error, cliente_nombre=settings.cliente_nombre)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


def init_auth(server) -> None:
    """Llamar una sola vez desde app.py, después de crear server = app.server."""
    login_manager.init_app(server)
    server.register_blueprint(auth_bp)

    @server.before_request
    def _requerir_sesion():
        rutas_publicas = {"/login", "/logout"}
        es_interno_dash = request.path.startswith("/assets") or request.path.startswith("/_dash-")
        if request.path in rutas_publicas or es_interno_dash:
            return None
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        return None
