"""Paquete backend.

Al importarse, carga el archivo .env si existe (sin sobreescribir variables
ya definidas en el entorno). Asi copiar .env.example como .env basta para
configurar la base de datos y la IA.
"""

from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - si no se instalo python-dotenv
    load_dotenv = None


def _cargar_env():
    if load_dotenv is None:
        return
    # override=False: las variables ya fijadas en el entorno ganan.
    # Asi las pruebas pueden fijar DATAOPS_DB_NAME antes de importar.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


_cargar_env()
