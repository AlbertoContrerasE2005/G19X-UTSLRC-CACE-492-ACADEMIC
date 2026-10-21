"""Base compartida de las pruebas.

Prepara la base de datos de pruebas (dataops_test) sin tocar tus datos
y ofrece una clase base con los metodos Auxiliares que usan todos los
archivos de prueba.

Requiere un MySQL/MariaDB local (por omision 127.0.0.1:3306).
"""

import os
import unittest
from pathlib import Path

# Fuerza la base de pruebas ANTES de importar backend: el paquete backend
# carga el .env, y si el .env define DATAOPS_DB_NAME (por ejemplo "dataops")
# las pruebas se ejecutarian contra la base real y la vaciarian.
os.environ["DATAOPS_DB_NAME"] = "dataops_test"

from fastapi.testclient import TestClient

from backend import db as mydb
from backend.app import create_app

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = "dataops_test"

H = {"X-Requested-With": "DataOps"}
HEADERS = H
ADMIN = {"username": "tester", "password": "ClavePrueba2026!", "name": "Tester"}

# Tablas que se limpian entre pruebas (el orden respeta las dependencias).
TABLES = (
    "ai_queries",
    "activity_logs",
    "approvals",
    "audit",
    "records",
    "sales",
    "run_rows",
    "run_logs",
    "runs",
    "reports",
    "anomalies",
    "alerts",
    "quality_results",
    "quality_rules",
    "project_members",
    "datasets",
    "pipelines",
    "projects",
    "sessions",
    "users",
)


def recreate_database():
    """Borra y crea la base de pruebas desde cero."""
    conn = mydb.connect(db="")
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
            cur.execute(f"CREATE DATABASE {TEST_DB} CHARACTER SET utf8mb4")
    finally:
        conn.close()


def fresh_schema():
    """Aplica db/schema.sql en la base de pruebas."""
    sql = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    clean = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )
    conn = mydb.connect()
    try:
        with conn.cursor() as cur:
            for stmt in [s.strip() for s in clean.split(";")]:
                if stmt:
                    cur.execute(stmt)
    finally:
        conn.close()


def clean_db():
    """Vacia las tablas sin recrear el esquema."""
    conn = mydb.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table in TABLES:
                cur.execute(f"TRUNCATE TABLE {table}")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    finally:
        conn.close()


class BaseTestCase(unittest.TestCase):
    """Clase base: base limpia, app instanciada y sesion iniciada."""

    admin = ADMIN

    @classmethod
    def setUpClass(cls):
        recreate_database()
        fresh_schema()

    def setUp(self):
        clean_db()
        fresh_schema()
        self.app = create_app(background=False)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.post("/setup", self.admin)
        self.post("/login", self.admin)
        self.store = self.app.state.store

    def tearDown(self):
        self.client.__exit__(None, None, None)

    # -- metodos auxiliares -------------------------------------------

    def post(self, path, value):
        return self.client.post("/api" + path, json=value, headers=H)

    def get(self, path):
        return self.client.get("/api" + path)

    def request(self, method, path, payload=None):
        return self.client.request(method, "/api" + path, json=payload, headers=H)

    def demo_run(self):
        """Carga el ejemplo de ventas, lo ejecuta y devuelve el run id."""
        dataset = self.post("/demo", {}).json()
        run_id = self.post("/runs", {"dataset_id": dataset["id"]}).json()["id"]
        self.app.state.worker.tick()
        return run_id
