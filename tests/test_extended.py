"""Ronda extendida: estres 5000 filas, recuperacion, programacion,
idempotencia, exports y neutralizacion de formulas.

La preparacion de la base vive en tests/base.py.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from backend import db as mydb
from base import ADMIN, H, BaseTestCase


class Extended(BaseTestCase):

    def test_estres_5000(self):
        rows = ["id,fecha,producto,cantidad,precio_unitario"]
        rows += [f"E-{i:05d},2026-03-01,Pieza,10,99.99" for i in range(5000)]
        t0 = time.perf_counter()
        did = self.post(
            "/datasets", {"filename": "big.csv", "content": "\n".join(rows)}
        ).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        dt = time.perf_counter() - t0
        run = self.client.get(f"/api/runs/{rid}").json()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["loaded"], 5000)
        print(f"\n5000 filas en {dt:.1f}s")

    def test_recuperacion(self):
        did = self.post("/demo", {}).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE runs SET status = 'running' WHERE id = %s", (rid,))
        finally:
            conn.close()
        from backend.core import Worker

        w = Worker(self.app.state.store)
        w.recover()
        w.tick()
        run = self.client.get(f"/api/runs/{rid}").json()
        self.assertEqual(run["status"], "completed")

    def test_programacion_vencida(self):
        did = self.post("/demo", {}).json()["id"]
        self.post(f"/pipelines/p_ventas", {"dataset_id": did, "interval_minutes": 15})
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE pipelines SET next_run = %s WHERE id = 'p_ventas'",
                    (time.time() - 5,),
                )
        finally:
            conn.close()
        self.app.state.worker.schedule()
        self.app.state.worker.schedule()
        n = self.app.state.store.one("SELECT COUNT(*) AS n FROM runs")["n"]
        self.assertEqual(n, 1)

    def test_idempotencia(self):
        did = self.post("/demo", {}).json()["id"]
        r1 = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        r2 = self.post("/runs", {"dataset_id": did, "parent_id": r1}).json()["id"]
        self.app.state.worker.tick()
        rep = self.client.get(f"/api/runs/{r2}").json()
        self.assertEqual(rep["loaded"], 0)
        self.assertGreater(rep["existing"], 0)

    def test_export_formulas(self):
        content = (
            "id,fecha,producto,cantidad,precio_unitario\n"
            "=1+1,2026-01-01,@cmd,1,1.00\n"
        )
        did = self.post("/datasets", {"filename": "f.csv", "content": content}).json()[
            "id"
        ]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        csv = self.client.get(f"/api/runs/{rid}/export?kind=all").text
        self.assertIn("'=1+1", csv)

    def test_concurrencia_409(self):
        did = self.post("/demo", {}).json()["id"]
        self.assertEqual(self.post("/runs", {"dataset_id": did}).status_code, 202)
        self.assertEqual(self.post("/runs", {"dataset_id": did}).status_code, 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
