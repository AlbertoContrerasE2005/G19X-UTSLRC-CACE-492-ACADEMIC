"""Conexión MySQL simple con PyMySQL.

Lee credenciales de variables de entorno (con valores locales):
  DATAOPS_DB_HOST, DATAOPS_DB_PORT, DATAOPS_DB_USER,
  DATAOPS_DB_PASSWORD, DATAOPS_DB_NAME
"""

import os

import pymysql
import pymysql.cursors


def settings():
    """Devuelve dict de conexión (local por defecto)."""
    return {
        "host": os.environ.get("DATAOPS_DB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DATAOPS_DB_PORT", "3307")),
        "user": os.environ.get("DATAOPS_DB_USER", "root"),
        "password": os.environ.get("DATAOPS_DB_PASSWORD", ""),
        "database": os.environ.get("DATAOPS_DB_NAME", "dataops"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    }


def connect(db=None):
    """Abre una conexión. Si db=None usa la base configurada."""
    cfg = settings()
    if db is not None:
        cfg = dict(cfg)
        if db:
            cfg["database"] = db
        else:
            cfg.pop("database", None)
    return pymysql.connect(**cfg)


def init_schema():
    """Crea la base y las tablas desde db/schema.sql."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[1]
    sql = (base / "db" / "schema.sql").read_text(encoding="utf-8")

    # 1. Crear la base si no existe (sin elegir base).
    conn = connect(db="")
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS dataops CHARACTER SET utf8mb4")
    finally:
        conn.close()

    # 2. Ejecutar el esquema sentencia por sentencia.
    conn = connect()
    try:
        with conn.cursor() as cur:
            lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
            for stmt in [s.strip() for s in "\n".join(lines).split(";")]:
                if stmt:
                    cur.execute(stmt)
            # 3. Columnas de plataforma en tablas base (migración suave).
            for ddl in (
                "ALTER TABLE datasets ADD COLUMN project_id VARCHAR(16)",
                "ALTER TABLE datasets ADD COLUMN quality_score DOUBLE NOT NULL DEFAULT 0",
                "ALTER TABLE datasets ADD COLUMN file_type VARCHAR(8) NOT NULL DEFAULT 'csv'",
                "ALTER TABLE pipelines ADD COLUMN project_id VARCHAR(16)",
                "ALTER TABLE pipelines ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'activo'",
                "ALTER TABLE pipelines ADD COLUMN run_count INT NOT NULL DEFAULT 0",
                "ALTER TABLE pipelines ADD COLUMN last_run VARCHAR(40)",
                "ALTER TABLE pipelines ADD COLUMN steps_json TEXT",
            ):
                try:
                    cur.execute(ddl)
                except Exception:
                    pass  # La columna ya existe.
            cur.execute(
                "UPDATE pipelines SET project_id = 'p_default'"
                " WHERE project_id IS NULL"
            )
            cur.execute(
                "UPDATE datasets SET project_id = 'p_default'"
                " WHERE project_id IS NULL"
            )
    finally:
        conn.close()
