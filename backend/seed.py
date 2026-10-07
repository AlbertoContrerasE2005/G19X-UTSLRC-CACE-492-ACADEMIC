"""Datos de prueba locales: python -m backend.seed (desde la raíz del proyecto).

Crea (si no existen): usuarios admin/ingeniero/consulta, proyecto DEMO,
dataset ventas_demo.csv, pipeline y regla de ejemplo, y ejecuta el pipeline.
Nunca se ejecuta solo: úsalo para probar en tu equipo.
"""
import json
import uuid

from backend.core import ROOT, Store, Worker, now, password_hash, parse_csv_dynamic
from backend.profiling import profile_dataset, quality_score

USERS = [
    ("admin", "Administrador DEMO", "DataOps2026!segura", "admin"),
    ("ingeniero", "Ingeniera DEMO", "DataOps2026!segura", "operator"),
    ("consulta", "Usuario DEMO", "DataOps2026!segura", "viewer"),
]


def main():
    import os

    store = Store(os.environ.get("DATAOPS_DATA_DIR", str(ROOT / "data")))
    ids = {}
    with store.connect() as db:
        for username, name, pw, role in USERS:
            row = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if row:
                ids[username] = row["id"] if isinstance(row, dict) else row[0]
                continue
            cur = db.execute(
                "INSERT INTO users(username,name,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                (username, name, password_hash(pw), role, now()),
            )
            ids[username] = cur.lastrowid
            print(f"usuario creado: {username} ({role})")
    admin_id = ids["admin"]
    with store.connect() as db:
        proj = db.execute("SELECT id FROM projects WHERE name=?", ("Proyecto DEMO",)).fetchone()
        if proj:
            pid = proj["id"] if isinstance(proj, dict) else proj[0]
        else:
            pid = "prj_demo0001"
            ts = now()
            db.execute(
                "INSERT OR IGNORE INTO projects(id,name,description,status,owner_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (pid, "Proyecto DEMO", "Datos de prueba para explorar la plataforma.", "activo", admin_id, ts, ts),
            )
            print("proyecto creado: Proyecto DEMO")
    content = (ROOT / "examples/ventas_demo.csv").read_text(encoding="utf-8")
    columns, rows = parse_csv_dynamic(content)
    from backend.core import excel_rows_to_csv

    with store.connect() as db:
        ds = db.execute("SELECT id FROM datasets WHERE filename=?", ("ventas_demo.csv",)).fetchone()
        if ds:
            did = ds["id"] if isinstance(ds, dict) else ds[0]
        else:
            did = uuid.uuid4().hex
            prof = profile_dataset(columns, rows)
            qual = quality_score(columns, rows)
            db.execute(
                "INSERT INTO datasets(id,filename,content,row_count,created_at,created_by,columns_json,project_id,file_size,file_type,profile_json,quality_json,quality_score,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (did, "ventas_demo.csv", excel_rows_to_csv(rows, columns), len(rows), now(), admin_id,
                 json.dumps(columns), pid, len(content.encode()), "csv",
                 json.dumps(prof, ensure_ascii=False), json.dumps(qual, ensure_ascii=False),
                 qual.get("general", 0), "listo"),
            )
            print(f"dataset cargado: ventas_demo.csv ({len(rows)} registros, calidad {qual.get('general')}%)")
    with store.connect() as db:
        pl = db.execute("SELECT id FROM pipelines WHERE name=?", ("Pipeline DEMO",)).fetchone()
        if pl:
            pipe = pl["id"] if isinstance(pl, dict) else pl[0]
        else:
            pipe = "p_demo0001"
            db.execute(
                "INSERT INTO pipelines(id,name,description,dataset_id,interval_minutes,enabled,rules_json,created_at,created_by,project_id,steps_json,status,run_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pipe, "Pipeline DEMO", "Pipeline de prueba.", did, 0, 0, "{}", now(), admin_id, pid,
                 json.dumps(["validar_estructura", "eliminar_duplicados", "tratar_nulos", "convertir_tipos", "ejecutar_reglas", "detectar_anomalias", "guardar_resultado"]), "activo", 0),
            )
        rl = db.execute("SELECT id FROM quality_rules WHERE dataset_id=? AND column_name=?", (did, "cantidad")).fetchone()
        if not rl:
            db.execute(
                "INSERT INTO quality_rules(id,project_id,dataset_id,pipeline_id,column_name,condition,value,severity,active,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("rl_demo0001", pid, did, pipe, "cantidad", "gte", "1", "alta", 1, admin_id, now()),
            )
            print("regla creada: cantidad gte 1 (alta)")
    run_id = store.queue(did, admin_id, "manual", None, pipe)
    Worker(store).tick()
    run = store.one("SELECT status,total,loaded,invalid,anomalies FROM runs WHERE id=?", (run_id,))
    print(f"pipeline ejecutado: {run['status']} total={run['total']} cargados={run['loaded']} invalidos={run['invalid']} anomalias={run['anomalies']}")
    print("Listo. Entra con admin / DataOps2026!segura")


if __name__ == "__main__":
    main()
