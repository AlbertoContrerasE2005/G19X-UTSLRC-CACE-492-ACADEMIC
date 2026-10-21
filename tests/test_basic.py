"""Pruebas basicas del flujo: carga, ejecucion, aprobacion y concurrencia.

La preparacion de la base vive en tests/base.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from base import ADMIN, H, BaseTestCase


class FlowTests(BaseTestCase):
    def test_demo_completo(self):
        """70 filas: 64 cargadas, 4 invalidas, 2 alertas."""
        run_id = self.demo_run()
        run = self.get(f"/runs/{run_id}").json()
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
        run = self.get(f"/runs/{run_id}").json()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["loaded"], 2)

    def test_aprobar_y_rechazar(self):
        run_id = self.demo_run()
        detail = self.get(f"/runs/{run_id}").json()
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
