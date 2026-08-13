"""
generar_hash.py — Genera el hash bcrypt de una contraseña para pegar en
la variable de entorno DASHBOARD_USERS.

Uso:
    python scripts/generar_hash.py
    (pide la contraseña de forma oculta, no la muestra en pantalla ni
    la guarda en el historial de la terminal)

El resultado se pega en .env así:
    DASHBOARD_USERS=gerardo:$2b$12$....,alejandro:$2b$12$....
"""
from __future__ import annotations

import getpass

import bcrypt


def main() -> None:
    password = getpass.getpass("Contraseña a hashear: ")
    confirmacion = getpass.getpass("Confirma la contraseña: ")
    if password != confirmacion:
        print("Las contraseñas no coinciden. Intenta de nuevo.")
        return
    hash_bcrypt = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print("\nHash generado (cópialo tal cual, incluye los símbolos $):\n")
    print(hash_bcrypt)


if __name__ == "__main__":
    main()
