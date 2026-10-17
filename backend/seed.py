"""Datos de prueba locales: python -m backend.seed (desde la raíz del proyecto).

Crea (si no existen) usuarios demo, proyecto DEMO, tres datasets de ejemplo
(ventas, pasteles y productos SQL), un pipeline y una regla de calidad,
y ejecuta el pipeline. Pensado para probar en tu equipo.

No borra ni modifica datos existentes: solo agrega lo que falta.
"""

import json
import os
import uuid

from backend import db as mydb
from backend.core import (
    ROOT,
    Store,
    Worker,
    now,
    parse_csv_dynamic,
    password_hash,
    rows_to_csv,
)

USERS = [
    ("demo", "Usuario DEMO", "Demo2026!!segura", "admin"),
    ("admin", "Administrador DEMO", "DataOps2026!segura", "admin"),
    ("ingeniero", "Ingeniera DEMO", "DataOps2026!segura", "operator"),
    ("consulta", "Usuario DEMO", "DataOps2026!segura", "viewer"),
]

# (nombre archivo, contenido de ejemplo)
PASTELES = (
    "id_pastel,sabor,precio,stock\n"
    "P-001,Chocolate,150.00,20\n"
    "P-002,Vainilla,120.50,15\n"
    "P-003,Fresa,130.00,18\n"
    "P-004,Limón,110.00,22\n"
    "P-005,Chocolate,150.00,9\n"
)
PRODUCTOS_SQL = (
    "INSERT INTO productos (sku, nombre, costo) VALUES\n"
    "  ('S-001','Tuerca',5.50),('S-002','Perno',7.25),\n"
    "  ('S-003','Arandela',1.10),('S-004','Tornillo',3.40);\n"
)


def ensure_user(store, username, name, password, role):
    """Crea el usuario si no existe y devuelve su id."""
    row = store.one("SELECT id FROM users WHERE username = %s", (username,))
    if row:
        print(f"  usuario ya existe: {username} ({row['id'] if 'id' in row else row})")
        return row["id"] if isinstance(row, dict) else row
    store.run(
        "INSERT INTO users (username, name, password_hash, role, created_at)"
        " VALUES (%s, %s, %s, %s, %s)",
        (username, name, password_hash(password), role, now()),
    )
    new = store.one("SELECT id FROM users WHERE username = %s", (username,))["id"]
    print(f"  usuario creado: {username} ({role})")
    return new


def ensure_dataset(store, filename, content, project_id, user_id, file_type="csv"):
    """Crea el dataset si no existe y devuelve su id."""
    row = store.one("SELECT id FROM datasets WHERE filename = %s", (filename,))
    if row:
        print(f"  archivo ya existe: {filename}")
        return row["id"]
    columns, rows = parse_csv_dynamic(content)
    did = uuid.uuid4().hex
    store.run(
        "INSERT INTO datasets"
        " (id, filename, content, columns_json, row_count, created_at,"
        " created_by, project_id, file_type, quality_score)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)",
        (
            did,
            filename,
            rows_to_csv(columns, rows),
            json.dumps(columns),
            len(rows),
            now(),
            user_id,
            project_id,
            file_type,
        ),
    )
    print(f"  archivo creado: {filename} ({len(rows)} registros)")
    return did


def main():
    # Asegura base + tablas antes de sembrar.
    mydb.init_schema()
    store = Store()

    print("Sembrando datos de prueba...")
    admin_id = ensure_user(store, *USERS[0])
    ensure_user(store, *USERS[1])
    ensure_user(store, *USERS[2])
    ensure_user(store, *USERS[3])

    # Proyecto DEMO (o p_default si ya existe).
    proj = store.one("SELECT id FROM projects WHERE id = 'p_default'")
    pid = proj["id"] if proj else None
    if not pid:
        pid = "prj_demo0001"
        store.run(
            "INSERT INTO projects (id, name, description, status, owner_id,"
            " created_at, updated_at) VALUES (%s, %s, %s, 'activo', %s, %s, %s)",
            (
                pid,
                "Proyecto DEMO",
                "Datos de prueba para explorar la plataforma.",
                admin_id,
                now(),
                now(),
            ),
        )
        print("  proyecto creado: Proyecto DEMO")

    # Datasets: ventas del repo + pasteles + SQL generados aquí.
    ventas = (ROOT / "examples" / "ventas_ejemplo.csv").read_text(encoding="utf-8")
    did_ventas = ensure_dataset(store, "ventas_ejemplo.csv", ventas, pid, admin_id)
    did_pasteles = ensure_dataset(store, "pasteles.csv", PASTELES, pid, admin_id, "csv")
    ensure_dataset(store, "productos.sql", PRODUCTOS_SQL, pid, admin_id, "sql")

    # Pipeline DEMO apuntando a ventas.
    pipe = store.one("SELECT id FROM pipelines WHERE id = 'p_demo0001'")
    if not pipe:
        steps = [
            "validar_estructura",
            "eliminar_duplicados",
            "tratar_nulos",
            "convertir_tipos",
            "ejecutar_reglas",
            "detectar_anomalias",
            "guardar_resultado",
        ]
        store.run(
            "INSERT INTO pipelines (id, name, description, dataset_id,"
            " interval_minutes, enabled, created_at, created_by, project_id,"
            " steps_json, status, run_count)"
            " VALUES (%s, %s, %s, %s, 0, 0, %s, %s, %s, %s, 'activo', 0)",
            (
                "p_demo0001",
                "Pipeline DEMO",
                "Pipeline de prueba.",
                did_ventas,
                now(),
                admin_id,
                pid,
                json.dumps(steps),
            ),
        )
        print("  pipeline creado: Pipeline DEMO")

    # Regla de calidad de ejemplo.
    if not store.one("SELECT id FROM quality_rules WHERE id = 'rl_demo0001'"):
        store.run(
            "INSERT INTO quality_rules (id, project_id, dataset_id, pipeline_id,"
            " column_name, `condition`, value, severity, active, created_by,"
            " created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)",
            (
                "rl_demo0001",
                pid,
                did_ventas,
                "p_demo0001",
                "cantidad",
                "gte",
                "1",
                "alta",
                admin_id,
                now(),
            ),
        )
        print("  regla creada: cantidad >= 1 (severidad alta)")

    # Ejecuta el pipeline DEMO una vez.
    worker = Worker(store)
    active = store.one("SELECT id FROM runs WHERE status IN ('queued', 'running')")
    if active:
        print(f"  ya hay una ejecución activa; se omite ({active['id'][:8]})")
    else:
        run_id = store.queue(did_ventas, admin_id, "manual", None, "p_demo0001")
        worker.tick()
        run = store.one(
            "SELECT status, total, loaded, invalid, anomalies FROM runs WHERE id = %s",
            (run_id,),
        )
        print(
            f"  ejecución: {run['status']} total={run['total']}"
            f" cargados={run['loaded']} inválidos={run['invalid']}"
            f" anomalías={run['anomalies']}"
        )
        # Segunda ejecución sobre pasteles para ver esquema dinámico.
        run2 = store.queue(did_pasteles, admin_id, "manual", None, "p_demo0001")
        worker.tick()
        r2 = store.one("SELECT status, total, loaded FROM runs WHERE id = %s", (run2,))
        print(
            f"  ejecución pasteles (dinámica): {r2['status']}"
            f" total={r2['total']} cargados={r2['loaded']}"
        )

    print("Listo. Entra con admin / DataOps2026!segura o demo / Demo2026!!segura")


if __name__ == "__main__":
    main()
