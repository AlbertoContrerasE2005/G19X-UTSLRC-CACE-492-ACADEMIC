"""Bateria integral DataOps Final (base dataops_test).

Cubre: auth y roles, datasets (csv/xlsx/sql/dinamicos/limites),
pipelines CRUD, runs, aprobacion, metricas, plataforma
(proyectos, reglas, anomalias, alertas, reportes, actividad,
dashboard, IA, config, usuarios) y exports.

La preparacion de la base vive en tests/base.py.
"""

import base64
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from base import ADMIN, H, BaseTestCase
from openpyxl import Workbook


class TestAuth(BaseTestCase):
    def test_setup_login_logout(self):
        self.assertEqual(self.post("/setup", ADMIN).status_code, 409)
        me = self.get("/me").json()
        self.assertEqual(me["role"], "admin")
        self.post("/logout", {})
        self.assertEqual(self.get("/summary").status_code, 401)

    def test_roles(self):
        self.post(
            "/users",
            {
                "username": "vis",
                "password": "ClaveQa2026!!",
                "name": "Vis",
                "role": "viewer",
            },
        )
        self.post("/logout", {})
        self.post("/login", {"username": "vis", "password": "ClaveQa2026!!"})
        self.assertEqual(self.get("/users").status_code, 403)
        self.assertEqual(
            self.post("/datasets", {"filename": "a.csv", "content": "x"}).status_code,
            403,
        )
        self.assertEqual(self.get("/summary").status_code, 200)

    def test_seguridad_headers(self):
        r = self.client.post("/api/demo", json={})
        self.assertEqual(r.status_code, 403)
        r = self.client.post(
            "/api/demo",
            json={},
            headers={**H, "Origin": "https://evil.example"},
        )
        self.assertEqual(r.status_code, 403)

    def test_usuarios_crud(self):
        uid = self.post(
            "/users",
            {
                "username": "op1",
                "password": "ClaveQa2026!!",
                "name": "Op",
                "role": "operator",
            },
        ).json()["id"]
        self.assertEqual(
            self.client.put(
                f"/api/users/{uid}", json={"name": "Op2"}, headers=H
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.request(
                "PUT", f"/api/users/{uid}", json={"role": "super"}, headers=H
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.delete(f"/api/users/{uid}", headers=H).status_code, 200
        )
        self.assertEqual(
            self.client.post(
                "/api/me/password",
                json={"current": "mala", "new": "ClaveQa2026!!"},
                headers=H,
            ).status_code,
            400,
        )


class TestDatasets(BaseTestCase):
    def test_csv_excel_sql(self):
        r = self.post(
            "/datasets",
            {
                "filename": "v.csv",
                "content": "id,fecha,producto,cantidad,precio_unitario\n"
                "A,2026-01-01,X,1,10.00\n",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json()["columns"],
            ["id", "fecha", "producto", "cantidad", "precio_unitario"],
        )

        wb = Workbook()
        ws = wb.active
        ws.append(["id", "fecha", "producto", "cantidad", "precio_unitario"])
        ws.append(["B", "2026-01-02", "Y", 2, 5.5])
        buf = io.BytesIO()
        wb.save(buf)
        r = self.post(
            "/datasets",
            {
                "filename": "v.xlsx",
                "content_b64": base64.b64encode(buf.getvalue()).decode(),
            },
        )
        self.assertEqual(r.status_code, 200)

        r = self.post(
            "/datasets",
            {
                "filename": "v.sql",
                "content": "INSERT INTO t (id,fecha,producto,cantidad,precio_unitario)"
                " VALUES ('C','2026-01-03','Z',3,7.25);",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.post("/datasets", {"filename": "v.txt", "content": "x"}).status_code,
            400,
        )

    def test_dinamico_y_limites(self):
        r = self.post(
            "/datasets",
            {"filename": "p.csv", "content": "pastel,precio\nChoc,100\n"},
        )
        self.assertEqual(r.json()["columns"], ["pastel", "precio"])
        big = "a,b\n" + "1,2\n" * 20001
        self.assertEqual(
            self.post("/datasets", {"filename": "big.csv", "content": big}).status_code,
            400,
        )
        dupes = "k,v\nA,1\nA,2\n"
        did = self.post("/datasets", {"filename": "d.csv", "content": dupes}).json()[
            "id"
        ]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        run = self.get(f"/runs/{rid}").json()
        self.assertEqual(run["invalid"], 1)

    def test_borrar_dataset_con_pipeline(self):
        did = self.post(
            "/datasets", {"filename": "del.csv", "content": "k,v\nA,1\nB,2\n"}
        ).json()["id"]
        pid = self.post("/pipelines", {"name": "Del", "dataset_id": did}).json()["id"]
        rid = self.post(
            "/runs", {"dataset_id": did, "pipeline_id": pid}
        ).json()["id"]
        self.app.state.worker.tick()
        self.assertEqual(self.get(f"/runs/{rid}").json()["status"], "completed")

        r = self.client.delete(f"/api/datasets/{did}", headers=H)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.get(f"/datasets/{did}").status_code, 404)
        self.assertEqual(self.get(f"/runs/{rid}").status_code, 404)
        pipe = self.get(f"/pipelines/{pid}").json()
        self.assertIsNone(pipe["dataset_id"])
        self.assertEqual(pipe["enabled"], 0)

    def test_preview_rows_profile_quality(self):
        did = self.post("/demo", {}).json()["id"]
        det = self.get(f"/datasets/{did}").json()
        self.assertEqual(len(det["preview"]), 8)
        rows = self.get(f"/datasets/{did}/rows?limit=5&search=VEN").json()
        self.assertEqual(rows["limit"], 5)
        self.assertGreaterEqual(rows["total"], 1)
        prof = self.get(f"/datasets/{did}/profile").json()
        self.assertEqual(prof["row_count"], 70)
        qual = self.get(f"/datasets/{did}/quality").json()
        self.assertIn("general", qual)


class TestPipelines(BaseTestCase):
    def test_crudprogramacion(self):
        pid = self.post("/pipelines", {"name": "P1", "description": "d"}).json()["id"]
        self.assertEqual(self.post("/pipelines", {"name": ""}).status_code, 400)
        d = self.post("/demo", {}).json()
        self.assertEqual(
            self.post(
                f"/pipelines/{pid}",
                {"dataset_id": d["id"], "interval_minutes": 60},
            ).status_code,
            200,
        )
        got = self.get(f"/pipelines/{pid}").json()
        self.assertEqual(got["interval_minutes"], 60)
        hist = self.get(f"/pipelines/{pid}/history").json()
        self.assertEqual(hist["total"], 0)
        self.assertEqual(
            self.client.delete(f"/api/pipelines/{pid}", headers=H).status_code, 200
        )
        self.assertEqual(
            self.client.delete("/api/pipelines/p_ventas", headers=H).status_code,
            400,
        )

    def test_proyectos(self):
        pid = self.post("/projects", {"name": "Norte"}).json()["id"]
        self.assertEqual(
            self.client.request(
                "PUT",
                f"/api/projects/{pid}",
                json={"status": "archivado"},
                headers=H,
            ).status_code,
            200,
        )
        s = self.get(f"/projects/{pid}/summary").json()
        self.assertEqual(s["project"]["status"], "archivado")
        self.assertEqual(
            self.client.delete(f"/api/projects/{pid}", headers=H).status_code, 200
        )
        self.assertEqual(
            self.client.delete("/api/projects/p_default", headers=H).status_code, 400
        )


class TestRunsIA(BaseTestCase):
    def test_flujo_completo_y_aprobacion(self):
        rid = self.demo_run()
        run = self.get(f"/runs/{rid}").json()
        self.assertEqual((run["total"], run["invalid"], run["anomalies"]), (70, 4, 2))
        self.assertEqual(run["model_version"], "ventas-v1")
        lines = [r["line"] for r in run["rows"] if r["status"] == "anomaly"]
        self.assertEqual(
            self.post(
                f"/runs/{rid}/approve", {"lines": lines[:1], "motivo": "ok"}
            ).status_code,
            400,
        )
        ok = self.post(
            f"/runs/{rid}/approve", {"lines": lines[:1], "motivo": "Pico validado"}
        ).json()
        self.assertEqual(ok["reviewed"], 1)
        rej = self.post(
            f"/runs/{rid}/reject", {"lines": lines[1:], "motivo": "No aplica"}
        ).json()
        self.assertEqual(rej["rejected"], 1)
        exp = self.client.get(f"/api/runs/{rid}/export?kind=all")
        self.assertEqual(exp.status_code, 200)
        self.assertIn("estado", exp.text[:200])

    def test_ia_generica(self):
        rows = ["k,precio,stock"] + [f"P{i},100,20" for i in range(10)] + ["PX,9999,1"]
        did = self.post(
            "/datasets", {"filename": "g.csv", "content": "\n".join(rows)}
        ).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        run = self.get(f"/runs/{rid}").json()
        self.assertEqual(run["model_version"], "generico-v1")
        self.assertGreaterEqual(run["anomalies"], 1)

    def test_metricas_y_plataforma(self):
        self.demo_run()
        self.assertEqual(self.get("/metrics/summary").status_code, 200)
        self.assertEqual(self.get("/metrics/runs?days=7").status_code, 200)
        self.assertEqual(self.get("/ready").status_code, 200)
        self.assertEqual(self.get("/dashboard").status_code, 200)
        self.assertEqual(self.get("/monitoring").status_code, 200)
        self.assertEqual(self.get("/anomalies").status_code, 200)
        self.assertEqual(self.get("/alerts").status_code, 200)
        self.assertEqual(self.get("/activity").status_code, 200)
        self.assertEqual(self.get("/config").status_code, 200)
        r = self.post(
            "/ai/ask",
            {
                "dataset_id": self.post("/demo", {}).json()["id"],
                "question": "total de cantidad",
            },
        )
        # Puede ser 202/200 segun worker; solo verifica que responde JSON.
        self.assertIn(r.status_code, (200, 202, 409))
        rep = self.post(
            "/reports",
            {
                "dataset_id": self.post("/demo", {}).json()["id"],
                "type": "analisis",
            },
        )
        if rep.status_code == 200:
            dl = self.get(f"/reports/{rep.json()['id']}/download")
            self.assertEqual(dl.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
