"""Motor DataOps: fachada que reexporta los modulos del motor.

La implementacion vive en modulos con una responsabilidad cada uno:
  settings.py    constantes, tiempo y seguridad
  data_io.py     lectura de CSV/Excel/SQL y exportacion
  validators.py  reglas de calidad
  store.py       acceso a MySQL
  engine.py      motor de una ejecucion
  worker.py      hilo que programa y ejecuta pipelines

Este modulo se mantiene para no romper los imports existentes.
"""

from backend.data_io import (
    csv_export,
    parse_csv_dynamic,
    parse_csv_strict,
    parse_excel_dynamic,
    parse_sql_dynamic,
    rows_to_csv,
)
from backend.engine import Engine
from backend.settings import (
    COLUMNS,
    MAX_BYTES,
    MAX_ROWS,
    MODEL_GENERIC,
    MODEL_SALES,
    ROOT,
    clean_header,
    now,
    password_hash,
    password_ok,
)
from backend.store import Store
from backend.validators import validate_generic, validate_sales
from backend.worker import Worker

__all__ = [
    "COLUMNS",
    "MAX_BYTES",
    "MAX_ROWS",
    "MODEL_GENERIC",
    "MODEL_SALES",
    "ROOT",
    "Engine",
    "Store",
    "Worker",
    "clean_header",
    "csv_export",
    "now",
    "parse_csv_dynamic",
    "parse_csv_strict",
    "parse_excel_dynamic",
    "parse_sql_dynamic",
    "password_hash",
    "password_ok",
    "rows_to_csv",
    "validate_generic",
    "validate_sales",
]
