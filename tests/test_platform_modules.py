"""Cubre la division de platform_api.py en modulos por dominio (commit 7dbde3b).

Antes, toda la plataforma vivia en un unico archivo de mas de mil lineas.
Ahora cada dominio tiene su modulo:

  platform_quality.py    reglas, evaluacion, resultados y anomalias
  platform_reports.py    listar, crear, ver y descargar reportes

Esta prueba llama a endpoints de esos modulos para garantizar que la
division no rompio nada.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
os.environ["DATAOPS_DB_NAME"] = "dataops_test"

from fastapi.testclient import TestClient

from backend import db as mydb
from backend.app import create_app
from test_full import clean_db, fresh_schema, H, ADMIN


class PlatformModulesTest(unittest.TestCase):
    """Endpoints de platform_quality.py y platform_reports.py."""

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

    def request(self, method, path, payload=None):
        return self.c.request(method, "/api" + path, json=payload, headers=H)

    # -- platform_quality.py -------------------------------------------

    def test_reglas_crud_y_evaluacion(self):
        """Reglas: crear, listar, actualizar, evaluar y eliminar."""
        did = self.post("/demo", {}).json()["id"]

        rid = self.post(
            "/quality/rules",
            {"column": "cantidad", "condition": "gte", "value": "1", "dataset_id": did},
        ).json()["id"]
        self.assertTrue(rid)

        rules = self.get("/quality/rules").json()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["column_name"], "cantidad")

        self.assertEqual(
            self.request("PUT", f"/quality/rules/{rid}", {"value": "5"}).status_code,
            200,
        )
        self.assertEqual(
            self.post("/quality/evaluate", {"dataset_id": did}).status_code,
            200,
        )
        self.assertEqual(
            self.request("DELETE", f"/quality/rules/{rid}").status_code,
            200,
        )
        self.assertEqual(len(self.get("/quality/rules").json()), 0)

    def test_resultados_de_calidad(self):
        """Ejecutar un pipeline deja resultados de calidad consultables."""
        did = self.post("/demo", {}).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()

        res = self.get(f"/quality/results?run_id={rid}").json()
        self.assertGreaterEqual(len(res), 1)
        self.assertEqual(res[0]["run_id"], rid)

    def test_anomalias_listar_y_resolver(self):
        """Anomalias: listar con filtros y resolver una."""
        did = self.post("/demo", {}).json()["id"]
        rid = self.post("/runs", {"dataset_id": did}).json()["id"]
        self.app.state.worker.tick()

        items = self.get("/anomalies?status=todas").json()
        self.assertGreaterEqual(items["total"], 2)

        aid = items["items"][0]["id"]
        self.assertEqual(
            self.request(
                "PATCH", f"/anomalies/{aid}", {"status": "resuelta"}
            ).status_code,
            200,
        )
        pending = self.get("/anomalies?status=pendiente").json()
        self.assertEqual(pending["total"], items["total"] - 1)

    # -- platform_reports.py -------------------------------------------

    def test_reportes_ciclo_completo(self):
        """Reportes: crear en los 3 formatos, ver y descargar."""
        did = self.post("/demo", {}).json()["id"]
        self.post("/runs", {"dataset_id": did})

        for fmt in ("json", "csv", "pdf"):
            with self.subTest(formato=fmt):
                r = self.post(
                    "/reports",
                    {"dataset_id": did, "type": "calidad", "format": fmt},
                )
                self.assertEqual(r.status_code, 200, r.text)
                rid = r.json()["id"]

                self.assertEqual(self.get(f"/reports/{rid}").status_code, 200)

                dl = self.c.get(f"/api/reports/{rid}/download")
                self.assertEqual(dl.status_code, 200)
                if fmt == "pdf":
                    self.assertTrue(dl.content.startswith(b"%PDF"))
                if fmt == "csv":
                    self.assertIn("Secci", dl.text)

        listing = self.get("/reports").json()
        self.assertEqual(len(listing), 3)

    # -- la division en si ---------------------------------------------

    def test_modulos_divididos_existen(self):
        """Los modulos por dominio estan presentes y registrables."""
        import importlib

        # Modulos con endpoints: cada uno expone register().
        for name in (
            "platform_projects",
            "platform_quality",
            "platform_monitoring",
            "platform_reports",
            "platform_ai",
            "platform_users",
        ):
            module = importlib.import_module(f"backend.{name}")
            self.assertTrue(
                hasattr(module, "register"),
                f"backend.{name} no define register()",
            )

        # Modulo de ayudantes compartidos: expone make_context().
        common = importlib.import_module("backend.platform_common")
        self.assertTrue(callable(common.make_context))

        # El orquestador registra todos los modulos sobre la app.
        from backend import platform_api

        self.assertTrue(callable(platform_api.register))


if __name__ == "__main__":
    unittest.main(verbosity=2)
