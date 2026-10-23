"""Ronda extendida: estres 5000 filas, recuperacion, programacion,
idempotencia, exports y neutralizacion de formulas.

La preparacion de la base vive en tests/base.py.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

# base primero: fija DATAOPS_DB_NAME=dataops_test antes de importar backend.
from base import ADMIN, H, BaseTestCase  # noqa: E402

from backend import db as mydb  # noqa: E402


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

    # -- concurrencia (mejora 2 de MEJORAS_FUTURAS) -------------------

    def test_bloqueo_no_conseguido_responde_reintentar(self):
        """Si el bloqueo no se consigue, se pide reintentar (503).

        Se simula que otro proceso tiene la seccion ocupada.
        """
        from contextlib import contextmanager

        from backend import db as dbmod

        did = self.post("/demo", {}).json()["id"]
        real = dbmod.named_lock

        @contextmanager
        def sin_bloqueo(name, timeout=10):
            yield False  # como si GET_LOCK no hubiera obtenido el bloqueo

        dbmod.named_lock = sin_bloqueo
        try:
            r = self.post("/runs", {"dataset_id": did})
        finally:
            dbmod.named_lock = real

        self.assertEqual(r.status_code, 503)
        self.assertIn("Intenta de nuevo", r.json()["detail"])
        # Y no se encolo nada.
        activos = self.store.one(
            "SELECT COUNT(*) AS n FROM runs WHERE status IN ('queued', 'running')"
        )["n"]
        self.assertEqual(activos, 0)

    def test_indice_unico_impide_dos_ejecuciones_activas(self):
        """La base de datos sola impide dos ejecuciones activas.

        Se intenta insertar una segunda fila en 'queued' saltandose la
        comprobacion de la aplicacion: el indice unico lo impide.
        """
        import pymysql

        did = self.post("/demo", {}).json()["id"]
        # Primera ejecucion activa (queda en 'queued').
        self.post("/runs", {"dataset_id": did})

        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                with self.assertRaises(pymysql.err.IntegrityError):
                    cur.execute(
                        "INSERT INTO runs (id, dataset_id, pipeline_id,"
                        " trigger_kind, status, created_at)"
                        " VALUES ('segundo', %s, 'p_ventas', 'manual',"
                        " 'queued', NOW())",
                        (did,),
                    )
        finally:
            conn.close()

        activos = self.store.one(
            "SELECT COUNT(*) AS n FROM runs WHERE status IN ('queued', 'running')"
        )["n"]
        self.assertEqual(activos, 1)

    def test_bloqueo_con_nombre_serializa_el_encolado(self):
        """El bloqueo con nombre impide que dos procesos se cuelen."""
        from backend import db as dbmod

        with dbmod.named_lock("dataops_queue") as obtenido:
            self.assertTrue(obtenido)

            # Mientras el bloqueo esta tomado, otra conexion no lo obtiene.
            with dbmod.named_lock("dataops_queue", timeout=0) as segundo:
                self.assertFalse(segundo, "el bloqueo deberia estar tomado")

    def test_bloqueo_es_por_base_de_datos(self):
        """El lock incluye la base: dos bases no se bloquean entre si.

        Los locks de MySQL son por servidor, no por base. Sin el nombre
        de la base, el servidor (dataops) y las pruebas (dataops_test)
        se estorban y las pruebas fallan de forma intermitente.
        """
        from backend import db as dbmod

        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT GET_LOCK(%s, 0)", ("dataops_queue_dataops_test",))
                tomado = cur.fetchone()
                self.assertEqual(list(tomado.values())[0], 1)
                # Con otro nombre de base si se puede tomar.
                cur.execute("SELECT GET_LOCK(%s, 0)", ("dataops_queue_dataops",))
                otro = cur.fetchone()
                self.assertEqual(list(otro.values())[0], 1)
                cur.execute("SELECT RELEASE_LOCK(%s)", ("dataops_queue_dataops",))
        finally:
            conn.close()

    # -- transacciones (mejora 1 de MEJORAS_FUTURAS) ------------------
    def test_transaccion_revierte_aprobacion_parcial(self):
        """Si la aprobacion falla a la mitad, no queda nada a medias.

        Se inyecta un fallo en la segunda insercion: ni la carga, ni los
        contadores, ni la auditoria deben quedar guardados.
        """
        from contextlib import contextmanager

        import backend.db as dbmod

        run_id = self.demo_run()
        detail = self.get(f"/runs/{run_id}").json()
        lines = [r["line"] for r in detail["rows"] if r["status"] == "anomaly"]
        self.assertEqual(len(lines), 2)

        sales_antes = self.store.one("SELECT COUNT(*) AS n FROM sales")["n"]
        approved_antes = self.store.one(
            "SELECT approved FROM runs WHERE id = %s", (run_id,)
        )["approved"]

        # Cursor que falla en la segunda carga a sales.
        class CursorQueFalla:
            def __init__(self, cur):
                self._cur = cur
                self.inserciones = 0

            def execute(self, sql, params=None):
                if "INSERT IGNORE INTO sales" in sql:
                    self.inserciones += 1
                    if self.inserciones == 2:
                        raise RuntimeError("Fallo simulado a mitad de la carga")
                if params is None:
                    return self._cur.execute(sql)
                return self._cur.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._cur, name)

        transaccion_real = dbmod.transaction

        @contextmanager
        def transaccion_con_fallo():
            with transaccion_real() as cur:
                yield CursorQueFalla(cur)

        dbmod.transaction = transaccion_con_fallo
        try:
            # El error del motor revierte la transaccion y sube como 500.
            with self.assertRaises(RuntimeError):
                self.post(
                    f"/runs/{run_id}/approve",
                    {"lines": lines, "motivo": "Prueba de transaccion"},
                )
        finally:
            dbmod.transaction = transaccion_real

        # Nada quedo a medias.
        sales_despues = self.store.one("SELECT COUNT(*) AS n FROM sales")["n"]
        approved_despues = self.store.one(
            "SELECT approved FROM runs WHERE id = %s", (run_id,)
        )["approved"]
        approvals = self.store.one(
            "SELECT COUNT(*) AS n FROM approvals WHERE run_id = %s", (run_id,)
        )["n"]
        anomalias = self.store.one(
            "SELECT anomalies FROM runs WHERE id = %s", (run_id,)
        )["anomalies"]

        self.assertEqual(sales_despues, sales_antes, "se cargaron filas de mas")
        self.assertEqual(approved_despues, approved_antes, "el contador cambio")
        self.assertEqual(approvals, 0, "quedo auditoria sin carga")
        self.assertEqual(anomalias, 2, "las anomalias siguen pendientes")


if __name__ == "__main__":
    unittest.main(verbosity=2)
