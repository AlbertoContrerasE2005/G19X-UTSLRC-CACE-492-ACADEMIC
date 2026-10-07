"""Cobertura total 1x1 + fallos provocados (base dataops_test)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
os.environ["DATAOPS_DB_NAME"] = "dataops_test"

from fastapi.testclient import TestClient

from backend import db as mydb
from backend.app import create_app
from test_full import clean_db, fresh_schema, H, ADMIN


class All(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = mydb.connect(db="")
        try:
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS dataops_test")
                cur.execute("CREATE DATABASE dataops_test CHARACTER SET utf8mb4")
        finally:
            conn.close()
        fresh_schema()

    def setUp(self):
        clean_db()
        fresh_schema()
        self.app = create_app(background=False)
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.post("/setup", ADMIN)
        self.post("/login", ADMIN)

    def tearDown(self):
        self.c.__exit__(None, None, None)

    def post(self, path, value):
        return self.c.post("/api" + path, json=value, headers=H)

    def get(self, path):
        return self.c.get("/api" + path)

    # ---- auth y usuarios ----

    def test_01_setup_duplicado_y_login_malo(self):
        self.assertEqual(self.post("/setup", ADMIN).status_code, 409)
        self.assertEqual(
            self.post(
                "/login", {"username": "nadie", "password": "x" * 12}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.post(
                "/users",
                {"username": "xx", "password": "corta", "name": "N", "role": "x"},
            ).status_code,
            400,
        )

    def test_02_admin_no_se_queda_sin_admin(self):
        me = self.get("/me").json()
        self.assertEqual(
            self.c.request(
                "PUT", f"/api/users/{me['id']}", json={"role": "viewer"}, headers=H
            ).status_code,
            400,
        )
        self.assertEqual(
            self.c.delete(f"/api/users/{me['id']}", headers=H).status_code, 400
        )

    def test_03_viewer_bloqueado_en_todo(self):
        self.post(
            "/users",
            {
                "username": "visor9",
                "password": "ClaveQa2026!!",
                "name": "V",
                "role": "viewer",
            },
        )
        self.post("/logout", {})
        self.post("/login", {"username": "visor9", "password": "ClaveQa2026!!"})
        for method, path, payload in [
            ("POST", "/demo", {}),
            ("POST", "/datasets", {"filename": "a.csv", "content": "a,b\n1,2"}),
            ("POST", "/pipelines", {"name": "x"}),
            ("POST", "/projects", {"name": "x"}),
            ("POST", "/quality/rules", {"column": "a", "condition": "gte"}),
        ]:
            r = self.c.request(method, "/api" + path, json=payload, headers=H)
            self.assertEqual(r.status_code, 403, path)
        self.assertEqual(self.c.delete("/api/alerts/1", headers=H).status_code, 403)

    # ---- datasets ----

    def test_04_dataset_errores_provdmocados(self):
        self.assertEqual(
            self.post("/datasets", {"filename": "a.csv", "content": ""}).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "/datasets", {"filename": "a.csv", "content": "solo,una\n1"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "/datasets", {"filename": "a.xlsx", "content_b64": "!!!no-base64!!!"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "/datasets", {"filename": "a.sql", "content": "SELECT 1"}
            ).status_code,
            400,
        )
        self.assertEqual(self.get("/datasets/falso").status_code, 404)
        self.assertEqual(self.get("/datasets/falso/profile").status_code, 404)

    def test_05_dataset_borrar_cascada(self):
        did = self.post(
            "/datasets", {"filename": "b.csv", "content": "k,v\nA,1\n"}
        ).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        self.assertEqual(
            self.c.delete(f"/api/datasets/{did}", headers=H).status_code, 200
        )
        self.assertEqual(self.get(f"/runs/{rid}").status_code, 404)

    def test_06_rows_buscar_ordenar(self):
        did = self.post(
            "/datasets",
            {"filename": "c.csv", "content": "k,v\nB,2\nA,1\nC,3\n"},
        ).json()["id"]
        r = self.get(f"/datasets/{did}/rows?search=b&limit=10").json()
        self.assertEqual(r["total"], 1)
        r = self.get(f"/datasets/{did}/rows?sort=k&order=desc&limit=10").json()
        self.assertEqual(r["items"][0]["k"], "C")

    # ---- pipelines ----

    def test_07_pipeline_errores(self):
        self.assertEqual(self.post("/pipelines", {"name": "x" * 81}).status_code, 400)
        self.assertEqual(
            self.post("/pipelines/p_falso", {"interval_minutes": 999}).status_code,
            404,
        )
        did = self.post("/demo", {}).json()["id"]
        pid = self.post("/pipelines", {"name": "PX"}).json()["id"]
        self.assertEqual(
            self.post(
                f"/pipelines/{pid}",
                {"dataset_id": did, "interval_minutes": 7},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(f"/pipelines/{pid}", {"interval_minutes": 15}).status_code,
            400,  # frecuencia sin archivo
        )

    def test_08_pipeline_steps(self):
        pid = self.post("/pipelines", {"name": "PS"}).json()["id"]
        self.assertEqual(self.post(f"/pipelines/{pid}", {"steps": []}).status_code, 400)
        self.assertEqual(
            self.post(f"/pipelines/{pid}", {"steps": ["a", "b"]}).status_code,
            200,
        )
        got = self.get(f"/pipelines/{pid}").json()
        self.assertEqual(got["steps_json"], '["a", "b"]')

    # ---- runs ----

    def test_09_run_errores(self):
        self.assertEqual(self.post("/runs", {"dataset_id": "falso"}).status_code, 404)
        self.assertEqual(
            self.post(
                "/runs", {"dataset_id": "x", "pipeline_id": "p_falsa"}
            ).status_code,
            404,
        )
        did = self.post("/demo", {}).json()["id"]
        r1 = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.assertEqual(
            self.post("/runs", {"dataset_id": did, "parent_id": r1}).status_code,
            400,  # aún no termina
        )
        self.assertEqual(self.get("/runs/falso").status_code, 404)
        self.assertEqual(self.get("/runs?status=raro").status_code, 400)

    def test_10_export_kinds(self):
        did = self.post("/demo", {}).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        for kind in ("all", "issues", "accepted", "pending", "rejected"):
            r = self.c.get(f"/api/runs/{rid}/export?kind={kind}")
            self.assertEqual(r.status_code, 200, kind)
        self.assertEqual(
            self.c.get(f"/api/runs/{rid}/export?kind=raro").status_code, 400
        )

    def test_11_review_errores(self):
        did = self.post("/demo", {}).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        det = self.get(f"/runs/{rid}").json()
        lines = [r["line"] for r in det["rows"] if r["status"] == "anomaly"]
        self.assertEqual(
            self.post(
                f"/runs/{rid}/approve", {"lines": [], "motivo": "abc"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                f"/runs/{rid}/approve", {"lines": lines, "motivo": "xx"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                f"/runs/{rid}/approve", {"lines": [999999], "motivo": "nada aquí"}
            ).status_code,
            400,
        )
        ok = self.post(f"/runs/{rid}/approve", {"lines": lines, "motivo": "todas ok"})
        self.assertEqual(ok.json()["reviewed"], 2)
        # Doble aprobación ya no encuentra pendientes.
        self.assertEqual(
            self.post(
                f"/runs/{rid}/approve", {"lines": lines, "motivo": "otra vez"}
            ).status_code,
            400,
        )

    # ---- calidad / anomalías / alertas ----

    def test_12_reglas_crud_y_evaluar(self):
        did = self.post("/demo", {}).json()["id"]
        self.assertEqual(
            self.post("/quality/rules", {"column": "", "condition": "gte"}).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "/quality/rules", {"column": "x", "condition": "raro"}
            ).status_code,
            400,
        )
        rid = self.post(
            "/quality/rules",
            {"column": "cantidad", "condition": "gte", "value": "1", "dataset_id": did},
        ).json()["id"]
        ev = self.post("/quality/evaluate", {"dataset_id": did}).json()
        self.assertIn("quality", ev)
        self.assertEqual(
            self.c.request(
                "PUT",
                f"/api/quality/rules/{rid}",
                json={"condition": "raro"},
                headers=H,
            ).status_code,
            400,
        )
        self.assertEqual(
            self.c.delete(f"/api/quality/rules/{rid}", headers=H).status_code, 200
        )
        self.assertEqual(
            self.c.delete("/api/quality/rules/rl_falsa", headers=H).status_code, 404
        )
        self.assertEqual(len(self.get("/quality/results").json()), 0)

    def test_13_anomalias_y_alertas(self):
        did = self.post("/demo", {}).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()
        items = self.get("/anomalies").json()
        self.assertGreaterEqual(items["total"], 2)
        aid = items["items"][0]["id"]
        self.assertEqual(
            self.c.request(
                "PATCH", f"/api/anomalies/{aid}", json={"status": "raro"}, headers=H
            ).status_code,
            400,
        )
        self.assertEqual(
            self.c.request(
                "PATCH", f"/api/anomalies/{aid}", json={"status": "resuelta"}, headers=H
            ).status_code,
            200,
        )
        al = self.get("/alerts").json()
        self.assertGreaterEqual(al["total"], 1)
        self.assertEqual(
            self.post(f"/alerts/{al['items'][0]['id']}/read", {}).status_code, 200
        )
        self.assertEqual(self.post("/alerts/read-all", {}).status_code, 200)
        self.assertEqual(
            self.c.delete(f"/api/alerts/{al['items'][0]['id']}", headers=H).status_code,
            200,
        )

    # ---- reportes / actividad / dashboard / IA ----

    def test_14_reportes(self):
        did = self.post("/demo", {}).json()["id"]
        self.assertEqual(
            self.post("/reports", {"dataset_id": did, "type": "raro"}).status_code, 400
        )
        self.assertEqual(
            self.post("/reports", {"dataset_id": did, "format": "raro"}).status_code,
            400,
        )
        self.assertEqual(
            self.post("/reports", {"dataset_id": "falso"}).status_code, 404
        )
        rid = self.post(
            "/reports", {"dataset_id": did, "type": "calidad", "format": "pdf"}
        ).json()["id"]
        dl = self.get(f"/reports/{rid}/download")
        self.assertEqual(dl.status_code, 200)
        self.assertTrue(dl.content.startswith(b"%PDF"))
        self.assertEqual(self.get("/reports/falso").status_code, 404)

    def test_15_ia_errores_y_historia(self):
        did = self.post("/demo", {}).json()["id"]
        self.assertEqual(
            self.post("/ai/ask", {"dataset_id": did, "question": ""}).status_code, 400
        )
        self.assertEqual(self.post("/ai/ask", {"question": "hola"}).status_code, 400)
        ok = self.post(
            "/ai/ask", {"dataset_id": did, "question": "cuántos registros hay"}
        )
        self.assertEqual(ok.status_code, 200)
        self.assertIn("answer", ok.json())
        self.assertEqual(len(self.get("/ai/history").json()), 1)
        self.assertEqual(self.post("/ai/summary", {}).status_code, 400)
        self.assertEqual(self.post("/ai/recommendations", {}).status_code, 400)

    def test_16_dashboard_filtros(self):
        self.assertEqual(self.get("/dashboard?project_id=falso").status_code, 200)
        self.assertEqual(self.get("/monitoring").status_code, 200)
        self.assertEqual(self.get("/activity?search=zzz").status_code, 200)
        self.assertEqual(self.get("/config").status_code, 200)
        self.assertEqual(self.get("/template").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
