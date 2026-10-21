"""Worker: programa pipelines y ejecuta los runs encolados en un hilo."""

import threading
import time
import uuid

from backend import db as mydb
from backend.engine import Engine
from backend.settings import now
from backend.store import Store

# ---------------------------------------------------------------- worker


class Worker:
    """Hilo único: programa pipelines y ejecuta runs encolados."""

    def __init__(self, store):
        self.store = store
        self.engine = Engine(store)
        self.stop_event = threading.Event()
        self.thread = None

    def recover(self):
        """Al arrancar: lo 'running' vuelve a 'queued'."""
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM runs WHERE status = 'running'")
                ids = [r["id"] for r in cur.fetchall()]
                cur.execute(
                    "UPDATE runs SET status = 'queued', stage = 'queued'"
                    " WHERE status = 'running'"
                )
                cur.execute(
                    "DELETE FROM sessions WHERE expires_at < %s", (time.time(),)
                )
        finally:
            conn.close()
        for rid in ids:
            self.store.log(rid, "queued", "Recuperada tras reinicio.")

    def schedule(self):
        """Dispara pipelines vencidos (1 por ciclo, si no hay activa)."""
        # Bajo el mismo bloqueo que usa la API para encolar: comprobar y
        # encolar sin que otro proceso se cuele en medio.
        with mydb.named_lock("dataops_queue") as _:
            if self.store.one(
                "SELECT id FROM runs WHERE status IN ('queued', 'running') LIMIT 1"
            ):
                return
            due = self.store.all(
                "SELECT * FROM pipelines WHERE enabled = 1"
                " AND dataset_id IS NOT NULL AND next_run IS NOT NULL"
                " AND next_run <= %s ORDER BY next_run LIMIT 1",
                (time.time(),),
            )
            for p in due:
                new_id = uuid.uuid4().hex
                conn = mydb.connect()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO runs (id, dataset_id, pipeline_id,"
                            " trigger_kind, status, created_at)"
                            " VALUES (%s, %s, %s, 'scheduled', 'queued', %s)",
                            (new_id, p["dataset_id"], p["id"], now()),
                        )
                        cur.execute(
                            "UPDATE pipelines SET next_run = %s WHERE id = %s",
                            (
                                time.time() + (p["interval_minutes"] or 0) * 60,
                                p["id"],
                            ),
                        )
                except Exception:
                    return
                finally:
                    conn.close()
                self.store.audit(None, "scheduled_run", new_id)
                break

    def tick(self):
        """Atiende un run encolado. Devuelve True si hizo algo."""
        self.schedule()
        row = self.store.one(
            "SELECT id FROM runs WHERE status = 'queued'" " ORDER BY created_at LIMIT 1"
        )
        if not row:
            return False
        run_id = row["id"]
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE runs SET status = 'running', started_at = %s,"
                    " attempts = attempts + 1 WHERE id = %s AND status = 'queued'",
                    (now(), run_id),
                )
                if cur.rowcount == 0:
                    return False
        finally:
            conn.close()
        try:
            self.engine.process(run_id)
        except Exception as exc:  # noqa: BLE001 (worker nunca debe morir)
            import logging
            import pymysql as _pm

            info = self.store.one("SELECT attempts FROM runs WHERE id = %s", (run_id,))
            retry = isinstance(exc, (_pm.OperationalError, OSError)) and (
                info["attempts"] < 2
            )
            msg = (
                "Error temporal; se reintenta una vez."
                if retry
                else "Fallo el proceso. Revisa el log."
            )
            conn = mydb.connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE runs SET status = %s, stage = %s, error = %s,"
                        " finished_at = %s WHERE id = %s",
                        (
                            "queued" if retry else "failed",
                            "queued" if retry else "failed",
                            msg,
                            None if retry else now(),
                            run_id,
                        ),
                    )
            finally:
                conn.close()
            self.store.log(run_id, "queued" if retry else "failed", msg)
            if not retry:
                try:
                    rec = self.store.one(
                        "SELECT r.dataset_id, d.project_id FROM runs r"
                        " LEFT JOIN datasets d ON d.id = r.dataset_id"
                        " WHERE r.id = %s",
                        (run_id,),
                    )
                    self.store.alert(
                        "error",
                        "Pipeline fallido",
                        msg,
                        "run",
                        run_id,
                        (rec and rec.get("project_id")) or "p_default",
                    )
                except Exception:
                    pass
            logging.exception("Fallo run %s", run_id)
        return True

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                import logging

                logging.exception("Error en worker")
            self.stop_event.wait(10)

    def start(self):
        self.recover()
        self.thread = threading.Thread(
            target=self.loop, name="dataops-worker", daemon=True
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=30)
