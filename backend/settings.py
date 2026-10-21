"""Constantes, tiempo y funciones de seguridad del proyecto.

Modulo hoja: no importa nada del proyecto, solo la libreria estandar.
"""

import hashlib
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Columnas del caso ventas (unico caso con reglas estrictas).
COLUMNS = ["id", "fecha", "producto", "cantidad", "precio_unitario"]

MAX_BYTES = 10 * 1024 * 1024  # 10 MiB por archivo.
MAX_ROWS = 20000  # Filas maximas por archivo.
MODEL_SALES = "ventas-v1"
MODEL_GENERIC = "generico-v1"


def now():
    """Fecha actual ISO UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def clean_header(name):
    """Normaliza un nombre de columna: minusculas, sin espacios raros."""
    name = str(name or "").strip().lower().replace(" ", "_")[:64]
    name = re.sub(r"[^a-z0-9_\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1.\-]", "", name)
    return name or "col"


def password_hash(password):
    """Hash scrypt con sal de 16 bytes. Formato sal:hash en hex."""
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + value.hex()


def password_ok(password, stored):
    """Compara contrasena contra hash (tiempo constante)."""
    salt, expected = stored.split(":")
    value = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
    )
    return secrets.compare_digest(value.hex(), expected)
