"""Pruebas del proyecto nuevo (MySQL real en 3307).

Usan la base dataops_test para no tocar tus datos.
Requieren MariaDB en 127.0.0.1:3307 con root sin clave.
"""

import os
import unittest

os.environ["DATAOPS_DB_NAME"] = "dataops_test"

from fastapi.testclient import TestClient

from backend import db as mydb
from backend.app import create_app

HEADERS = {"X-Requested-With": "DataOps"}
ADMIN = {"username": "tester", "password": "ClavePrueba2026!", "name": "Tester"}


class FlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Base de pruebas limpia.
        conn = mydb.connect(db="")
        try:
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS dataops_test")
                cur.execute("CREATE DATABASE dataops_test CHARACTER SET utf8mb4")
        finally:
            conn.close()
        from pathlib import Path

        sql = (Path(__file__).resolve().parents[1] / "db" / "schema.sql").read_text()
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                clean = "\n".join(
                    ln for ln in sql.splitlines() if not ln.strip().startswith("--")
                )
                for stmt in [s.strip() for s in clean.split(";")]:
                    if stmt:
                        cur.execute(stmt)
        finally:
            conn.close()

    def setUp(self):
        # Tablas limpias entre pruebas (misma base de test).
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for t in (
                    "approvals",
                    "audit",
                    "records",
                    "sales",
                    "run_rows",
                    "run_logs",
                    "runs",
                    "datasets",
                    "sessions",
                ):
                    cur.execute(f"TRUNCATE TABLE {t}")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        finally:
            conn.close()
        self.app = create_app(background=False)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.post("/setup", ADMIN)
        self.post("/login", ADMIN)
        self.store = self.app.state.store

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def post(self, path, value):
        return self.client.post("/api" + path, json=value, headers=HEADERS)

    def test_demo_completo(self):
        """70 filas: 64 cargadas, 4 inválidas, 2 alertas."""
        d = self.post("/demo", {}).json()
        run_id = self.post("/runs", {"dataset_id": d["id"]}).json()["id"]
        self.app.state.worker.tick()
        run = self.client.get(f"/api/runs/{run_id}").json()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(
            (run["total"], run["invalid"], run["anomalies"], run["loaded"]),
            (70, 4, 2, 64),
        )

    def test_dinamico_pasteles(self):
        """Cualquier columna funciona (ej. pasteles)."""
        csv = "id_pastel,sabor,precio\nP-1,Chocolate,100\nP-2,Vainilla,120\n"
        d = self.post("/datasets", {"filename": "p.csv", "content": csv}).json()
        self.assertEqual(d["columns"], ["id_pastel", "sabor", "precio"])
        run_id = self.post("/runs", {"dataset_id": d["id"]}).json()["id"]
        self.app.state.worker.tick()
        run = self.client.get(f"/api/runs/{run_id}").json()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["loaded"], 2)

    def test_aprobar_y_rechazar(self):
        d = self.post("/demo", {}).json()
        run_id = self.post("/runs", {"dataset_id": d["id"]}).json()["id"]
        self.app.state.worker.tick()
        detail = self.client.get(f"/api/runs/{run_id}").json()
        lines = [r["line"] for r in detail["rows"] if r["status"] == "anomaly"]
        self.assertEqual(len(lines), 2)
        ok = self.post(
            f"/runs/{run_id}/approve",
            {"lines": lines[:1], "motivo": "Pico validado"},
        )
        self.assertEqual(ok.status_code, 200)
        bad = self.post(f"/runs/{run_id}/reject", {"lines": lines[1:], "motivo": "x"})
        self.assertEqual(bad.status_code, 400)  # motivo muy corto
        ok2 = self.post(
            f"/runs/{run_id}/reject", {"lines": lines[1:], "motivo": "No aplica"}
        )
        self.assertEqual(ok2.status_code, 200)

    def test_solo_una_activa(self):
        d = self.post("/demo", {}).json()
        self.assertEqual(self.post("/runs", {"dataset_id": d["id"]}).status_code, 202)
        self.assertEqual(self.post("/runs", {"dataset_id": d["id"]}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
