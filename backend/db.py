"""Conexión MySQL simple con PyMySQL.

Lee credenciales de variables de entorno (o de un .env en la raíz):
  DATAOPS_DB_HOST, DATAOPS_DB_PORT, DATAOPS_DB_USER,
  DATAOPS_DB_PASSWORD, DATAOPS_DB_NAME

Por omisión usa 127.0.0.1:3306, el puerto estandar de MySQL/MariaDB.
Si tu servidor esta en otro puerto (por ejemplo 3307), cambia
DATAOPS_DB_PORT en el archivo .env.
"""

import os
from contextlib import contextmanager

import pymysql
import pymysql.cursors


def settings():
    """Devuelve dict de conexión (local por defecto)."""
    return {
        "host": os.environ.get("DATAOPS_DB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DATAOPS_DB_PORT", "3306")),
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


@contextmanager
def transaction():
    """Abre una conexion con transaccion.

    Todo lo que se ejecuta dentro se confirma junto al salir, o se
    revierte entero si hay un error. Se usa para operaciones que deben
    quedar consistentes: aprobar filas y cargar un run.
    """
    cfg = dict(settings())
    cfg["autocommit"] = False
    conn = pymysql.connect(**cfg)
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


@contextmanager
def named_lock(name, timeout=10):
    """Bloqueo con nombre de MySQL (GET_LOCK).

    Sirve para las secciones donde hay que comprobar y luego escribir
    (por ejemplo, comprobar que no hay una ejecucion activa y encolarla):
    dos procesos a la vez no pueden entrar en la seccion.

    El nombre incluye la base de datos: los locks de MySQL son por
    servidor, no por base, asi que dos bases distintas no deben
    bloquearse entre si (por ejemplo, las pruebas contra dataops_test
    y el servidor contra dataops).

    Devuelve True si se logro el bloqueo, False si se agoto el tiempo.
    """
    nombre = f"{name}_{settings()['database']}"
    conn = connect()
    acquired = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, %s)", (nombre, timeout))
            fila = cur.fetchone()
            acquired = bool(fila and list(fila.values())[0] == 1)
        yield acquired
    finally:
        if acquired:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT RELEASE_LOCK(%s)", (nombre,))
            except Exception:
                pass
        conn.close()


def init_schema():
    """Crea la base y las tablas desde db/schema.sql."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[1]
    sql = (base / "db" / "schema.sql").read_text(encoding="utf-8")

    # 1. Crear la base si no existe (sin elegir base).
    # El nombre viene de DATAOPS_DB_NAME para no quedar fijo en el código.
    db_name = settings()["database"]
    conn = connect(db="")
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}`" " CHARACTER SET utf8mb4"
            )
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

            # 3. Migracion suave: agregar solo lo que falte.
            _migrar(cur)

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


# Columnas que se agregan si no existen (para bases creadas antes).
_COLUMNAS = {
    "datasets": [
        ("project_id", "VARCHAR(16)"),
        ("quality_score", "DOUBLE NOT NULL DEFAULT 0"),
        ("file_type", "VARCHAR(8) NOT NULL DEFAULT 'csv'"),
    ],
    "pipelines": [
        ("project_id", "VARCHAR(16)"),
        ("status", "VARCHAR(16) NOT NULL DEFAULT 'activo'"),
        ("run_count", "INT NOT NULL DEFAULT 0"),
        ("last_run", "VARCHAR(40)"),
        ("steps_json", "TEXT"),
    ],
}


def _existe_columna(cur, tabla, columna):
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.COLUMNS"
        " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s"
        " AND COLUMN_NAME = %s",
        (tabla, columna),
    )
    return cur.fetchone()["n"] > 0


def _indices_de_runs(cur):
    """Devuelve las columnas del indice uq_one_active (vacio si no existe)."""
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.STATISTICS"
        " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'runs'"
        " AND INDEX_NAME = 'uq_one_active' ORDER BY SEQ_IN_INDEX"
    )
    return [r["COLUMN_NAME"] for r in cur.fetchall()]


def _migrar(cur):
    """Agrega lo que falte sin rehacer lo que ya existe.

    Si algo falla de verdad, avisa por pantalla en vez de tragarse el error.
    """
    avisos = []

    # Columnas nuevas.
    for tabla, columnas in _COLUMNAS.items():
        for nombre, tipo in columnas:
            if _existe_columna(cur, tabla, nombre):
                continue
            try:
                cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}")
            except Exception as exc:  # noqa: BLE001
                avisos.append(f"no se pudo agregar {tabla}.{nombre}: {exc}")

    # Indice de una sola ejecucion activa.
    if not _existe_columna(cur, "runs", "active_flag"):
        try:
            cur.execute(
                "ALTER TABLE runs ADD COLUMN active_flag TINYINT"
                " GENERATED ALWAYS AS"
                " (IF(status IN ('queued', 'running'), 1, NULL)) VIRTUAL"
            )
        except Exception as exc:  # noqa: BLE001
            avisos.append(f"no se pudo agregar runs.active_flag: {exc}")

    columnas_indice = _indices_de_runs(cur)
    if columnas_indice != ["active_flag"]:
        # Indice viejo (o ninguno): se reemplaza por el correcto.
        if columnas_indice:
            try:
                cur.execute("ALTER TABLE runs DROP INDEX uq_one_active")
            except Exception as exc:  # noqa: BLE001
                avisos.append(f"no se pudo quitar el indice anterior: {exc}")
        try:
            cur.execute("ALTER TABLE runs ADD UNIQUE KEY uq_one_active (active_flag)")
        except Exception as exc:  # noqa: BLE001
            avisos.append(
                "no se pudo crear el indice de ejecucion activa"
                f" (una sola ejecucion a la vez): {exc}"
            )

    for aviso in avisos:
        print(f"[DataOps] Aviso de esquema: {aviso}")
