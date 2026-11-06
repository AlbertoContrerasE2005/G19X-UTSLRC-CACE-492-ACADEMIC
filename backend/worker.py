"""Worker: programa pipelines y ejecuta los runs encolados en un hilo."""

import threading
import time
import uuid

import pymysql

from backend import db as mydb
from backend.engine import Engine
from backend.settings import now
from backend.store import Store

# ---------------------------------------------------------------- worker

# Espera entre ciclos: normal y cuando la base de datos no responde.
WAIT_OK = 10
WAIT_DB_DOWN = 30

# Codigos de error de MySQL que indican caida/conexion perdida, no un SQL malo.
DB_DOWN_CODES = (2002, 2003, 2006, 2013)


def _db_down(exc):
    """True si la excepcion es de conexion (servidor caido o conexion perdida)."""
    if isinstance(exc, (OSError, pymysql.err.InterfaceError)):
        return True
    code = exc.args[0] if getattr(exc, "args", None) else None
    return code in DB_DOWN_CODES


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
        # Primero se mira si hay algo vencido (solo lectura, sin bloqueo).
        # Asi el worker no tomaria el bloqueo cada 10 segundos sin motivo.
        if not self.store.one(
            "SELECT id FROM pipelines WHERE enabled = 1"
            " AND dataset_id IS NOT NULL AND next_run IS NOT NULL"
            " AND next_run <= %s LIMIT 1",
            (time.time(),),
        ):
            return
        # Bajo el mismo bloqueo que usa la API para encolar: comprobar y
        # encolar sin que otro proceso se cuele en medio.
        with mydb.named_lock("dataops_queue") as bloqueo:
            if not bloqueo:
                return
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
        import logging

        offline = False
        while not self.stop_event.is_set():
            try:
                self.tick()
                if offline:
                    logging.warning("Conexion con la base de datos restablecida.")
                    offline = False
                wait = WAIT_OK
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError, OSError) as exc:
                if _db_down(exc):
                    # Se avisa una sola vez para no inundar la consola.
                    if not offline:
                        logging.warning(
                            "Base de datos no disponible (%s)."
                            " El worker reintentara cada %s s.",
                            exc,
                            WAIT_DB_DOWN,
                        )
                        offline = True
                    wait = WAIT_DB_DOWN
                else:
                    logging.exception("Error en worker")
                    wait = WAIT_OK
            except Exception:  # noqa: BLE001
                logging.exception("Error en worker")
                wait = WAIT_OK
            self.stop_event.wait(wait)

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
